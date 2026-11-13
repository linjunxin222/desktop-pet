# 协议契约（CONTRACTS）

> **当前版本：v1**。任何新增 / 修改通道，必须同时改本文件与版本号，否则视为破坏性变更。

## 1. 进程边界

```
renderer (src/)  ──preload 白名单──▶  main (electron/main.cjs)
```

- 渲染层没有 `require`、没有 `ipcRenderer`、不能访问文件系统。
- 所有能力都必须先在 `electron/preload.cjs` 里显式暴露，再在 `main.cjs` 里校验 `event.sender`。

## 2. IPC 通道（v1）

| 通道 | 方向 | 载荷 | 返回 | 说明 |
|---|---|---|---|---|
| `pet:close` | R → M（send） | — | — | 收起到托盘，**不退出进程** |
| `pet:get-state` | R → M（invoke） | — | `State \| null` | 读取持久化状态 |
| `pet:save-state` | R → M（invoke） | `{ replyIndex?: number, visits?: number }` | `State \| null` | 未列出的字段一律忽略 |
| `pet:hit-regions` | R → M（send） | `HitRect[]`，最多 64 条 | — | 上报可点击区域，用于点击穿透 |

### 类型

```ts
type View = "pet" | "house";
interface HitRect { x: number; y: number; w: number; h: number } // CSS px，相对窗口左上角
interface State {
  version: 1;
  window: { x: number | null; y: number | null; view: View };
  pet: { replyIndex: number; visits: number };
}
```

### 失败约定

- `event.sender` 不是桌宠窗口 → 直接丢弃 / 返回 `null`。
- 载荷类型不符 → 丢弃该字段，不抛异常。
- 渲染层必须容忍 `null` 返回值（例如 preload 未注入时）。

## 3. 窗口与视图

| 视图 | 尺寸（DIP） | 说明 |
|---|---|---|
| `pet` | 整屏（workArea） | 透明覆盖层，只有她所在的矩形接收鼠标，其余位置点击穿透 |

2D 小屋已移除（不是想要的样子）。房间以后按 3D 方案单独做，不进这个窗口。

## 4. 点击穿透

- 主进程每 80ms 取一次 `screen.getCursorScreenPoint()`，判断光标是否落在任一 `HitRect` 内（外扩 2px）。
- 在内部 → `setIgnoreMouseEvents(false)`；在外部 → `setIgnoreMouseEvents(true, { forward: true })`。
- 窗口隐藏时强制回到「穿透」状态。
- 渲染层每 700ms 上报一次命中区域，视图切换 / resize 后立即补报一次。

> 为什么不靠 `pointermove` 事件：窗口穿透时事件不保证到达渲染层，轮询光标是唯一稳定方案。

## 5. 状态文件

- 位置：`app.getPath("userData")/pet-state.json`（Windows 约 `%APPDATA%/desktop-pet/pet-state.json`）。
- 写入：变更后 400ms 防抖；退出前强制落盘。
- 容错：文件缺失 / JSON 损坏 / 字段类型不对 → 回落默认值，**不许让程序起不来**。
- 位置越界（拔显示器）→ 按最近显示器的工作区夹取。

## 6. 能力分级（为后续「助手」能力预留）

| 级别 | 含义 | 交互要求 |
|---|---|---|
| L0 | 只读感知（电量、网速、时间） | 无确认 |
| L1 | 可逆操作（开应用、调音量） | 气泡提示 + 3 秒撤销 |
| L2 | 有副作用（删文件、关机） | 必须显式确认 |
| L3 | 支付、密码、系统目录、远程控制他人设备 | 代码层禁止 |
