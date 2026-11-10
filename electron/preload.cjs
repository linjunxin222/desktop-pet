const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopPet", {
  close: () => ipcRenderer.send("desktop-pet:close"),
});
