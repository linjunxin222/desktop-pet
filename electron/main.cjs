const path = require("node:path");
const { spawn } = require("node:child_process");
const { app, BrowserWindow, Menu, screen, dialog } = require("electron");
const idleLayout = require("../assets/idle-layout.json");

let petWindow;

function openChatWindow() {
  const chatDir = path.join(app.getPath("documents"), "绘梨衣对话");
  const chatExe = path.join(chatDir, "runtime", "electron", "electron.exe");
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  try {
    const child = spawn(chatExe, [chatDir], {
      detached: true,
      stdio: "ignore",
      env,
      windowsHide: true,
    });
    child.on("error", () => {
      dialog.showErrorBox(
        "打不开绘梨衣对话",
        "找不到对话窗口程序，请确认这个目录还在：\n" + chatDir,
      );
    });
    child.unref();
  } catch (error) {
    dialog.showErrorBox(
      "打不开绘梨衣对话",
      String(error && error.message ? error.message : error),
    );
  }
}

function createPetWindow() {
  const { workArea } = screen.getPrimaryDisplay();
  const width = idleLayout.windowWidth;
  const height = idleLayout.windowHeight;

  petWindow = new BrowserWindow({
    width,
    height,
    x: Math.max(workArea.x, workArea.x + workArea.width - width - 24),
    y: Math.max(workArea.y, workArea.y + workArea.height - height - 24),
    frame: false,
    thickFrame: false,
    transparent: true,
    backgroundColor: "#00000000",
    hasShadow: false,
    alwaysOnTop: true,
    resizable: false,
    minWidth: 1,
    minHeight: 1,
    movable: true,
    maximizable: false,
    minimizable: false,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
    },
  });

  const applyWindowShape = () => {
    if (petWindow && (process.platform === "win32" || process.platform === "linux")) {
      // The union of the animation's alpha masks keeps every frame visible.
      // Points outside the character region pass through to the desktop.
      petWindow.setShape(idleLayout.shape);
    }
  };
  petWindow.on("resize", applyWindowShape);
  petWindow.on("moved", applyWindowShape);

  petWindow.setMenu(null);
  const contextMenu = Menu.buildFromTemplate([
    { label: "打开绘梨衣对话", click: openChatWindow },
    { type: "separator" },
    { label: "退出", click: () => app.quit() },
  ]);
  let menuOpen = false;
  const showContextMenu = () => {
    if (petWindow && !petWindow.isDestroyed() && !menuOpen) {
      menuOpen = true;
      contextMenu.popup({ window: petWindow, callback: () => { menuOpen = false; } });
    }
  };

  // Windows treats the character's native drag region as a title bar.
  petWindow.on("system-context-menu", (event) => {
    event.preventDefault();
    showContextMenu();
  });
  petWindow.webContents.on("context-menu", showContextMenu);

  petWindow.loadFile(path.join(__dirname, "../src/index.html"));
  petWindow.once("ready-to-show", () => {
    applyWindowShape();
    petWindow.show();
  });
  petWindow.on("closed", () => {
    petWindow = undefined;
  });
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    petWindow?.show();
    petWindow?.focus();
  });
  app.whenReady().then(createPetWindow);
}

app.on("window-all-closed", () => app.quit());

