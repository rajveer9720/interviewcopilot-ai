import { useEffect, useRef, useCallback, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useStore } from "../store";
import { apiClient, createSessionWebSocket, refreshAccessToken } from "../api/client";
import { PcmStreamer, int16ToBase64 } from "../lib/pcm";
import { Square, Mic, MicOff } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";

type TaggedWebSocket = WebSocket & { intentionalClose?: boolean };

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { session, transcripts, aiSuggestions, currentSuggestion, isCapturing, audioLevel,
    addTranscript, appendSuggestionToken, finalizeSuggestion, setCapturing, setAudioLevel } = useStore();
  const [aiStatus, setAiStatus] = useState<"idle" | "thinking">("idle");
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);
  const [sourceLabel, setSourceLabel] = useState("");
  const wsRef = useRef<TaggedWebSocket | null>(null);
  const pcmRef = useRef<PcmStreamer | null>(null);
  const streamsRef = useRef<MediaStream[]>([]);
  const pendingAudioRef = useRef<Int16Array[]>([]);
  const pendingSamplesRef = useRef(0);
  const captureSourceRef = useRef("system");
  const activeRequestRef = useRef<string | null>(null);
  const endAckRef = useRef<(() => void) | null>(null);
  const captureStartingRef = useRef(false);
  const mountedRef = useRef(true);
  const endingRef = useRef(false);
  const authenticatedRef = useRef(false);

  const handleWsMessage = useCallback((event: MessageEvent) => {
    let msg: any;
    try { msg = JSON.parse(event.data); } catch { return; }
    window.electronAPI?.pushOverlayUpdate(msg);
    switch (msg.type) {
      case "transcript":
        if (msg.is_final) addTranscript({ session_id: id!, speaker: msg.speaker || "interviewer",
          content: msg.text, confidence: msg.confidence ?? null, is_question: !!msg.is_question,
          created_at: new Date().toISOString() });
        break;
      case "question_detected":
        activeRequestRef.current = msg.request_id;
        useStore.setState({ currentSuggestion: "", currentProvider: "" });
        setAiStatus("thinking");
        break;
      case "ai_suggestion":
        if (msg.request_id !== activeRequestRef.current) break;
        setAiStatus("idle");
        appendSuggestionToken(msg.token, msg.provider);
        break;
      case "ai_complete":
        if (msg.request_id !== activeRequestRef.current) break;
        useStore.setState({ currentSuggestion: msg.full_text, currentProvider: msg.provider });
        finalizeSuggestion();
        activeRequestRef.current = null;
        setAiStatus("idle");
        break;
      case "session_ended":
        endAckRef.current?.();
        break;
      case "error":
        setAiStatus("idle");
        useStore.setState({ currentSuggestion: "" });
        toast.error(msg.message || "Could not process audio");
        break;
    }
  }, [id, addTranscript, appendSuggestionToken, finalizeSuggestion]);

  useEffect(() => {
    mountedRef.current = true;
    let disposed = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;
    let lastMessage = Date.now();
    if (useStore.getState().session?.id !== id) {
      useStore.setState({ transcripts: [], aiSuggestions: [], currentSuggestion: "" });
    }
    window.electronAPI?.pushOverlayUpdate({ type: "reset" });
    const connect = () => {
      if (disposed || !id) return;
      const token = useStore.getState().accessToken;
      if (!token) { setConnectionStatus("Sign in to reconnect"); return; }
      setConnectionStatus(attempts ? "reconnecting" : "connecting");
      authenticatedRef.current = false;
      const ws = createSessionWebSocket(id) as TaggedWebSocket;
      wsRef.current = ws;
      ws.onopen = () => {
        lastMessage = Date.now();
        ws.send(JSON.stringify({ type: "authenticate", token }));
      };
      ws.onmessage = (event) => {
        if (disposed || ws !== wsRef.current) return;
        lastMessage = Date.now();
        let msg: any;
        try { msg = JSON.parse(event.data); } catch { return; }
        if (msg.type === "connected") {
          authenticatedRef.current = true;
          attempts = 0;
          setConnectionStatus("connected");
          ws.send(JSON.stringify({ type: "capture_config", source: captureSourceRef.current }));
          for (const pcm of pendingAudioRef.current) ws.send(JSON.stringify({ type: "audio_chunk", data: int16ToBase64(pcm) }));
          pendingAudioRef.current = [];
          pendingSamplesRef.current = 0;
        }
        handleWsMessage(event);
      };
      ws.onclose = async (event) => {
        authenticatedRef.current = false;
        if (disposed || ws.intentionalClose || event.code === 1000) return;
        toast.error("Connection lost. Please repeat any unfinished question after reconnecting.");
        setConnectionStatus("reconnecting");
        setAiStatus("idle");
        activeRequestRef.current = null;
        useStore.setState({ currentSuggestion: "" });
        window.electronAPI?.pushOverlayUpdate({ type: "connection", value: "reconnecting" });
        if (event.code === 4003) {
          setConnectionStatus("Session unavailable ? start a new session");
          return;
        }
        if (++attempts > 5) {
          setConnectionStatus("Disconnected ? reopen this session to retry");
          toast.error("Connection lost. Listening cannot reach the server.");
          return;
        }
        if (event.code === 4001 || event.code === 1006) {
          try {
            const refreshedToken = await refreshAccessToken();
            useStore.getState().setAccessToken(refreshedToken);
          } catch {
            if (event.code === 4001) { setConnectionStatus("Sign in to reconnect"); return; }
          }
        }
        if (!disposed) timer = setTimeout(connect, Math.min(1000 * 2 ** (attempts - 1), 10000));
      };
    };
    connect();
    heartbeat = setInterval(() => {
      if (endingRef.current) return;
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        if (Date.now() - lastMessage > 35000) ws.close();
        else ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 10000);
    apiClient.get(`/sessions/${id}`).then(({ data }) => {
      if (!disposed) useStore.setState({ session: data, sessionStatus: data.status === "active" ? "active" : "ended" });
    }).catch(() => { if (!disposed) toast.error("Could not load session"); });
    return () => {
      disposed = true;
      mountedRef.current = false;
      clearTimeout(timer);
      clearInterval(heartbeat);
      const ws = wsRef.current;
      if (ws) { ws.intentionalClose = true; ws.close(); }
    };
  }, [id, handleWsMessage]);

  const stopCapture = useCallback(() => {
    pcmRef.current?.stop();
    pcmRef.current = null;
    streamsRef.current.forEach((s) => s.getTracks().forEach((t) => t.stop()));
    streamsRef.current = [];
    pendingAudioRef.current = [];
    pendingSamplesRef.current = 0;
    setCapturing(false);
    setAudioLevel(0);
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio_pause" }));
    window.electronAPI?.pushOverlayUpdate({ type: "capturing", value: false });
  }, [setCapturing, setAudioLevel]);

  const startCapture = useCallback(async () => {
    if (captureStartingRef.current || pcmRef.current) return;
    if (wsRef.current?.readyState !== WebSocket.OPEN) { toast.error("Wait for the server connection"); return; }
    captureStartingRef.current = true;
    setStarting(true);
    const streams: MediaStream[] = [];
    try {
      const { micEnabled, captureSystemAudio } = useStore.getState();
      if (!micEnabled && !captureSystemAudio) throw new Error("Enable meeting audio or your microphone in Settings.");
      if (captureSystemAudio) {
        if (!window.electronAPI || window.electronAPI.platform !== "win32") {
          throw new Error("Meeting audio requires the Windows desktop app. For browser practice, disable system audio and enable microphone in Settings.");
        }
        const sourceId = await window.electronAPI.getDesktopAudioSourceId();
        if (!sourceId) throw new Error("No desktop audio source found. Check your playback device and retry.");
        const system = await navigator.mediaDevices.getUserMedia({
          audio: {
            // @ts-expect-error Electron desktop loopback constraints
            mandatory: { chromeMediaSource: "desktop" },
          },
          video: {
            // @ts-expect-error Electron requires a desktop video source for loopback
            mandatory: { chromeMediaSource: "desktop", chromeMediaSourceId: sourceId },
          },
        });
        streams.push(system);
        system.getVideoTracks().forEach((t) => t.stop());
        if (!system.getAudioTracks().some((t) => t.readyState === "live")) {
          throw new Error("Meeting audio is unavailable. Check the output device and retry.");
        }
      }
      if (micEnabled) streams.push(await navigator.mediaDevices.getUserMedia({ audio: true }));
      if (!mountedRef.current) { streams.forEach((s) => s.getTracks().forEach((t) => t.stop())); return; }
      await window.electronAPI?.openOverlay();
      if (!mountedRef.current || wsRef.current?.readyState !== WebSocket.OPEN) throw new Error("Connection changed. Please retry listening.");
      captureSourceRef.current = captureSystemAudio && !micEnabled ? "system" : "mixed";
      setSourceLabel(captureSourceRef.current === "system" ? "Meeting audio only ? microphone off" : captureSystemAudio ? "Meeting audio + microphone" : "Microphone only");
      wsRef.current.send(JSON.stringify({ type: "capture_config", source: captureSourceRef.current }));
      streamsRef.current = streams;
      for (const stream of streams) for (const track of stream.getAudioTracks()) {
        track.addEventListener("ended", () => { stopCapture(); toast.error("Audio device disconnected. Check your device and restart listening."); }, { once: true });
      }
      let warned = false;
      pcmRef.current = new PcmStreamer(streams, (pcm) => {
        const ws = wsRef.current;
        if (authenticatedRef.current && ws?.readyState === WebSocket.OPEN && ws.bufferedAmount < 256000) {
          for (const pending of pendingAudioRef.current) {
            ws.send(JSON.stringify({ type: "audio_chunk", data: int16ToBase64(pending) }));
          }
          pendingAudioRef.current = [];
          pendingSamplesRef.current = 0;
          ws.send(JSON.stringify({ type: "audio_chunk", data: int16ToBase64(pcm) }));
        } else {
          pendingAudioRef.current.push(pcm.slice());
          pendingSamplesRef.current += pcm.length;
          while (pendingSamplesRef.current > 80000) {
            pendingSamplesRef.current -= pendingAudioRef.current.shift()!.length;
            if (!warned) { toast.error("Connection is slow. Some audio was missed; please repeat the question after reconnecting."); warned = true; }
          }
        }
      }, setAudioLevel);
      await pcmRef.current.resume();
      setCapturing(true);
      window.electronAPI?.pushOverlayUpdate({ type: "capturing", value: true });
    } catch (error) {
      streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
      stopCapture();
      toast.error(error instanceof Error ? error.message : "Could not start audio capture");
    } finally {
      captureStartingRef.current = false;
      if (mountedRef.current) setStarting(false);
    }
  }, [setCapturing, setAudioLevel, stopCapture]);

  useEffect(() => () => { stopCapture(); window.electronAPI?.closeOverlay(); }, [stopCapture]);

  const handleEndSession = async () => {
    if (ending) return;
    setEnding(true);
    endingRef.current = true;
    stopCapture();
    try {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(() => { endAckRef.current = null; reject(new Error("Pending processing did not finish. Please retry ending the session.")); }, 60000);
          endAckRef.current = () => { clearTimeout(timer); endAckRef.current = null; resolve(); };
          ws.send(JSON.stringify({ type: "session_end" }));
        });
      } else {
        await apiClient.post(`/sessions/${id}/end`);
      }
      useStore.setState({ sessionStatus: "ended" });
      await apiClient.post(`/feedback/sessions/${id}/feedback/generate`);
      await window.electronAPI?.closeOverlay();
      navigate(`/feedback/${id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not finish session. Please retry.");
    } finally { endingRef.current = false; setEnding(false); }
  };

  const latestSuggestion = currentSuggestion || aiSuggestions[aiSuggestions.length - 1]?.text;

  return (
    <div className="flex h-screen">
      {/* ── Left: Transcript Feed ─────────────────────────── */}
      <div className="flex-1 flex flex-col border-r border-border">
        {/* Session Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface">
          <div>
            <p className="text-sm font-medium text-primary">{session?.title || "Active Session"}</p>
            <p className="text-xs text-muted">{session?.target_role || session?.mode}</p>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                "w-2 h-2 rounded-full",
                isCapturing ? "bg-success animate-pulse-slow" : "bg-muted"
              )}
            />
            <button
              disabled={starting || ending || connectionStatus !== "connected"}
              onClick={isCapturing ? stopCapture : startCapture}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-surface-2 hover:bg-border text-primary transition-colors"
            >
              {isCapturing ? <MicOff size={12} /> : <Mic size={12} />}
              {isCapturing ? "Pause listening" : "Start listening"}
            </button>
            <button
              disabled={ending}
              onClick={handleEndSession}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-error/10 hover:bg-error/20 text-error transition-colors"
            >
              <Square size={12} /> End
            </button>
          </div>
        </div>

        <div role="status" className="px-4 py-2 text-xs text-muted">
          {connectionStatus === "connected" ? (isCapturing ? "Listening" : "Connected ? ready to listen") : connectionStatus}
          {isCapturing && ` ? ${sourceLabel}`}
          {starting && " ? Starting audio..."}
          {ending && " ? Finishing pending answers..."}
          {connectionStatus !== "connected" && isCapturing && " ? Audio buffered for up to 5 seconds"}
        </div>
        {/* Audio level bar */}
        {isCapturing && (
          <div className="h-0.5 bg-surface">
            <div
              className="h-full bg-accent transition-all duration-75"
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        )}

        {/* Transcript list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {transcripts.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Mic size={32} className="text-muted mb-3" />
              <p className="text-sm text-muted">Play meeting audio to begin transcription</p>
              <p className="text-xs text-muted/60 mt-1">AI coaching will appear when questions are detected</p>
            </div>
          )}
          {transcripts.map((t) => (
            <div
              key={t.id}
              className={clsx(
                "flex gap-2 text-sm",
                t.speaker === "user" ? "justify-start" : "justify-end"
              )}
            >
              <div
                className={clsx(
                  "max-w-[80%] px-3 py-2 rounded-lg text-sm",
                  t.speaker === "user"
                    ? "bg-surface-2 text-primary"
                    : "bg-accent/10 text-accent"
                )}
              >
                <span className="text-[10px] text-muted block mb-1 uppercase tracking-wider">
                  {t.speaker}
                  {t.is_question && " · question detected"}
                </span>
                {t.content}
              </div>
            </div>
          ))}
        </div>

        {/* Not capturing notice */}
        {!isCapturing && (
          <div className="px-4 pb-4">
            <button
              disabled={starting || ending || connectionStatus !== "connected"}
              onClick={startCapture}
              className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Mic size={16} /> Start Listening
            </button>
          </div>
        )}
      </div>

      {/* ── Right: AI Suggestion Panel ────────────────────── */}
      <div className="w-80 flex flex-col bg-surface">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-xs font-medium text-muted uppercase tracking-wider">AI Answer</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Question detected, waiting for the first token */}
          {aiStatus === "thinking" && !currentSuggestion && (
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 animate-fade-in">
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                <span className="text-[10px] text-accent uppercase tracking-wider">
                  Question detected — thinking...
                </span>
              </div>
            </div>
          )}

          {/* Current streaming suggestion */}
          {currentSuggestion && (
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 animate-fade-in">
              <div className="flex items-center gap-1 mb-2">
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                <span className="text-[10px] text-accent uppercase tracking-wider">Generating</span>
              </div>
              <p className="text-sm text-primary leading-relaxed">{currentSuggestion}</p>
            </div>
          )}

          {/* Previous suggestions */}
          {[...aiSuggestions].reverse().map((s, i) => (
            <div key={i} className="bg-surface-2 rounded-lg p-3 animate-slide-up">
              <p className="text-[10px] text-muted mb-2 uppercase tracking-wider">
                {s.provider} · {new Date(s.timestamp).toLocaleTimeString()}
              </p>
              <p className="text-sm text-primary leading-relaxed whitespace-pre-wrap">{s.text}</p>
            </div>
          ))}

          {aiSuggestions.length === 0 && !currentSuggestion && (
            <div className="flex flex-col items-center justify-center h-40 text-center">
              <p className="text-xs text-muted">AI coaching appears when an<br/>interview question is detected</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
