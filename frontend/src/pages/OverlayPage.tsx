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

import { useEffect, useState } from "react";
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
  const [currentSuggestion, setCurrentSuggestion] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  useEffect(() => {
    document.documentElement.style.setProperty("--overlay-drag", "drag");

    const unsubscribe = window.electronAPI?.onOverlayUpdate((msg: any) => {
      switch (msg.type) {
        case "capturing":
          setIsCapturing(!!msg.value);
          break;
        case "transcript":
          if (msg.is_final) {
            setLatestTranscript({ speaker: msg.speaker || "user", content: msg.text });
          }
          break;
        case "ai_suggestion":
          setCurrentSuggestion((prev) => prev + msg.token);
          break;
        case "ai_complete":
          setCurrentSuggestion((prev) => {
            if (prev) {
              setSuggestions((s) => [...s, { text: prev, timestamp: new Date().toISOString() }]);
            }
            return "";
          });
          break;
      }
    });

    return unsubscribe;
  }, []);

  const latestSuggestion = currentSuggestion || suggestions[suggestions.length - 1]?.text;

  return (
    <div
      className="select-none"
      style={{ WebkitAppRegion: "drag" } as any}
    >
      {/* Overlay Container */}
      <div className="fixed inset-0 p-3 flex flex-col gap-2 pointer-events-none">
        {/* Session indicator */}
        <div className="flex items-center gap-2 self-end">
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
            className="bg-[rgba(20,20,32,0.92)] border border-[#2D2D3D] backdrop-blur rounded-lg px-3 py-2 pointer-events-auto"
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

        {/* AI Coaching Bubble */}
        {latestSuggestion && (
          <div
            className="bg-[rgba(108,99,255,0.12)] border border-[rgba(108,99,255,0.3)] backdrop-blur rounded-lg px-3 py-2 pointer-events-auto animate-fade-in"
            style={{ WebkitAppRegion: "no-drag" } as any}
          >
            <div className="flex items-center gap-1 mb-1">
              {currentSuggestion && (
                <div className="w-1 h-1 rounded-full bg-accent animate-pulse" />
              )}
              <p className="text-[10px] text-accent uppercase tracking-wider">
                {currentSuggestion ? "AI Coaching..." : "AI Coaching"}
              </p>
            </div>
            <p className="text-xs text-primary/90 leading-snug">
              {latestSuggestion.slice(0, 200)}
              {latestSuggestion.length > 200 && "..."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
