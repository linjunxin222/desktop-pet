# 桌宠项目

这是同一角色陪伴系统的 Windows 桌面原型，使用 Electron 实现。

## 当前交互

- 角色暂时固定正面，不随鼠标转向
- 循环播放用户提供的待机动画，已去除绿幕和音轨
- 按住角色拖动可移动桌宠，松开后留在新位置
- 角色高 225 像素，透明背景直接显示在桌面上
- 右键点击角色，菜单里有“打开绘梨衣对话”和“退出”
- 窗口贴近动画尺寸，人物轮廓外的空白区域可点击穿透

## 角色素材

- `assets/idle.webm` 是带透明通道的待机动画，`idle-poster.png` 用于首帧预览
- `assets/idle-layout.json`、`idle-layout.css` 保存显示尺寸和覆盖全部动画帧的窗口轮廓
- `assets/turnaround-source.png` 保存用户提供的原始三视图
- `assets/character-front.png`、`character-side.png`、`character-back.png` 是桌宠运行时使用的透明切图

## 本地运行

本机可双击桌面上的“绘梨衣桌宠”快捷方式启动。重复启动会显示已有窗口。

需要安装 Node.js 当前 LTS 版本。

    npm install
    npm start

语音、视频互动、手机控制和实体机器人会在后续阶段加入。

## 与绘梨衣对话窗口联动

右键菜单里的「打开绘梨衣对话」会启动本机 `Documents\绘梨衣对话` 的独立对话窗口；对话窗口工程不在本仓库，桌宠本体仍按上面的方式运行。

## 替换待机动画

准备纯绿幕视频后，使用已安装的 Python 和 FFmpeg 转换素材：

    python scripts/prepare-idle.py "待机动画.mp4" --height 225

然后重新启动桌宠。转换过程会自动去绿幕、去音轨、裁掉留白，并重新计算窗口的可点击轮廓。

