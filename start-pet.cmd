@echo off
chcp 65001 >nul
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0"

if not exist "node_modules\electron\dist\electron.exe" (
  echo [!] 还没装依赖，先在当前目录运行：npm install
  pause
  exit /b 1
)

echo 正在启动桌宠... 启动后窗口是全屏透明的，她出现在屏幕右下角。
echo 关闭：点她右下角的 x，或者托盘图标右键退出。
start "" "node_modules\electron\dist\electron.exe" .
