// Bridges the quick window to Electron main: dismiss on Escape, and capture the
// screen with the Jarvis panel hidden (so 👁 reads the app behind it, not us).
const { ipcRenderer } = require("electron");
window.addEventListener("DOMContentLoaded", () => {
  window.jarvisHide = () => ipcRenderer.send("quick-hide");
  // returns the OCR'd text of the screen with the panel momentarily hidden
  window.jarvisCaptureScreen = () => ipcRenderer.invoke("quick-capture-screen");
});
