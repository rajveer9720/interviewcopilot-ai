import { Minus, Square, X } from "lucide-react";

// The main window is frameless on Windows (see electron/src/windows/main-window.ts)
// so there are no native minimize/maximize/close buttons — draw our own.
export default function WindowTitleBar() {
  if (window.electronAPI?.platform !== "win32") return null;

  return (
    <div
      className="flex items-center justify-end h-8 bg-surface border-b border-border shrink-0"
      style={{ WebkitAppRegion: "drag" } as any}
    >
      <div className="flex items-center h-full" style={{ WebkitAppRegion: "no-drag" } as any}>
        <button
          onClick={() => window.electronAPI?.minimizeWindow()}
          className="h-full w-11 flex items-center justify-center text-muted hover:bg-surface-2 hover:text-primary transition-colors"
          aria-label="Minimize"
        >
          <Minus size={14} />
        </button>
        <button
          onClick={() => window.electronAPI?.toggleMaximizeWindow()}
          className="h-full w-11 flex items-center justify-center text-muted hover:bg-surface-2 hover:text-primary transition-colors"
          aria-label="Maximize"
        >
          <Square size={11} />
        </button>
        <button
          onClick={() => window.electronAPI?.closeWindow()}
          className="h-full w-11 flex items-center justify-center text-muted hover:bg-error hover:text-white transition-colors"
          aria-label="Close"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
