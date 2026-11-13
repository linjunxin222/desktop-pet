"""小鱼 · 桌面伙伴（Windows 原生版）

宿主用 python.exe（有数字签名，360 放行），窗口用 Win32 分层窗口（UpdateLayeredWindow），
所以能做到逐像素透明、置顶、不进任务栏、透明区域点击穿透。

运行：pythonw petwin/pet.py
退出：右键点她 → 菜单里选“退出”；或关掉托盘/任务管理器里的 pythonw。
"""

from __future__ import annotations

import ctypes
import glob
import json
import math
import os
import random
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont

from eyewarp import warp_eyes

# ---------------------------------------------------------------- Win32 常量
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
SM_CXSCREEN = 0
SM_CYSCREEN = 1

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
ASSET = os.path.join(ROOT, "assets", "character-chibi.png")
STATE_FILE = os.path.join(os.environ.get("APPDATA", ROOT), "xiaoyu", "state.json")

# 眼睛在立绘里的归一化位置（换图后要跟着改，否则眨眼会闭偏）
EYES = [
    {"x": 0.415, "y": 0.288, "rx": 0.055, "ry": 0.048},
    {"x": 0.575, "y": 0.288, "rx": 0.055, "ry": 0.048},
]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]




def _setup_prototypes() -> None:
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        wintypes.HDC, ctypes.POINTER(POINT), wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
    ]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DefWindowProcW.restype = ctypes.c_long
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]


_setup_prototypes()

# ---------------------------------------------------------------- 角色资产
def load_font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class Character:
    def __init__(self, path: str, height: int = 250):
        source = Image.open(path).convert("RGBA")
        ratio = source.width / source.height
        self.base = source.resize((max(1, round(height * ratio)), height), Image.LANCZOS)
        self.closed = None
        self.idle_frames = []
        idle_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), "assets", "actions", "idle")
        for frame_path in sorted(glob.glob(os.path.join(idle_dir, "*.png"))):
            frame = Image.open(frame_path).convert("RGBA")
            self.idle_frames.append(frame.resize((round(height * frame.width / frame.height), height), Image.LANCZOS))
        closed_path = path.replace(".png", "-closed.png")
        if os.path.exists(closed_path):
            alt = Image.open(closed_path).convert("RGBA")
            self.closed = alt.resize((max(1, round(height * alt.width / alt.height)), height), Image.LANCZOS)

    def frame(self, state: str, t: float, scale: float, rotate: float, flip: bool) -> Image.Image:
        image = self.base
        if abs(scale - 1.0) > 0.005:
            w = max(1, round(image.width * scale))
            h = max(1, round(image.height * scale))
            image = image.resize((w, h), Image.LANCZOS)
        if abs(rotate) > 0.5:
            image = image.rotate(-rotate, expand=True, resample=Image.BICUBIC)
        if flip:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        return image


# ---------------------------------------------------------------- 状态机
class PetState:
    IDLE = "idle"
    WALK = "walk"
    CLIMB = "climb"
    CRAWL = "crawl"
    FALL = "fall"
    DRAG = "drag"
    SIT = "sit"
    HAPPY = "happy"


