import { BrowserWindow, screen } from "electron";
import * as path from "path";

const isDev = process.env.NODE_ENV === "development";

export function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: "#0A0A0F",
    titleBarStyle: "hiddenInset",
    frame: process.platform !== "win32",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  if (isDev) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(
      path.join(__dirname, "..", "..", "resources", "frontend", "index.html")
    );
  }

  // Excluded from screen capture too — session transcripts and the app name
  // would otherwise identify the tool if the user shares their entire screen
  // and briefly brings the control panel to front.
  win.setContentProtection(true);

  win.once("ready-to-show", () => win.show());

  win.on("close", (evt) => {
    // Minimise to tray instead of closing on Windows
    if (process.platform === "win32") {
      evt.preventDefault();
      win.hide();
    }
  });

  return win;
}
