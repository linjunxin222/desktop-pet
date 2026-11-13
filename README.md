# 小鱼 · 桌面伙伴

同一个角色的陪伴系统。**当前仓库只做第一阶段：Windows 桌面上的 Q 版桌宠。**

> **项目边界**：这是一个**全新项目**，与「大肥鱼」（dafeiyu）系列**没有任何关系**，也不复用它的代码、素材、
> 账号体系或记忆数据。两边不要互相引用、不要共用状态文件、不要合并仓库。

角色有四种形态（桌面 Q 版 / 视频通话 / 实体机器人 / 手机随身），四种形态共用一份记忆。
形态规划与验收标准见 [`docs/ROADMAP.md`](docs/ROADMAP.md)，协作规约见 [`AGENTS.md`](AGENTS.md)。

## 现在能做什么（M0）

- **透明悬浮**：无边框、置顶、不进任务栏，角色直接站在桌面上
- **点击穿透**：只有角色、气泡、按钮所在区域接收鼠标，其余位置点击直达桌面
- **托盘常驻**：× 只是收起，进程留在托盘；托盘可显示/收起、开机自启、退出
- **记得住**：窗口位置、当前视图、台词进度、启动次数都写进 `userData/pet-state.json`
- **单实例**：重复启动不会出现第二只，而是唤起已有的那只
- **全局快捷键**：`Ctrl+Alt+P` 显示 / 收起
- **她会动**：WebGL 网格直接变形原图——呼吸、摆动、朝鼠标倾身、瞳孔跟随、随机眨眼、点击回弹（不需要分层素材）
- **她住在桌面上**：整屏透明覆盖层，她会自己走动、走到屏幕边缘爬墙、爬到顶上倒挂着横移、松手会掉下来，也能被鼠标拎起来拖走

## 本地运行

需要 Node.js 20+。

```bash
npm install          # 只需一次
start-pet.cmd        # 双击这个就能启动（或 npm start）
```

> `start-pet.cmd` 会清掉 `ELECTRON_RUN_AS_NODE` 再启动；如果你在别的 Electron 项目里
> 继承过这个环境变量，直接用 `npm start` 会变成跑 node 而不是开窗口。

启动后：**整屏透明覆盖层 + 她站在屏幕右下角**，窗口不进任务栏、不抢焦点；
只有她身体那一块接收鼠标，其他位置点击直接穿透到桌面。

国内网络如果卡在 Electron 二进制下载，先设置镜像再装：

```bash
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
npm install
```

## 交互

| 操作 | 结果 |
|---|---|
| 左键点角色 | 换一句台词并开心一下 |
| 点「挥挥手」 | 她会回应你的挥手 |
| 拖动顶部 26px | 移动窗口（位置会被记住） |
| 右上角 × | 收起到托盘 |
| `Ctrl+Alt+P` | 显示 / 收起 |
| 托盘菜单 | 显示收起、回到桌面、开机自启、退出 |

## 结构

```
electron/main.cjs      主进程：窗口、托盘、状态、命中检测
electron/preload.cjs   唯一能力桥（渲染层拿不到 ipcRenderer）
src/                   渲染层：原生 HTML/CSS/JS
src/rig.js             WebGL 网格绑定：呼吸 / 视线 / 眨眼 / 点击回弹
src/pet.js             物理与状态机：行走 / 爬墙 / 倒挂 / 下落 / 拖拽 / 坐
docs/ACTIONS.md        动作规格：8 个状态、帧尺寸、生成提示词
src/character-texture.js  立绘的 base64 纹理（本地生成，**不入库**）
assets/character-chibi.png   Q 版立绘（透明底，640px 高；**只放本地，已被 .gitignore 排除**）
assets/                托盘与应用图标
docs/CONTRACTS.md      IPC 协议 v1、状态结构与能力分级
docs/character-sheet.md 角色设定卡（绘梨衣）与两种形态规格
docs/ROADMAP.md        M0–M7 与验收标准
AGENTS.md              给 AI / 协作者的约定与验收清单
```

## 角色素材（重要）

角色形象属于第三方作品，**只放本地，不提交到公开仓库**：

```bash
# 本地需要自己准备这两个文件
assets/character-chibi.png    # 透明底立绘
src/character-texture.js      # 由 node tools/pack-texture.mjs 生成
```

`.gitignore` 已排除它们和 `docs/design/`。缺了素材时程序不会崩：Electron 版会隐藏角色画布，
Python 版启动时会提示缺图。

## 已知限制

- 只有 Windows 验证过；macOS / Linux 的托盘与穿透行为未测
- 动作目前是「单图 + 程序化近似」：走路/爬墙/倒挂靠位移和翻转实现，还没有真正的逐帧动作（见 `docs/ACTIONS.md`）
- 还不能换表情、不能对口型
- 没有语音、没有记忆库、没有电脑操作能力（M2–M4）
- 仓库暂无 LICENSE；角色形象来自《龙族》，公开分发前需改名改形象（见 `docs/character-sheet.md`）

## 设计取舍

- **陪伴优先**：助手能力一律以「她帮你」的方式出现，不给你加一排工具按钮
- **主进程只做壳**：后续的语音、记忆、模型都放到独立进程，桌面端只当显示器
- **能力分级**：电脑操作按 L0–L3 分级，L2 以上必须显式确认（见 `docs/CONTRACTS.md`）

## 两种运行方式（重要）

这台机器上 **360 会拦截所有没有数字签名的 exe**（Electron 的 electron.exe、我们自己编译的 exe 都被
静默取消）。所以仓库里有两套宿主：

| 方式 | 入口 | 状态 |
|---|---|---|
| **Python 原生版（推荐，已能跑）** | 双击 `启动桌宠.pyw`（宿主 pythonw.exe，有签名） | 分层窗口、逐像素透明、置顶、穿透、走动/爬墙/倒挂/拖拽 |
| Electron 版 | `start-pet.cmd` | 代码完整，但本机被 360 拦，等加白名单后可用 |

Python 版实现：`petwin/pet.py`（Win32 `UpdateLayeredWindow` + PIL 渲染 + 轮询状态机）。
