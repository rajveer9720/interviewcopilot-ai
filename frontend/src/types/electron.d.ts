export interface ElectronAPI {
  platform: string;

  setToken(token: string): Promise<void>;
  getToken(): Promise<string>;

  getDesktopAudioSourceId(): Promise<string | null>;

  minimizeWindow(): void;
  toggleMaximizeWindow(): void;
  closeWindow(): void;

  openOverlay(): Promise<void>;
  closeOverlay(): Promise<void>;
  toggleOverlay(): Promise<void>;
  pushOverlayUpdate(data: unknown): void;
  onOverlayUpdate(cb: (data: any) => void): () => void;

  onMeetingDetected(cb: (info: { detected: boolean; apps: string[] }) => void): () => void;

  getApiUrl(): Promise<string>;
  setApiUrl(url: string): Promise<void>;

  getVersion(): Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
