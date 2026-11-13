"""双击我就启动桌宠（pythonw.exe 宿主，签名程序，360 放行）。"""
import runpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
target = root / "desktop-pet" / "petwin" / "pet.py"
if not target.exists():
    target = root / "petwin" / "pet.py"
runpy.run_path(str(target), run_name="__main__")
