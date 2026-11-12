// 启动探针：同时往三个地方写，任何一处能写就留下现场
const probeFs = require("node:fs");
const probePath = require("node:path");
const probeOs = require("node:os");

const probeTargets = [
  probePath.join(__dirname, "..", "logs", "boot.log"),
  probePath.join(probeOs.tmpdir(), "xiaoyu-boot.log"),
  probePath.join(process.env.APPDATA || probeOs.homedir(), "desktop-pet", "boot.log"),
];

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  for (const target of probeTargets) {
    try {
      probeFs.mkdirSync(probePath.dirname(target), { recursive: true });
      probeFs.appendFileSync(target, line);
    } catch {
      // 换下一个位置
    }
  }
}

log(`boot | electron=${process.versions.electron} | argv=${process.argv.slice(1).join(" ")} | __dirname=${__dirname}`);
log(`paths | userData=${process.env.APPDATA || "?"} | argv0=${process.argv[0]}`);
process.on("uncaughtException", (error) => log(`uncaughtException: ${error && error.stack}`));
process.on("unhandledRejection", (reason) => log(`unhandledRejection: ${reason && reason.stack ? reason.stack : reason}`));

const path = require("node:path");
const fs = require("node:fs");
const {
  app,
  BrowserWindow,
  Menu,
  Tray,
  nativeImage,
  ipcMain,
  screen,
  globalShortcut,
} = require("electron");

const HIT_PADDING = 2;
const HIT_POLL_MS = 80;
const SAVE_DEBOUNCE_MS = 400;
const TOGGLE_ACCELERATOR = "CommandOrControl+Alt+P";

let petWindow = null;
let tray = null;
let saveTimer = null;
let hitTimer = null;
let hitRegions = [];
let pointerInside = null;
let isQuitting = false;

function createDefaultState() {
  return {
    version: 1,
    window: { view: "pet" },
    pet: { x: null, y: null, replyIndex: 0, visits: 0 },
  };
}

let state = createDefaultState();

function stateFile() {
  return path.join(app.getPath("userData"), "pet-state.json");
}

function clampToWorkArea(x, y, width, height) {
  const display = screen.getDisplayNearestPoint({ x: Math.round(x), y: Math.round(y) });
  const area = display.workArea;
  const maxX = area.x + area.width - width;
  const maxY = area.y + area.height - height;
  return {
    x: Math.round(Math.min(Math.max(x, area.x), Math.max(area.x, maxX))),
    y: Math.round(Math.min(Math.max(y, area.y), Math.max(area.y, maxY))),
  };
}

function loadState() {
  const defaults = createDefaultState();
  try {
    const raw = JSON.parse(fs.readFileSync(stateFile(), "utf8"));
    const windowState = raw && typeof raw.window === "object" ? raw.window : {};
    const petState = raw && typeof raw.pet === "object" ? raw.pet : {};
    state = {
      ...defaults,
      ...raw,
      window: {
        ...defaults.window,
        ...windowState,
        x: Number.isFinite(windowState.x) ? windowState.x : null,
        y: Number.isFinite(windowState.y) ? windowState.y : null,
        view: windowState.view === "house" ? "house" : "pet",
      },
      pet: {
        ...defaults.pet,
        ...petState,
        replyIndex: Number.isFinite(petState.replyIndex) ? petState.replyIndex : 0,
        visits: Number.isFinite(petState.visits) ? petState.visits : 0,
      },
    };
  } catch {
    state = defaults;
  }
}

function writeState() {
  try {
    fs.mkdirSync(path.dirname(stateFile()), { recursive: true });
    fs.writeFileSync(stateFile(), `${JSON.stringify(state, null, 2)}\n`, "utf8");
  } catch (error) {
    console.error("[pet] failed to persist state", error);
  }
}

function saveStateSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(writeState, SAVE_DEBOUNCE_MS);
}

function rememberBounds() {
  if (!petWindow || petWindow.isDestroyed()) return;
  const bounds = petWindow.getBounds();
  state.window.x = bounds.x;
  state.window.y = bounds.y;
  saveStateSoon();
}

function initialBounds() {
  const { workArea } = screen.getPrimaryDisplay();
  return { x: workArea.x, y: workArea.y, width: workArea.width, height: workArea.height };
}

function showPet() {
  if (!petWindow || petWindow.isDestroyed()) return;
  if (petWindow.isMinimized()) petWindow.restore();
  petWindow.show();
  petWindow.focus();
}

function hidePet() {
  if (!petWindow || petWindow.isDestroyed()) return;
  petWindow.hide();
}

function togglePet() {
  if (!petWindow || petWindow.isDestroyed()) return;
  if (petWindow.isVisible() && !petWindow.isMinimized()) hidePet();
  else showPet();
}

