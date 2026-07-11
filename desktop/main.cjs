/* Jarvis desktop shell.
 *
 * Wraps the web UI in a native macOS window with vibrancy, a menu-bar (tray)
 * icon, a global shortcut (Cmd+Shift+J) that toggles a floating assistant
 * window, and native notifications. It also launches the Python backend if
 * it isn't already running.
 *
 * Dev:  npm start          (loads http://localhost:5173 from `npm run dev`)
 * Prod: build the frontend first (npm run build in ../frontend), then package.
 */
const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const DEV_URL = "http://localhost:5173";
const PROD_INDEX = path.join(__dirname, "..", "frontend", "dist", "index.html");
const BACKEND_DIR = path.join(__dirname, "..", "backend");

let mainWindow = null;
let floatWindow = null;
let tray = null;
let backendProc = null;

const isDev = !app.isPackaged;

function checkBackend(cb) {
  http.get("http://127.0.0.1:8765/api/status", (res) => cb(res.statusCode === 200))
    .on("error", () => cb(false));
}

function startBackend() {
  checkBackend((up) => {
    if (up) return;
    const python = path.join(BACKEND_DIR, ".venv", "bin", "python");
    backendProc = spawn(python, ["run.py"], { cwd: BACKEND_DIR, stdio: "ignore" });
  });
}

function loadUI(win) {
  if (isDev) win.loadURL(DEV_URL);
  else win.loadFile(PROD_INDEX);
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 780,
    minWidth: 800,
    minHeight: 560,
    titleBarStyle: "hiddenInset",
    vibrancy: "under-window",
    visualEffectState: "active",
    backgroundColor: "#00000000",
    webPreferences: { contextIsolation: true },
  });
  loadUI(mainWindow);
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => (mainWindow = null));
}

function toggleFloatWindow() {
  if (floatWindow && !floatWindow.isDestroyed()) {
    floatWindow.isVisible() ? floatWindow.hide() : floatWindow.show();
    return;
  }
  const { screen } = require("electron");
  const display = screen.getPrimaryDisplay().workAreaSize;
  floatWindow = new BrowserWindow({
    width: 460,
    height: 640,
    x: display.width - 480,
    y: 40,
    frame: false,
    alwaysOnTop: true,
    vibrancy: "hud",
    visualEffectState: "active",
    backgroundColor: "#00000000",
    resizable: true,
    skipTaskbar: true,
    webPreferences: { contextIsolation: true },
  });
  loadUI(floatWindow);
}

function createTray() {
  const icon = nativeImage.createFromDataURL(
    // 16x16 template circle
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAoUlEQVQ4je2SsQ3CMBBFn5NIFBQMwAY0DMAGMAIjMAIbwAZkAxggFRUFEgW5FDaKHTvBSkfBl67x+X/dP58BwzAK1lqcc78ZSCkBWGvRWv9uUJYlIQTGGKy1eXVKKUopKKUwxswzSCkRQmCM+bpBRJimKZ9BCIExhpQSAGvtvIH3HhFBRJhSAmCM+d5ARJhSAsA5N88ghADnHM45Sqm/3+AF6BpTC/HPBDkAAAAASUVORK5CYII="
  );
  icon.setTemplateImage(true);
  tray = new Tray(icon);
  tray.setToolTip("Jarvis");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open Jarvis", click: () => (mainWindow ? mainWindow.show() : createMainWindow()) },
    { label: "Floating assistant  ⌘⇧J", click: toggleFloatWindow },
    { type: "separator" },
    { label: "Quit", click: () => app.quit() },
  ]));
}

app.whenReady().then(() => {
  startBackend();
  createMainWindow();
  createTray();
  globalShortcut.register("CommandOrControl+Shift+J", toggleFloatWindow);
});

app.on("window-all-closed", () => {
  /* keep running in the tray, JARVIS-style */
});

app.on("activate", () => {
  if (!mainWindow) createMainWindow();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  if (backendProc) backendProc.kill();
});
