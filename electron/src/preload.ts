import { contextBridge, ipcRenderer } from "electron";

// ─── Type-safe API surface exposed to renderer ────────────────────────────────
export interface ElectronAPI {
  // Platform (main window is frameless on Windows — renderer needs to know
  // whether to draw its own title bar / window controls)
  platform: NodeJS.Platform;

  // Auth
  setToken(token: string): Promise<void>;
  getToken(): Promise<string>;

  // System audio (loopback) — used with getUserMedia's chromeMediaSource
  // desktop-capture constraints; no native module required.
  getDesktopAudioSourceId(): Promise<string | null>;

  // Window controls (only meaningful when the window is frameless)
  minimizeWindow(): void;
  toggleMaximizeWindow(): void;
  closeWindow(): void;

  // Overlay
  openOverlay(): Promise<void>;
  closeOverlay(): Promise<void>;
  toggleOverlay(): Promise<void>;
  pushOverlayUpdate(data: unknown): void;
  onOverlayUpdate(cb: (data: any) => void): () => void;

  // Meeting detection
  onMeetingDetected(cb: (info: { detected: boolean; apps: string[] }) => void): () => void;

  // Config
  getApiUrl(): Promise<string>;
  setApiUrl(url: string): Promise<void>;

  // App
  getVersion(): Promise<string>;
}

// Helper to create a listener that returns an unsubscribe function
function createListener(channel: string, cb: (...args: any[]) => void) {
  const handler = (_event: Electron.IpcRendererEvent, ...args: any[]) =>
    cb(...args);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
}

const api: ElectronAPI = {
  platform: process.platform,

  // Auth
  setToken: (token) => ipcRenderer.invoke("auth:set-token", token),
  getToken: () => ipcRenderer.invoke("auth:get-token"),

  // System audio
  getDesktopAudioSourceId: () => ipcRenderer.invoke("desktop:get-audio-source-id"),

  // Window controls
  minimizeWindow: () => ipcRenderer.send("window:minimize"),
  toggleMaximizeWindow: () => ipcRenderer.send("window:toggle-maximize"),
  closeWindow: () => ipcRenderer.send("window:close"),

  // Overlay
  openOverlay: () => ipcRenderer.invoke("overlay:open"),
  closeOverlay: () => ipcRenderer.invoke("overlay:close"),
  toggleOverlay: () => ipcRenderer.invoke("overlay:toggle"),
  pushOverlayUpdate: (data) => ipcRenderer.send("overlay:push", data),
  onOverlayUpdate: (cb) => createListener("overlay:push", cb),

  // Meeting detection
  onMeetingDetected: (cb) => createListener("meeting:detected", cb),

  // Config
  getApiUrl: () => ipcRenderer.invoke("config:get-api-url"),
  setApiUrl: (url) => ipcRenderer.invoke("config:set-api-url", url),

  // App
  getVersion: () => ipcRenderer.invoke("app:version"),
};

contextBridge.exposeInMainWorld("electronAPI", api);
