import { BrowserWindow, screen } from "electron";
import * as path from "path";

const isDev = process.env.NODE_ENV === "development";

let overlayWindow: BrowserWindow | null = null;

export function createOverlayWindow(): BrowserWindow {
  if (overlayWindow) {
    overlayWindow.show();
    overlayWindow.focus();
    return overlayWindow;
  }

  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;
  const width = 480;
  const height = Math.min(620, screenHeight - 48);

  overlayWindow = new BrowserWindow({
    width,
    height,
    minWidth: 340,
    minHeight: 260,
    x: screenWidth - width - 24,
    y: 24,
    frame: false,
    transparent: true,
    hasShadow: false,
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "..", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      backgroundThrottling: false,
    },
  });

  overlayWindow.setAlwaysOnTop(true, "screen-saver");
  overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  // Keep the overlay out of screen shares / recordings (Zoom, Teams, Meet, OBS).
  overlayWindow.setContentProtection(true);

  if (isDev) {
    overlayWindow.loadURL("http://localhost:5173/overlay");
  } else {
    overlayWindow.loadURL("app://interviewcopilot/index.html#/overlay");
  }

  overlayWindow.on("closed", () => {
    overlayWindow = null;
  });

  return overlayWindow;
}

export function getOverlayWindow(): BrowserWindow | null {
  return overlayWindow;
}