class Pet:
    WIDTH = 360
    HEIGHT = 470

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.character = Character(ASSET, 250)
        self.state = PetState.IDLE
        self.state_time = 0.0
        self.dir = -1
        self.vx = 0.0
        self.vy = 0.0
        self.dragging = False
        self.drag_offset = (0, 0)

        saved = self._load_state()
        self.x = float(saved.get("x", screen_w - self.WIDTH - 20))
        self.y = float(saved.get("y", screen_h - self.HEIGHT - 40))
        self._clamp()

        self.bubble = "嗨，我来陪你啦！"
        self.bubble_until = time.time() + 6
        self.font = load_font(15)

        # 眨眼 / 视线状态
        self.blink = 0.0
        self.blink_start = None
        self.next_blink = time.time() + 2.5 + random.random() * 3
        self.gaze_x = 0.0
        self.gaze_y = 0.0
        self.drift_x = 0.0
        self.drift_y = 0.0
        self.look_timer = time.time() + random.uniform(2, 5)
        self.menu_open = False
        self.pause_walk = False

    # -- 持久化 -------------------------------------------------------
    def _load_state(self) -> dict:
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as handle:
                json.dump({"x": round(self.x), "y": round(self.y)}, handle)
        except Exception:
            pass

    # -- 物理 ---------------------------------------------------------
    def _clamp(self) -> None:
        self.x = max(-40, min(self.screen_w - self.WIDTH + 40, self.x))
        self.y = max(-80, min(self.screen_h - self.HEIGHT, self.y))

    @property
    def ground_y(self) -> float:
        return self.screen_h - self.HEIGHT

    def enter(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self.state_time = 0.0

    def update(self, dt: float) -> None:
        self.state_time += dt
        now_ts = time.time()

        # 待机时自己东张西望
        if self.state == PetState.IDLE and now_ts > self.look_timer:
            self.drift_x = random.uniform(-0.95, 0.95)
            self.drift_y = random.uniform(-0.4, 0.35)
            self.look_timer = now_ts + random.uniform(1.6, 3.8)

        if self.pause_walk and self.state in (PetState.WALK, PetState.CLIMB, PetState.CRAWL):
            self.enter(PetState.IDLE)

        # 眨眼：每 2.5–6 秒一次，单次 160ms
        now = time.time()
        if self.blink_start is None and now >= self.next_blink:
            self.blink_start = now
        if self.blink_start is not None:
            progress = (now - self.blink_start) / 0.16
            if progress >= 1:
                self.blink_start = None
                self.blink = 0.0
                self.next_blink = now + 2.5 + random.random() * 3.5
            else:
                self.blink = math.sin(math.pi * progress)
        if os.environ.get("PET_DEBUG_BLINK") == "1":
            self.blink = 1.0
        if self.state == PetState.IDLE and self.state_time > 5 + random.random() * 4:
            self.dir = random.choice((-1, 1))
            self.enter(PetState.WALK)
        elif self.state == PetState.WALK:
            self.x += self.dir * 46 * dt
            if self.x <= 0 or self.x >= self.screen_w - self.WIDTH:
                self.x = max(0, min(self.screen_w - self.WIDTH, self.x))
                self.enter(PetState.CLIMB)
        elif self.state == PetState.CLIMB:
            self.y -= 62 * dt
            if self.y <= 0:
                self.y = 0
                self.dir = -self.dir
                self.enter(PetState.CRAWL)
        elif self.state == PetState.CRAWL:
            self.x += self.dir * 40 * dt
            if self.x <= 0 or self.x >= self.screen_w - self.WIDTH:
                self.x = max(0, min(self.screen_w - self.WIDTH, self.x))
                self.enter(PetState.FALL)
        elif self.state == PetState.FALL:
            self.vy += 2400 * dt
            self.y += self.vy * dt
            self.x += self.vx * dt
            self._clamp()
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self.vy = 0
                self.vx = 0
                self.enter(random.choice((PetState.SIT, PetState.IDLE)))
        elif self.state == PetState.SIT and self.state_time > 4:
            self.enter(PetState.IDLE)
        elif self.state == PetState.HAPPY and self.state_time > 1.2:
            self.enter(PetState.IDLE)

    # -- 绘制 ---------------------------------------------------------
    def render(self, cursor) -> Image.Image:
        canvas = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))

        bob = math.sin(self.state_time * 9) * 3 if self.state == PetState.WALK else 0
        if self.state == PetState.HAPPY:
            bob -= abs(math.sin(self.state_time * 9)) * 10
        breathe = 1 + 0.012 * math.sin(time.time() * 1.7)
        rotate = 0.0
        scale = 1.0

        if self.state == PetState.CRAWL:
            rotate = 180.0
        elif self.state == PetState.CLIMB:
            rotate = self.dir * 6.0
        elif self.state == PetState.FALL:
            scale = 1.03
        elif self.state == PetState.SIT:
            scale = 0.94
        elif self.state == PetState.HAPPY:
            scale = 1 + math.sin(self.state_time * 18) * 0.04
        elif self.state == PetState.DRAG:
            rotate = math.sin(self.state_time * 6) * 8

        frames = self.character.idle_frames
        if self.state == PetState.IDLE and frames:
            # 待机播逐帧动画（视频抽帧），不再叠加程序化形变
            image = frames[int(self.state_time * 12) % len(frames)]
            px = (self.WIDTH - image.width) // 2
            py = self.HEIGHT - image.height - 70
            canvas.paste(image, (px, py), image)
            if self.bubble and time.time() < self.bubble_until:
                canvas.alpha_composite(self._bubble_image(self.bubble), (self.WIDTH // 2 - 120, 8))
            if self.menu_open:
                canvas.alpha_composite(self._menu_image(), (self.WIDTH // 2 - 78, 6))
            if self._hover_quit:
                draw = ImageDraw.Draw(canvas)
                draw.ellipse((self.WIDTH - 46, 12, self.WIDTH - 16, 42), fill=(255, 255, 255, 235), outline=(220, 200, 210))
                draw.line((self.WIDTH - 37, 21, self.WIDTH - 25, 33), fill=(150, 120, 130), width=2)
                draw.line((self.WIDTH - 25, 21, self.WIDTH - 37, 33), fill=(150, 120, 130), width=2)
            return canvas

        image = self.character.frame(
            self.state, self.state_time, scale * breathe, rotate + self.gaze_x * 2.4, self.dir < 0
        )

        # 视线跟着鼠标：以她的头中心为原点
        head_x = self.x + self.WIDTH / 2
        head_y = self.y + self.HEIGHT - image.height - 70 + image.height * 0.30
        target_x = max(-1.0, min(1.0, (cursor.x - head_x) / 280.0))
        target_y = max(-1.0, min(1.0, (cursor.y - head_y) / 280.0))
        ease = 0.25
        self.gaze_x += (target_x - self.gaze_x) * ease
        self.gaze_y += (target_y - self.gaze_y) * ease

        if os.environ.get("PET_DEBUG_GAZE") == "1":
            self.gaze_x, self.gaze_y = 1.0, -0.2
        image = warp_eyes(image, EYES, self.gaze_x, self.gaze_y, self.blink)
        px = (self.WIDTH - image.width) // 2 + int(self.gaze_x * 7)
        py = self.HEIGHT - image.height - 70 + int(bob)
        canvas.paste(image, (px, py), image)

        # 气泡
        if self.bubble and time.time() < self.bubble_until:
            canvas.alpha_composite(self._bubble_image(self.bubble), (self.WIDTH // 2 - 120, 8))

        # 右键菜单
        if self.menu_open:
            canvas.alpha_composite(self._menu_image(), (self.WIDTH // 2 - 78, 6))

        # 悬停时的退出按钮
        if self._hover_quit:
            draw = ImageDraw.Draw(canvas)
            draw.ellipse((self.WIDTH - 46, 12, self.WIDTH - 16, 42), fill=(255, 255, 255, 235), outline=(220, 200, 210))
            draw.line((self.WIDTH - 37, 21, self.WIDTH - 25, 33), fill=(150, 120, 130), width=2)
            draw.line((self.WIDTH - 25, 21, self.WIDTH - 37, 33), fill=(150, 120, 130), width=2)

        return canvas

    def _bubble_image(self, text: str) -> Image.Image:
        margin = 14
        bbox = self.font.getbbox(text)
        width = min(232, bbox[2] - bbox[0] + margin * 2)
        height = bbox[3] - bbox[1] + margin * 2 - 4
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=14, fill=(255, 255, 255, 242), outline=(255, 255, 255, 255), width=1)
        draw.polygon([(width // 2 - 7, height - 1), (width // 2 + 7, height - 1), (width // 2, height + 9)], fill=(255, 255, 255, 242))
        draw.text((margin - bbox[0], margin - bbox[1] - 2), text, font=self.font, fill=(103, 87, 121, 255))
        return image

    MENU_ITEMS = (("回到右下角", "recenter"), ("暂停走动", "pause"), ("退出", "quit"))
    MENU_X = WIDTH // 2 - 78
    MENU_Y = 6.0
    MENU_W = 156
    MENU_ROW = 30

    def _menu_image(self) -> Image.Image:
        rows = len(self.MENU_ITEMS)
        height = rows * self.MENU_ROW + 12
        image = Image.new("RGBA", (self.MENU_W, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, self.MENU_W - 1, height - 1), radius=12,
                               fill=(255, 255, 255, 246), outline=(232, 220, 228), width=1)
        for index, (label, _action) in enumerate(self.MENU_ITEMS):
            text = label
            if _action == "pause" and self.pause_walk:
                text = "继续走动"
            y = 6 + index * self.MENU_ROW
            if index:
                draw.line((10, y, self.MENU_W - 10, y), fill=(240, 232, 238), width=1)
            draw.text((16, y + 7), text, font=self.font, fill=(92, 78, 104, 255))
        return image

    def menu_hit(self, local_x: float, local_y: float):
        if not self.menu_open:
            return None
        if not (self.MENU_X <= local_x <= self.MENU_X + self.MENU_W):
            return None
        offset = local_y - self.MENU_Y - 6
        if offset < 0:
            return None
        index = int(offset // self.MENU_ROW)
        if 0 <= index < len(self.MENU_ITEMS):
            return self.MENU_ITEMS[index][1]
        return None

    _hover_quit = False


# ---------------------------------------------------------------- 窗口
class LayeredWindow:
    def __init__(self, pet: Pet):
        self.pet = pet
        self.hinst = kernel32.GetModuleHandleW(None)
        self.class_name = "XiaoyuPetWindow"
        self.wndproc = WNDPROC(self._wndproc)
        wc = WNDCLASS(
            0,
            self.wndproc,
            0,
            0,
            self.hinst,
            None,
            None,
            None,
            None,
            self.class_name,
        )
        if not user32.RegisterClassW(ctypes.byref(wc)):
            error = ctypes.get_last_error()
            if error not in (0, 1410):  # 1410 = class already exists
                raise ctypes.WinError(error)

        ex_style = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = user32.CreateWindowExW(
            ex_style,
            self.class_name,
            "小鱼",
            WS_POPUP,
            int(pet.x),
            int(pet.y),
            pet.WIDTH,
            pet.HEIGHT,
            None,
            None,
            self.hinst,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError()

        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        self.bits = ctypes.c_void_p()
        self.bitmap = None
        self.old_bitmap = None

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = pet.WIDTH
        bmi.bmiHeader.biHeight = -pet.HEIGHT
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        self.bitmap = gdi32.CreateDIBSection(
            self.hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0
        )
        self.old_bitmap = gdi32.SelectObject(self.hdc_mem, self.bitmap)
        self.size = SIZE(pet.WIDTH, pet.HEIGHT)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def blit(self, image: Image.Image) -> None:
        import numpy as np

        rgba = np.asarray(image, dtype=np.float32)
        alpha = rgba[..., 3:4] / 255.0
        premultiplied = rgba[..., :3] * alpha
        bgra = np.empty(rgba.shape, dtype=np.uint8)
        bgra[..., 0] = premultiplied[..., 2]   # B
        bgra[..., 1] = premultiplied[..., 1]   # G
        bgra[..., 2] = premultiplied[..., 0]   # R
        bgra[..., 3] = rgba[..., 3]            # A
        data = bgra.tobytes()
        ctypes.memmove(self.bits, data, len(data))

        pt_dst = POINT(int(self.pet.x), int(self.pet.y))
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd,
            self.hdc_screen,
            ctypes.byref(pt_dst),
            ctypes.byref(self.size),
            self.hdc_mem,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )


# ---------------------------------------------------------------- 主循环
def main() -> None:
    user32.SetProcessDPIAware()
    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYSCREEN)

    pet = Pet(screen_w, screen_h)
    if os.environ.get("PET_DEBUG_MENU") == "1":
        pet.menu_open = True
    window = LayeredWindow(pet)

    last = time.time()
    save_at = time.time() + 5
    press_pos = None
    press_time = 0.0
    was_down = False

    while True:
        now = time.time()
        dt = min(0.05, now - last)
        last = now

        # 消息泵
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        cursor = POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        local_x = cursor.x - int(pet.x)
        local_y = cursor.y - int(pet.y)
        inside = -20 <= local_x <= pet.WIDTH + 20 and -20 <= local_y <= pet.HEIGHT + 20
        pet._hover_quit = inside and local_x > pet.WIDTH - 60 and local_y < 60

        down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        right = bool(user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)

        if inside and pet._hover_quit and down and not was_down:
            pet.save_state()
            user32.ShowWindow(window.hwnd, 0)
            return
        if right and not was_down:
            pet.menu_open = inside and not pet.menu_open

        if down and not was_down and pet.menu_open:
            action = pet.menu_hit(local_x, local_y)
            pet.menu_open = False
            was_down = True
            if action == "quit":
                pet.save_state()
                user32.ShowWindow(window.hwnd, 0)
                return
            if action == "recenter":
                pet.x = screen_w - pet.WIDTH - 20
                pet.y = pet.ground_y
                pet.enter(PetState.IDLE)
            elif action == "pause":
                pet.pause_walk = not pet.pause_walk
            continue

        if inside and down and not was_down:
            press_pos = (cursor.x, cursor.y)
            press_time = now
            pet.dragging = True
            pet.drag_offset = (cursor.x - int(pet.x), cursor.y - int(pet.y))
            pet.enter(PetState.DRAG)

        if pet.dragging and down:
            pet.x = cursor.x - pet.drag_offset[0]
            pet.y = cursor.y - pet.drag_offset[1]
            pet._clamp()
        elif pet.dragging and not down:
            pet.dragging = False
            pet.vy = 0
            pet.enter(PetState.FALL)
            if press_pos and now - press_time < 0.35 and abs(cursor.x - press_pos[0]) < 6 and abs(cursor.y - press_pos[1]) < 6:
                pet.bubble = random.choice(["嗯？", "你回来啦。", "我在这儿。", "……饿。"])
                pet.bubble_until = now + 5
                pet.enter(PetState.HAPPY)

        was_down = down

        if not pet.dragging:
            pet.update(dt)

        window.blit(pet.render(cursor))

        if now > save_at:
            pet.save_state()
            save_at = now + 5

        time.sleep(0.033)


if __name__ == "__main__":
    main()
