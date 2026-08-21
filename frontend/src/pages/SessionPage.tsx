import { useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useStore } from "../store";
import { apiClient, createSessionWebSocket } from "../api/client";
import { PcmStreamer, int16ToBase64 } from "../lib/pcm";
import { Square, Mic, MicOff, Pause, Play } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";

const MAX_RECONNECT_ATTEMPTS = 5;

// A close is only "intentional" if the exact socket instance that closed was
// the one we asked to close — a ref shared across reconnects/StrictMode
// remounts can't tell that apart from a real drop, since the old socket's
// close event can land after a new effect run already reset it.
type TaggedWebSocket = WebSocket & { intentionalClose?: boolean };

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    session, sessionStatus, transcripts, aiSuggestions, currentSuggestion,
    isCapturing, audioLevel,
    addTranscript, appendSuggestionToken, finalizeSuggestion, endSession,
    setCapturing, setAudioLevel,
  } = useStore();

  const wsRef = useRef<TaggedWebSocket | null>(null);
  const pcmRef = useRef<PcmStreamer | null>(null);
  const streamsRef = useRef<MediaStream[]>([]);
  const levelCtxRef = useRef<AudioContext | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isUnmountedRef = useRef(false);

  const handleWsMessage = useCallback((event: MessageEvent) => {
    const msg = JSON.parse(event.data);
    // Mirror every event to the overlay window — it runs in its own renderer
    // with its own store instance, so it can't see this component's state.
    window.electronAPI?.pushOverlayUpdate(msg);

    switch (msg.type) {
      case "transcript":
        if (msg.is_final) {
          addTranscript({
            session_id: id!,
            speaker:    msg.speaker || "user",
            content:    msg.text,
            confidence: msg.confidence ?? null,
            is_question: false,
            created_at: new Date().toISOString(),
          });
        }
        break;
      case "ai_suggestion":
        appendSuggestionToken(msg.token, msg.provider || "openai");
        break;
      case "ai_complete":
        finalizeSuggestion();
        break;
      case "error":
        toast.error(msg.message || "WebSocket error");
        break;
    }
  }, [id, addTranscript, appendSuggestionToken, finalizeSuggestion]);

  const connectWebSocket = useCallback(() => {
    const token = useStore.getState().accessToken;
    if (!id || !token) return;

    const ws = createSessionWebSocket(id, token) as TaggedWebSocket;
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
    };

    ws.onmessage = handleWsMessage;

    ws.onclose = (event) => {
      if (ws.intentionalClose || event.code === 1000) return;
      scheduleReconnect();
    };
  }, [id, handleWsMessage]);

  const scheduleReconnect = useCallback(async () => {
    if (isUnmountedRef.current) return;

    const attempt = reconnectAttemptRef.current + 1;
    if (attempt > MAX_RECONNECT_ATTEMPTS) {
      toast.error("Lost connection to the server. Please refresh the page.");
      return;
    }
    reconnectAttemptRef.current = attempt;
    toast.error(`Connection lost. Reconnecting... (${attempt}/${MAX_RECONNECT_ATTEMPTS})`);

    // The socket may have dropped because the access token expired — refresh it
    // before retrying so the reconnect doesn't just fail the same way again.
    try {
      const { data } = await apiClient.post("/auth/refresh");
      useStore.getState().setAccessToken(data.access_token);
    } catch {
      // Keep the existing token; the server will reject it again if it's the
      // real problem, which re-enters this same retry loop.
    }

    if (isUnmountedRef.current) return;

    const delay = Math.min(1000 * 2 ** (attempt - 1), 10_000);
    reconnectTimerRef.current = setTimeout(connectWebSocket, delay);
  }, [connectWebSocket]);

  // ── Connect WebSocket ──────────────────────────────────────
  useEffect(() => {
    isUnmountedRef.current = false;
    reconnectAttemptRef.current = 0;
    connectWebSocket();

    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.intentionalClose = true;
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  // ── Start Audio Capture ────────────────────────────────────
  // Sends raw 16-bit/16kHz/mono PCM over the WebSocket — the format
  // backend/transcripts/whisper_client.py expects. In Electron, system audio
  // (Zoom/Teams/Meet output) is captured too via Chromium's built-in desktop
  // loopback support, so questions asked by the interviewer get transcribed
  // and coached, not just what the user says into the mic.
  const startCapture = useCallback(async () => {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const streams = [micStream];

      const sourceId = useStore.getState().captureSystemAudio
        ? await window.electronAPI?.getDesktopAudioSourceId().catch(() => null)
        : null;
      if (sourceId) {
        try {
          const systemStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              // @ts-expect-error — non-standard Electron desktop-capture constraints
              mandatory: { chromeMediaSource: "desktop" },
            },
            video: {
              // @ts-expect-error — a (unused, discarded) video track is required
              // to unlock Chromium's desktop-capture audio path.
              mandatory: { chromeMediaSource: "desktop", chromeMediaSourceId: sourceId },
            },
          });
          systemStream.getVideoTracks().forEach((t) => t.stop());
          streams.push(systemStream);
        } catch {
          // System audio is a bonus, not a requirement — keep going with mic only.
        }
      }

      streamsRef.current = streams;

      // Audio level visualization (mic only — just a UI indicator).
      const levelCtx = new AudioContext();
      levelCtxRef.current = levelCtx;
      const source = levelCtx.createMediaStreamSource(micStream);
      const analyser = levelCtx.createAnalyser();
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        setAudioLevel(avg / 255);
        if (useStore.getState().isCapturing) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);

      pcmRef.current = new PcmStreamer(streams, (pcm16) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({ type: "audio_chunk", data: int16ToBase64(pcm16) })
          );
        }
      });

      setCapturing(true);
      window.electronAPI?.pushOverlayUpdate({ type: "capturing", value: true });
    } catch {
      toast.error("Could not access microphone.");
    }
  }, []);

  const stopCapture = useCallback(() => {
    pcmRef.current?.stop();
    pcmRef.current = null;
    streamsRef.current.forEach((s) => s.getTracks().forEach((t) => t.stop()));
    streamsRef.current = [];
    levelCtxRef.current?.close();
    levelCtxRef.current = null;
    setCapturing(false);
    setAudioLevel(0);
    window.electronAPI?.pushOverlayUpdate({ type: "capturing", value: false });
  }, []);

  // Stop mic/system-audio tracks if the user navigates away without hitting "End".
  useEffect(() => {
    return () => {
      pcmRef.current?.stop();
      streamsRef.current.forEach((s) => s.getTracks().forEach((t) => t.stop()));
      levelCtxRef.current?.close();
    };
  }, []);

  const handleEndSession = async () => {
    stopCapture();
    wsRef.current?.send(JSON.stringify({ type: "session_end" }));
    await endSession();
    navigate(`/feedback/${id}`);
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
              onClick={isCapturing ? stopCapture : startCapture}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-surface-2 hover:bg-border text-primary transition-colors"
            >
              {isCapturing ? <MicOff size={12} /> : <Mic size={12} />}
              {isCapturing ? "Mute" : "Unmute"}
            </button>
            <button
              onClick={handleEndSession}
              className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-error/10 hover:bg-error/20 text-error transition-colors"
            >
              <Square size={12} /> End
            </button>
          </div>
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
              <p className="text-sm text-muted">Start speaking to begin transcription</p>
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
              onClick={startCapture}
              className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Mic size={16} /> Start Microphone Capture
            </button>
          </div>
        )}
      </div>

      {/* ── Right: AI Suggestion Panel ────────────────────── */}
      <div className="w-80 flex flex-col bg-surface">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-xs font-medium text-muted uppercase tracking-wider">AI Coaching</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
