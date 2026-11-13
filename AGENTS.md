# AGENTS.md

给所有接手这个仓库的 AI / 协作者：先读完这一页，再动代码。

## 这个项目是什么

「小鱼」是一个桌面陪伴系统。当前仓库只有**第一阶段：Windows 桌面端桌宠**。
角色有四种形态（桌面 Q 版 / 视频通话 / 实体机器人 / 手机随身），但**现在只做桌面端**，
其余形态在 `docs/ROADMAP.md` 里排队，不要在桌面端代码里提前埋它们的实现。

> **与「大肥鱼」（dafeiyu）无关。** 这是全新项目：不复制、不引用、不依赖大肥鱼系列的代码、素材、
> 配置或记忆数据，也不要把它俩的仓库/状态文件混在一起。

## 快速开始

```bash
npm install          # 国内网络建议先设 ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
npm start            # 启动桌宠
```

无自动化测试，验收靠「跑起来 + 下面这份手工清单」。

## 目录约定

| 路径 | 职责 | 谁可以改 |
|---|---|---|
| `electron/main.cjs` | 主进程：窗口、托盘、状态持久化、命中检测 | 桌面端负责人 |
| `electron/preload.cjs` | 唯一的能力桥，**新增能力必须同步改 docs/CONTRACTS.md** | 桌面端负责人 |
| `src/` | 渲染层：HTML / CSS / 原生 JS，无框架 | 桌面端负责人 |
| `assets/` | 托盘与应用图标（由脚本生成，勿手改） | 桌面端负责人 |
| `docs/` | 契约与路线图 | 改协议的人 |

多 AI 并行时：**一个 AI 只改一个目录**。跨目录（尤其是 `preload.cjs` + `src/`）的改动，
先改 `docs/CONTRACTS.md` 升协议版本，再动代码。

## 代码风格

- 主进程 / preload 用 **CommonJS**（`.cjs`），渲染层用**原生 JS**，不引入框架。
- 2 空格缩进、双引号、语句带分号（沿用现有文件）。
- UI 文案用中文；代码注释用中文或英文均可，但一个文件内保持一致。
- 不加依赖：新增 npm 依赖前必须先在 PR 里说明理由。

## 安全红线（不要为了省事绕过）

- `contextIsolation: true`、`sandbox: true`、`nodeIntegration: false` 不许关。
- 渲染层**永远拿不到** `ipcRenderer`；只能在 `preload.cjs` 里逐个暴露方法。
- `main.cjs` 的每个 IPC handler 必须校验 `event.sender`，并对入参做类型/范围检查。
- 不执行外部命令、不读写工作目录以外的文件（状态文件除外，路径由 `app.getPath("userData")` 决定）。
- 任何「帮用户操作电脑」的能力，属于 L1 以上，必须走 `docs/CONTRACTS.md` 里的确认流程，不许直接开。
- **角色图（`assets/character-chibi.png`、`src/character-texture.js`、`docs/design/`）只放本地，绝不允许提交/推送**；发现它们被跟踪要立刻 `git rm --cached`。

## 手工验收清单（改完必跑）

1. `npm start` 能起来；角色贴在桌面右下角，**周围透明区域不挡桌面点击**（点图标、点另一个窗口应正常）。
2. 鼠标移到角色上 → 可以点；移开 → 点击穿透恢复。
3. 点角色 → 气泡换台词；点「挥挥手」→ 有回应。
4. 她会自己走动：走到左右边缘时向上爬，到顶后倒挂横移，再掉下来落地。
5. 拖动顶部 26px 区域能移动窗口；关掉再开，**位置和台词进度还在**。
6. 点 × → 收起到托盘（进程不退出）；托盘图标可显示/收起、可退出。
7. 双击启动第二次 → 不出现第二只，而是唤起已有窗口。
8. `Ctrl+Alt+P` 可显示/收起。

## 提交前

```bash
node --check electron/main.cjs
node --check electron/preload.cjs
node --check src/app.js
git diff --stat
```

提交信息用 `feat: / fix: / docs: / chore:` 前缀，一个提交只做一件事。
