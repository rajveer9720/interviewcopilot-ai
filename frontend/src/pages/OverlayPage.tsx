/**
 * OverlayPage — rendered in the transparent Electron overlay window.
 * Always-on-top, excluded from screen capture.
 * Shows minimal transcript + streaming AI suggestion bubble.
 *
 * This runs in its own BrowserWindow, i.e. its own renderer process with its
 * own JS heap — the Zustand store in SessionPage's window is a different
 * instance and never reaches here. State is fed purely by relayed IPC events
 * (see SessionPage's handleWsMessage -> electronAPI.pushOverlayUpdate).
 */

import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { clsx } from "clsx";

interface Transcript {
  speaker: string;
  content: string;
}

interface Suggestion {
  text: string;
  timestamp: string;
}

export default function OverlayPage() {
  const [isCapturing, setIsCapturing] = useState(false);
  const [latestTranscript, setLatestTranscript] = useState<Transcript | null>(null);
  const [aiStatus, setAiStatus] = useState<"idle" | "thinking">("idle");
  const [currentSuggestion, setCurrentSuggestion] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [connection, setConnection] = useState("connected");
  const [error, setError] = useState("");
  const requestId = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.style.setProperty("--overlay-drag", "drag");

    const unsubscribe = window.electronAPI?.onOverlayUpdate((msg: any) => {
      switch (msg.type) {
        case "reset":
          setIsCapturing(false);
          setLatestTranscript(null);
          setSuggestions([]);
          setCurrentSuggestion("");
          setAiStatus("idle");
          setError("");
          requestId.current = null;
          break;
        case "capturing":
          setIsCapturing(!!msg.value);
          break;
        case "transcript":
          if (msg.is_final) {
            setLatestTranscript({ speaker: msg.speaker || "user", content: msg.text });
          }
          break;
        case "question_detected":
          requestId.current = msg.request_id;
          setCurrentSuggestion("");
          setError("");
          setAiStatus("thinking");
          break;
        case "ai_suggestion":
          if (msg.request_id !== requestId.current) break;
          setAiStatus("idle");
          setCurrentSuggestion((prev) => prev + msg.token);
          break;
        case "ai_complete":
          if (msg.request_id !== requestId.current) break;
          setSuggestions([{ text: msg.full_text, timestamp: new Date().toISOString() }]);
          setCurrentSuggestion("");
          setAiStatus("idle");
          break;
        case "connected":
          setConnection("connected");
          break;
        case "connection":
          setConnection(msg.value);
          setCurrentSuggestion("");
          setAiStatus("idle");
          break;
        case "error":
          setError(msg.message || "Could not process question");
          setCurrentSuggestion("");
          setAiStatus("idle");
          break;
      }
    });

    return unsubscribe;
  }, []);

  const latestSuggestion = currentSuggestion || suggestions[suggestions.length - 1]?.text;
  const showThinking = aiStatus === "thinking" && !currentSuggestion;

  return (
    <div
      className="select-none h-screen"
      style={{ WebkitAppRegion: "drag" } as any}
    >
      {/* Overlay Container */}
      <div className="fixed inset-0 p-3 flex flex-col gap-2 pointer-events-none">
        {(error || connection !== "connected") && (
          <div role="status" className="text-xs text-white bg-error/80 rounded-lg p-2">
            {error || "Connection lost — reconnecting. Some audio may be missed."}
          </div>
        )}
        {/* Session indicator */}
        <div className="flex items-center gap-2 self-end shrink-0">
          <div
            className={clsx(
              "w-1.5 h-1.5 rounded-full",
              isCapturing ? "bg-success animate-pulse" : "bg-muted"
            )}
          />
          <Mic size={12} className="text-muted" />
        </div>

        {/* Latest transcript */}
        {latestTranscript && (
          <div
            className="shrink-0 bg-[rgba(15,15,24,0.55)] border border-[rgba(255,255,255,0.08)] backdrop-blur-md rounded-lg px-3 py-2 pointer-events-auto"
            style={{ WebkitAppRegion: "no-drag" } as any}
          >
            <p className="text-[10px] text-muted mb-0.5 uppercase tracking-wider">
              {latestTranscript.speaker}
            </p>
            <p className="text-xs text-primary leading-snug line-clamp-2">
              {latestTranscript.content}
            </p>
          </div>
        )}

        {/* Question detected, waiting for the first token */}
        {showThinking && (
          <div
            className="shrink-0 bg-[rgba(108,99,255,0.18)] border border-[rgba(108,99,255,0.35)] backdrop-blur-md rounded-lg px-3 py-2 pointer-events-auto animate-fade-in"
            style={{ WebkitAppRegion: "no-drag" } as any}
          >
            <div className="flex items-center gap-1">
              <div className="w-1 h-1 rounded-full bg-accent animate-pulse" />
              <p className="text-[10px] text-accent uppercase tracking-wider">Thinking...</p>
            </div>
          </div>
        )}

        {/* AI Coaching Bubble — grows to fill the rest of the (now bigger,
            resizable) overlay window and scrolls internally so long answers
            are never cut off. Background stays translucent/blurred (glass
            look, easy to miss on a shared screen) while the text itself is
            solid and high-contrast so it stays easy to read. */}
        {latestSuggestion && (
          <div
            className="flex-1 min-h-0 flex flex-col bg-[rgba(20,18,38,0.55)] border border-[rgba(108,99,255,0.35)] backdrop-blur-md rounded-lg px-3 py-2.5 pointer-events-auto animate-fade-in"
            style={{ WebkitAppRegion: "no-drag" } as any}
          >
            <div className="flex items-center gap-1 mb-1.5 shrink-0">
              {currentSuggestion && (
                <div className="w-1 h-1 rounded-full bg-accent animate-pulse" />
              )}
              <p className="text-[10px] text-accent uppercase tracking-wider">
                {currentSuggestion ? "AI Coaching..." : "AI Coaching"}
              </p>
            </div>
            <p className="flex-1 min-h-0 overflow-y-auto text-sm text-white leading-relaxed whitespace-pre-wrap">
              {latestSuggestion}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