function buildTray() {
  const iconPath = path.join(__dirname, "../assets/tray.png");
  let image = nativeImage.createFromPath(iconPath);
  if (image.isEmpty()) image = nativeImage.createEmpty();

  tray = new Tray(image);
  tray.setToolTip("小鱼 · 桌面伙伴");

  const menu = Menu.buildFromTemplate([
    { label: "显示 / 收起", click: () => togglePet() },
    {
      label: "开机自启",
      type: "checkbox",
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => {
        app.setLoginItemSettings({ openAtLogin: item.checked, openAsHidden: true });
      },
    },
    { type: "separator" },
    {
      label: "退出",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);
  tray.on("click", () => togglePet());
}

function evaluatePointer() {
  if (!petWindow || petWindow.isDestroyed() || !petWindow.isVisible()) return;
  const point = screen.getCursorScreenPoint();
  const bounds = petWindow.getBounds();
  const inside = hitRegions.some(
    (region) =>
      point.x >= bounds.x + region.x - HIT_PADDING &&
      point.x <= bounds.x + region.x + region.w + HIT_PADDING &&
      point.y >= bounds.y + region.y - HIT_PADDING &&
      point.y <= bounds.y + region.y + region.h + HIT_PADDING,
  );
  if (inside === pointerInside) return;
  pointerInside = inside;
  petWindow.setIgnoreMouseEvents(!inside, { forward: true });
}

function startHitTracking() {
  stopHitTracking();
  hitTimer = setInterval(evaluatePointer, HIT_POLL_MS);
}

function stopHitTracking() {
  if (hitTimer) clearInterval(hitTimer);
  hitTimer = null;
}

function createPetWindow() {
  const bounds = initialBounds();
  petWindow = new BrowserWindow({
    ...bounds,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
    },
  });

  petWindow.setAlwaysOnTop(true, "floating");
  petWindow.setIgnoreMouseEvents(true, { forward: true });
  petWindow.loadFile(path.join(__dirname, "../src/index.html"));

  petWindow.once("ready-to-show", () => {
    log("ready-to-show");
    petWindow.showInactive();
    startHitTracking();
  });
  petWindow.webContents.on("render-process-gone", (_event, details) => {
    log(`render-process-gone: ${JSON.stringify(details)}`);
  });
  petWindow.webContents.on("did-fail-load", (_event, code, description) => {
    log(`did-fail-load: ${code} ${description}`);
  });

  petWindow.on("hide", () => {
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.setIgnoreMouseEvents(true, { forward: true });
    }
    pointerInside = null;
  });

  petWindow.on("show", () => {
    pointerInside = null;
    evaluatePointer();
  });

  petWindow.on("close", (event) => {
    if (isQuitting) return;
    event.preventDefault();
    hidePet();
  });
}

function registerShortcuts() {
  globalShortcut.register(TOGGLE_ACCELERATOR, () => togglePet());
}

function registerIpc() {
  const fromPet = (event) =>
    Boolean(petWindow) && !petWindow.isDestroyed() && event.sender === petWindow.webContents;

  ipcMain.on("pet:close", (event) => {
    if (fromPet(event)) hidePet();
  });

  ipcMain.on("pet:hit-regions", (event, regions) => {
    if (!fromPet(event) || !Array.isArray(regions)) return;
    hitRegions = regions
      .slice(0, 64)
      .filter(
        (region) =>
          region &&
          Number.isFinite(region.x) &&
          Number.isFinite(region.y) &&
          Number.isFinite(region.w) &&
          Number.isFinite(region.h),
      )
      .map((region) => ({
        x: Math.round(region.x),
        y: Math.round(region.y),
        w: Math.max(0, Math.round(region.w)),
        h: Math.max(0, Math.round(region.h)),
      }));
    evaluatePointer();
  });

  ipcMain.handle("pet:get-state", (event) => {
    if (!fromPet(event)) return null;
    return { window: { ...state.window }, pet: { ...state.pet } };
  });

  ipcMain.handle("pet:save-state", (event, patch) => {
    if (!fromPet(event) || !patch || typeof patch !== "object") return null;
    if (Number.isFinite(patch.replyIndex)) {
      state.pet.replyIndex = Math.max(0, Math.trunc(patch.replyIndex));
    }
    if (Number.isFinite(patch.visits)) {
      state.pet.visits = Math.max(0, Math.trunc(patch.visits));
    }
    if (Number.isFinite(patch.x)) state.pet.x = Math.round(patch.x);
    if (Number.isFinite(patch.y)) state.pet.y = Math.round(patch.y);
    saveStateSoon();
    return { window: { ...state.window }, pet: { ...state.pet } };
  });

}

const hasLock = app.requestSingleInstanceLock();

if (!hasLock) {
  app.quit();
} else {
  app.on("second-instance", () => showPet());

  app.whenReady().then(() => {
    log("ready");
    try {
      app.setAppUserModelId("com.linjunxin.desktop-pet");
      Menu.setApplicationMenu(null);
      loadState();
      log(`state loaded | pet=${JSON.stringify(state.pet)}`);
      state.pet.visits += 1;
      saveStateSoon();
      createPetWindow();
      log("window created");
      buildTray();
      log("tray created");
      registerIpc();
      registerShortcuts();
      log("init done");
    } catch (error) {
      log(`init failed: ${error && error.stack}`);
      throw error;
    }
  });

  app.on("window-all-closed", () => {
    log("window-all-closed");
    // Tray resident: keep the process alive while the window is hidden.
  });

  app.on("before-quit", () => {
    log("before-quit");
    isQuitting = true;
    writeState();
  });

  app.on("will-quit", () => {
    stopHitTracking();
    globalShortcut.unregisterAll();
  });
}
