const path = require("node:path");
const { app, BrowserWindow, ipcMain, screen } = require("electron");

let petWindow;

function createPetWindow() {
  const { workArea } = screen.getPrimaryDisplay();
  const width = 400;
  const height = 540;

  petWindow = new BrowserWindow({
    width,
    height,
    x: Math.max(workArea.x, workArea.x + workArea.width - width - 24),
    y: Math.max(workArea.y, workArea.y + workArea.height - height - 24),
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  petWindow.loadFile(path.join(__dirname, "../src/index.html"));
  petWindow.once("ready-to-show", () => petWindow.show());
  petWindow.on("closed", () => {
    petWindow = undefined;
  });
}

app.whenReady().then(createPetWindow);

ipcMain.on("desktop-pet:close", () => petWindow?.close());

app.on("window-all-closed", () => app.quit());
