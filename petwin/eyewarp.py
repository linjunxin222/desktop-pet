"""眼睛局部位形变（眨眼 / 视线）。

自然眨眼不是把整只眼等比压扁，而是：
1. 上眼皮从上往下盖，眼球内容向下压缩（锚点在下眼睑）；
2. 盖住的部分用周围肤色填充；
3. 接缝处画一条睫毛线（取眼睛上缘最深的颜色）。

视线则是眼睛椭圆内的水平/垂直平移。所有位移在椭圆边缘权重归零，所以没有接缝。
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def _bilinear(arr: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> np.ndarray:
    height, width = arr.shape[:2]
    sx = np.clip(sx, 0, width - 1)
    sy = np.clip(sy, 0, height - 1)
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (sx - x0)[..., None]
    wy = (sy - y0)[..., None]
    top = arr[y0, x0] * (1 - wx) + arr[y0, x1] * wx
    bottom = arr[y1, x0] * (1 - wx) + arr[y1, x1] * wx
    return top * (1 - wy) + bottom * wy


def _patch_mean(arr: np.ndarray, cx: int, cy: int, radius: int) -> np.ndarray:
    height, width = arr.shape[:2]
    x0 = max(0, min(width - 1, cx - radius))
    x1 = max(1, min(width, cx + radius + 1))
    y0 = max(0, min(height - 1, cy - radius))
    y1 = max(1, min(height, cy + radius + 1))
    return arr[y0:y1, x0:x1].reshape(-1, 4).mean(axis=0)


def warp_eyes(image: Image.Image, eyes, gaze_x: float = 0.0, gaze_y: float = 0.0, blink: float = 0.0) -> Image.Image:
    """eyes: [{'x','y','rx','ry'}] 归一化；gaze -1..1；blink 0..1。"""
    if abs(gaze_x) < 1e-3 and abs(gaze_y) < 1e-3 and blink < 1e-3:
        return image

    arr = np.asarray(image.convert("RGBA"), dtype=np.float32)
    height, width = arr.shape[:2]
    out = arr.copy()

    for eye in eyes:
        cx = eye["x"] * width
        cy = eye["y"] * height
        rx = max(2.0, eye["rx"] * width)
        ry = max(2.0, eye["ry"] * height)

        x_start = max(0, int(cx - 1.7 * rx))
        x_end = min(width, int(cx + 1.7 * rx))
        y_start = max(0, int(cy - 1.7 * ry))
        y_end = min(height, int(cy + 1.7 * ry))
        if x_end <= x_start or y_end <= y_start:
            continue

        ys, xs = np.mgrid[y_start:y_end, x_start:x_end].astype(np.float32)
        norm_x = (xs - cx) / rx
        norm_y = (ys - cy) / ry
        distance = norm_x * norm_x + norm_y * norm_y
        weight = np.clip((1.0 - distance) / 0.18, 0.0, 1.0)
        if not weight.any():
            continue

        # 肤色：分别取眼睛上方和脸颊的均值，选更亮的那个（避免采到刘海）
        upper = _patch_mean(arr, int(cx), int(cy - ry * 1.5), max(2, int(rx * 0.3)))
        cheek = _patch_mean(arr, int(cx), int(cy + ry * 1.5), max(2, int(rx * 0.3)))
        skin = upper if (upper[0] + upper[1] + upper[2]) > (cheek[0] + cheek[1] + cheek[2]) else cheek
        # 睫毛色：眼睛区域内最暗的一小撮
        region = arr[y_start:y_end, x_start:x_end]
        flat = region.reshape(-1, 4)
        darkest = flat[np.argsort(flat[:, 0] * 0.3 + flat[:, 1] * 0.6 + flat[:, 2] * 0.1)[: max(1, len(flat) // 400)]].mean(axis=0)

        # 眨眼：锚点在下眼睑，上眼皮往下压
        bottom = cy + ry * 0.92
        squeeze = np.maximum(1.0 - 0.92 * blink * weight, 0.08)
        src_y = bottom - (bottom - ys) / squeeze
        src_x = xs - gaze_x * 0.011 * width * weight
        src_x = cx + (src_x - cx) * (1.0 + 0.04 * blink * weight)

        src_x = np.clip(src_x, cx - rx, cx + rx)
        src_y = np.clip(src_y, cy - ry, cy + ry)
        sampled = _bilinear(arr, src_x, src_y)
        blended = sampled * weight[..., None] + region * (1.0 - weight[..., None])

        if blink > 0.02:
            # 闭眼时把压扁的眼球压暗成一条睫毛线（不填肤色、不画弧，避免坐标依赖）
            k = np.clip(0.62 * blink * weight, 0.0, 0.72)[..., None]
            blended = blended * (1.0 - k) + darkest * k

        out[y_start:y_end, x_start:x_end] = blended

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
