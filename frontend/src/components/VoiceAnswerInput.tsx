import { useEffect, useRef, useState } from "react";
import { Mic, Square, Loader2, RotateCcw, Trash2 } from "lucide-react";
import { apiClient } from "../api/client";
import { PcmStreamer } from "../lib/pcm";

interface Props {
  sessionId: string;
  questionId: string;
  disabled: boolean;
  onTranscript: (text: string) => boolean;
  onBusyChange: (busy: boolean) => void;
}

const MAX_SAMPLES = 16000 * 120;

export default function VoiceAnswerInput({ sessionId, questionId, disabled, onTranscript, onBusyChange }: Props) {
  const [phase, setPhase] = useState<"idle" | "starting" | "recording" | "transcribing" | "retry">("idle");
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const stream = useRef<MediaStream | null>(null);
  const pcm = useRef<PcmStreamer | null>(null);
  const chunks = useRef<Int16Array[]>([]);
  const samples = useRef(0);
  const mounted = useRef(true);
  const working = useRef(false);
  const timer = useRef<ReturnType<typeof setInterval>>();
  const controller = useRef<AbortController | null>(null);
  const callbacks = useRef({ onTranscript, onBusyChange });
  callbacks.current = { onTranscript, onBusyChange };

  function release() {
    if (timer.current) clearInterval(timer.current);
    stream.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    stream.current = null;
    pcm.current?.stop(); pcm.current = null;
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; release(); controller.current?.abort();
      chunks.current = []; callbacks.current.onBusyChange(false);
    };
  }, []);

  async function transcribe() {
    if (!mounted.current) return;
    working.current = true; setPhase("transcribing"); setError("");
    callbacks.current.onBusyChange(true);
    const data = new Int16Array(samples.current);
    let offset = 0;
    for (const chunk of chunks.current) { data.set(chunk, offset); offset += chunk.length; }
    controller.current = new AbortController();
    try {
      const { data: response } = await apiClient.post(`/sessions/${sessionId}/practice/transcribe`, data.buffer, {
        params: { question_id: questionId }, headers: { "Content-Type": "application/octet-stream" },
        timeout: 90000, signal: controller.current.signal,
      });
      if (!mounted.current) return;
      if (!callbacks.current.onTranscript(response.text)) throw new Error("Transcript exceeds the answer limit. Shorten your answer and retry.");
      chunks.current = []; samples.current = 0; setPhase("idle"); setSeconds(0);
    } catch (err: any) {
      if (!mounted.current) return;
      setError(err.response?.data?.detail || err.message || "Could not transcribe. Retry this recording or type your answer.");
      setPhase("retry");
    } finally {
      working.current = false;
      if (mounted.current) callbacks.current.onBusyChange(false);
    }
  }

  function stop() {
    if (working.current || !pcm.current) return;
    release(); setLevel(0); void transcribe();
  }

  async function start() {
    if (working.current || pcm.current || disabled) return;
    working.current = true; setPhase("starting"); setError("");
    callbacks.current.onBusyChange(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone is unavailable. Use HTTPS or the desktop app, or type your answer.");
      const media = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
      if (!mounted.current) { media.getTracks().forEach((track) => track.stop()); return; }
      stream.current = media; chunks.current = []; samples.current = 0;
      media.getAudioTracks().forEach((track) => { track.onended = () => {
        release(); working.current = false; setPhase("idle"); setLevel(0);
        chunks.current = []; samples.current = 0;
        setError("Microphone disconnected. Reconnect it and record again, or type your answer.");
        callbacks.current.onBusyChange(false);
      }; });
      pcm.current = new PcmStreamer([media], (chunk) => {
        const remaining = MAX_SAMPLES - samples.current;
        const bounded = chunk.slice(0, Math.max(0, remaining));
        if (bounded.length) { chunks.current.push(bounded); samples.current += bounded.length; }
        if (samples.current >= MAX_SAMPLES) stop();
      }, (value) => { if (mounted.current) setLevel(value); });
      await pcm.current.resume();
      if (!mounted.current || !pcm.current) return;
      working.current = false; setSeconds(0); setPhase("recording");
      const started = Date.now();
      timer.current = setInterval(() => {
        setSeconds(Math.min(120, Math.floor((Date.now() - started) / 1000)));
        if (Date.now() - started >= 120000) stop();
      }, 250);
    } catch (err: any) {
      release(); working.current = false;
      if (!mounted.current) return;
      setError(err.name === "NotAllowedError" ? "Microphone permission denied. Allow access and retry, or type your answer." : err.message || "Microphone could not start.");
      setPhase("idle"); callbacks.current.onBusyChange(false);
    }
  }

  const active = phase === "starting" || phase === "transcribing";
  const control = "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-50";
  return <div className="mb-4 rounded-lg border border-border bg-bg p-4">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><p className="text-sm font-medium">Answer with your voice</p><p className="mt-1 text-xs leading-5 text-slate-400">Record up to 2 minutes per clip. Review and edit the transcript before submitting.</p></div>
      {phase === "recording" ? <button type="button" onClick={stop} className={`${control} shrink-0 border-red-400/40 text-red-300`}><Square size={16} /> Stop & transcribe</button>
        : <button type="button" disabled={disabled || active || phase === "retry"} onClick={start} className={`${control} shrink-0 text-violet-300`}>{active ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}{phase === "starting" ? "Opening mic..." : phase === "transcribing" ? "Transcribing..." : "Record answer"}</button>}
    </div>
    {phase === "recording" && <div role="status" className="mt-3 flex items-center gap-3 text-xs text-red-300"><span className="h-2 w-2 animate-pulse rounded-full bg-red-400" />Recording {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")} / 2:00<div aria-hidden="true" className="h-1.5 flex-1 overflow-hidden rounded-full bg-border"><div className="h-full bg-violet-400" style={{ width: `${level * 100}%` }} /></div></div>}
    {error && <p role="alert" className="mt-3 text-sm leading-6 text-red-300">{error}</p>}
    {phase === "retry" && <div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={disabled} onClick={() => void transcribe()} className={control}><RotateCcw size={15} /> Retry transcription</button><button type="button" disabled={disabled} onClick={() => { chunks.current = []; samples.current = 0; setPhase("idle"); setError(""); setSeconds(0); }} className={control}><Trash2 size={15} /> Discard recording</button></div>}
    {phase === "transcribing" && <p role="status" className="mt-3 text-xs text-slate-400">Converting your recording to text. Your answer will not be submitted automatically.</p>}
  </div>;
}
