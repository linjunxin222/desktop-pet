const { contextBridge, ipcRenderer } = require("electron");

/**
 * The renderer never sees ipcRenderer itself: every capability is an explicit
 * method here, and the main process validates the sender on the other side.
 * See docs/CONTRACTS.md for the channel list.
 */
contextBridge.exposeInMainWorld("desktopPet", {
  close: () => ipcRenderer.send("pet:close"),
  getState: () => ipcRenderer.invoke("pet:get-state"),
  saveState: (patch) => ipcRenderer.invoke("pet:save-state", patch),
  setView: (view) => ipcRenderer.invoke("pet:set-view", view),
  reportHitRegions: (regions) => ipcRenderer.send("pet:hit-regions", regions),
  onGoDesktop: (handler) => {
    const listener = () => handler();
    ipcRenderer.on("pet:go-desktop", listener);
    return () => ipcRenderer.removeListener("pet:go-desktop", listener);
  },
});
