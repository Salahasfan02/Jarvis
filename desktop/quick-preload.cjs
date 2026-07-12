// Exposes a hide() helper to the quick window so Escape can dismiss it.
const { ipcRenderer } = require("electron");
window.addEventListener("DOMContentLoaded", () => {
  window.jarvisHide = () => ipcRenderer.send("quick-hide");
});
