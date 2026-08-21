import {
  app,
  BrowserWindow,
  ipcMain,
  desktopCapturer,
  nativeTheme,
  Tray,
  Menu,
  nativeImage,
} from "electron";
import * as path from "path";
import Store from "electron-store";
import { createMainWindow } from "./windows/main-window";
import { createOverlayWindow, getOverlayWindow } from "./windows/overlay-window";
import { exec } from "child_process";

// ─── App state ────────────────────────────────────────────────────────────────
const store = new Store<{ apiUrl: string; accessToken: string }>({
  defaults: { apiUrl: "http://localhost:8000", accessToken: "" },
});

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let meetingDetectionInterval: NodeJS.Timeout | null = null;

// ─── Single instance lock ─────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ─── App ready ────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  nativeTheme.themeSource = "dark";

  mainWindow = createMainWindow();
  setupTray();
  registerIpcHandlers();
  startMeetingDetection();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    stopMeetingDetection();
    app.quit();
  }
});

app.on("before-quit", () => {
  meetingDetectionInterval && clearInterval(meetingDetectionInterval);
});

// ─── System tray ─────────────────────────────────────────────────────────────
function setupTray() {
  const icon = nativeImage.createFromPath(
    path.join(__dirname, "..", "assets", "tray-icon.png")
  );
  tray = new Tray(icon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Open InterviewCopilot AI",
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      },
    },
    { type: "separator" },
    {
      label: "Toggle Overlay",
      click: () => {
        const overlay = getOverlayWindow();
        overlay ? overlay.close() : createOverlayWindow();
      },
    },
    { type: "separator" },
    { label: "Quit", click: () => app.quit() },
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip("InterviewCopilot AI");
  tray.on("click", () => {
    mainWindow?.show();
    mainWindow?.focus();
  });
}

// ─── IPC handlers ─────────────────────────────────────────────────────────────
function registerIpcHandlers() {
  // -- Auth token handoff --
  ipcMain.handle("auth:set-token", (_evt, token: string) => {
    store.set("accessToken", token);
  });

  ipcMain.handle("auth:get-token", () => store.get("accessToken"));

  // -- System audio (loopback) source for getUserMedia's desktop-capture path --
  // No native module needed: Chromium's own desktop-capture support handles
  // WASAPI loopback under the hood once the renderer has a source id.
  ipcMain.handle("desktop:get-audio-source-id", async () => {
    const sources = await desktopCapturer.getSources({ types: ["screen"] });
    return sources[0]?.id ?? null;
  });

  // -- Overlay window --
  ipcMain.handle("overlay:open", () => {
    createOverlayWindow();
  });

  ipcMain.handle("overlay:close", () => {
    getOverlayWindow()?.close();
  });

  ipcMain.handle("overlay:toggle", () => {
    const overlay = getOverlayWindow();
    if (overlay) {
      overlay.close();
    } else {
      createOverlayWindow();
    }
  });

  // -- Overlay relay: main window -> main process -> overlay window --
  ipcMain.on("overlay:push", (_evt, payload) => {
    getOverlayWindow()?.webContents.send("overlay:push", payload);
  });

  // -- Window controls (main window is frameless on Windows — see
  // windows/main-window.ts — so the renderer needs a way to drive these) --
  ipcMain.on("window:minimize", () => mainWindow?.minimize());
  ipcMain.on("window:toggle-maximize", () => {
    if (!mainWindow) return;
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
  });
  ipcMain.on("window:close", () => mainWindow?.close());

  // -- App config --
  ipcMain.handle("config:get-api-url", () => store.get("apiUrl"));
  ipcMain.handle("config:set-api-url", (_evt, url: string) => {
    store.set("apiUrl", url);
  });

  // -- Version --
  ipcMain.handle("app:version", () => app.getVersion());
}

// ─── Meeting app detection ────────────────────────────────────────────────────
const MEETING_PROCESSES = [
  "Zoom.exe",
  "Teams.exe",
  "chrome.exe",
  "msedge.exe",
  "slack.exe",
];

function startMeetingDetection() {
  meetingDetectionInterval = setInterval(() => {
    if (process.platform !== "win32") return;

    exec("tasklist /FO CSV /NH", (err, stdout) => {
      if (err) return;

      const running = MEETING_PROCESSES.filter((p) =>
        stdout.toLowerCase().includes(p.toLowerCase())
      );

      mainWindow?.webContents.send("meeting:detected", {
        detected: running.length > 0,
        apps: running,
      });
    });
  }, 5_000);
}

function stopMeetingDetection() {
  if (meetingDetectionInterval) {
    clearInterval(meetingDetectionInterval);
    meetingDetectionInterval = null;
  }
}
