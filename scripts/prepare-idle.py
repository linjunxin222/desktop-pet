"""Convert a green-screen idle clip into transparent desktop-pet assets.

Requires ffmpeg with libvpx-vp9; uses only the Python standard library.
"""

import argparse
import json
import math
import statistics
import subprocess
from pathlib import Path


def ffmpeg(*args):
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", *map(str, args)]


def first_frame(source):
    pam = subprocess.check_output(ffmpeg("-i", source, "-frames:v", 1, "-pix_fmt", "rgb24", "-c:v", "pam", "-f", "image2pipe", "pipe:1"))
    header, pixels = pam.split(b"ENDHDR\n", 1)
    fields = dict(line.split(maxsplit=1) for line in header.splitlines()[1:])
    width, height = int(fields[b"WIDTH"]), int(fields[b"HEIGHT"])
    corners = [0, width - 1, width * (height - 1), width * height - 1]
    color = tuple(int(statistics.median(pixels[index * 3 + channel] for index in corners)) for channel in range(3))
    if color[1] < max(color[0], color[2]) + 30:
        raise ValueError("Expected an evenly lit green background.")
    return width, height, color


def alpha_union(command, width, height):
    union = bytearray(width * height)
    frame_size = width * height * 4
    frames = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        while True:
            frame = process.stdout.read(frame_size)
            if not frame:
                break
            if len(frame) != frame_size:
                raise RuntimeError("Incomplete RGBA frame.")
            frames += 1
            for index, alpha in enumerate(frame[3::4]):
                if alpha >= 8:
                    union[index] = 1
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError(error)
    if not frames or not any(union):
        raise RuntimeError("No visible character frames were decoded.")
    return union, frames


def bounding_box(mask, width, height):
    visible = [index for index, value in enumerate(mask) if value]
    return min(index % width for index in visible), min(index // width for index in visible), max(index % width for index in visible) + 1, max(index // width for index in visible) + 1


def greenscreen_filter(key):
    # Shadows in narrow hair gaps have a different chroma from the flat screen.
    # Remove green-dominant pixels as well, without increasing the chroma key
    # tolerance enough to make the white clothes transparent.
    dominance = "(g(X,Y)-max(r(X,Y),b(X,Y)))/max(g(X,Y),1)"
    edge_alpha = (
        "alpha(X,Y)*if(gt(g(X,Y)-max(r(X,Y),b(X,Y)),6),"
        f"clip((0.18-{dominance})/0.10,0,1),1)"
    )
    return (
        f"chromakey={key}:0.12:0.02,format=gbrap,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{edge_alpha}',"
        "format=rgba,despill=type=green:mix=1,"
        "lut=a='if(lt(val,8),0,val)'"
    )


def shape_rectangles(mask, width, height, padding):
    # One pixel of contour tolerance retains soft edges and tiny animation details.
    expanded = bytearray(width * height)
    for index, value in enumerate(mask):
        if not value:
            continue
        x, y = index % width, index // width
        for yy in range(max(0, y - 1), min(height, y + 2)):
            for xx in range(max(0, x - 1), min(width, x + 2)):
                expanded[yy * width + xx] = 1

    rectangles = []
    active = {}
    for y in range(height):
        runs = []
        x = 0
        while x < width:
            if not expanded[y * width + x]:
                x += 1
                continue
            start = x
            while x < width and expanded[y * width + x]:
                x += 1
            runs.append((start, x - start))
        next_active = {}
        for run in runs:
            rectangle = active.pop(run, {"x": run[0] + padding, "y": y + padding, "width": run[1], "height": 0})
            rectangle["height"] += 1
            next_active[run] = rectangle
        rectangles.extend(active.values())
        active = next_active
    rectangles.extend(active.values())
    return rectangles


def encode_clean_video(source, clip, video_filter, video_width, video_height):
    """Decode RGBA frames, remove green spill, then encode a transparent WebM."""
    decoder = subprocess.Popen(
        ffmpeg("-i", source, "-vf", video_filter, "-an", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    encoder = subprocess.Popen(
        ffmpeg(
            "-y", "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{video_width}x{video_height}",
            "-framerate", "24", "-i", "pipe:0", "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "0", "-lossless", "1", "-cpu-used", "4", "-row-mt", "1", "-auto-alt-ref", "0",
            "-metadata:s:v:0", "alpha_mode=1", clip,
        ),
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    frame_size = video_width * video_height * 4
    frames = 0
    try:
        while True:
            raw_frame = decoder.stdout.read(frame_size)
            if not raw_frame:
                break
            if len(raw_frame) != frame_size:
                raise RuntimeError("Incomplete RGBA frame.")
            frame = bytearray(raw_frame)
            for index in range(0, len(frame), 4):
                red, green, blue, alpha = frame[index:index + 4]
                if alpha == 0:
                    frame[index:index + 3] = b"\x00\x00\x00"
                    continue
                green_excess = green - max(red, blue)
                if green_excess > 0:
                    # Neutralize every green-tinted edge. Strongly green pixels
                    # belong to the screen inside hair gaps, so remove them;
                    # very small excesses are kept but lose the green cast.
                    frame[index + 1] = max(red, blue)
                    if green_excess >= 4:
                        frame[index + 3] = 0
                        frame[index:index + 3] = b"\x00\x00\x00"
                else:
                    # Compression can leave a yellow-green cast even when red
                    # is still the highest channel. Pull that cast toward the
                    # warm red hair palette while leaving white fabric almost
                    # unchanged.
                    yellow_green_cast = green - blue
                    red_margin = red - green
                    if yellow_green_cast > 12 and red_margin < 55:
                        target_green = int(blue + (red - blue) * 0.24)
                        frame[index + 1] = min(green, target_green)
            encoder.stdin.write(frame)
            frames += 1
    finally:
        if encoder.stdin:
            encoder.stdin.close()
    decoder_error = decoder.stderr.read().decode(errors="replace")
    encoder_error = encoder.stderr.read().decode(errors="replace")
    decoder_code = decoder.wait()
    encoder_code = encoder.wait()
    if decoder_code != 0:
        raise RuntimeError(decoder_error)
    if encoder_code != 0:
        raise RuntimeError(encoder_error)
    if frames == 0:
        raise RuntimeError("No animation frames were encoded.")
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--height", type=int, default=225)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
    args = parser.parse_args()
    if args.height < 64:
        parser.error("The display height must be at least 64 pixels.")
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    source_width, source_height, color = first_frame(args.input)
    key = "0x" + "".join(f"{value:02x}" for value in color)
    key_filter = greenscreen_filter(key)
    analysis_height = 450
    analysis_width = round(source_width / source_height * analysis_height / 2) * 2
    mask, _ = alpha_union(ffmpeg("-i", args.input, "-vf", f"{key_filter},scale={analysis_width}:{analysis_height}", "-an", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"), analysis_width, analysis_height)
    left, top, right, bottom = bounding_box(mask, analysis_width, analysis_height)
    # Keep a small margin around the union of all frames, not only the first frame.
    crop_x = max(0, math.floor((left - 2) * source_width / analysis_width / 2) * 2)
    crop_y = max(0, math.floor((top - 2) * source_height / analysis_height / 2) * 2)
    crop_right = min(source_width, math.ceil((right + 2) * source_width / analysis_width / 2) * 2)
    crop_bottom = min(source_height, math.ceil((bottom + 2) * source_height / analysis_height / 2) * 2)
    crop_width, crop_height = crop_right - crop_x, crop_bottom - crop_y
    display_height = args.height
    display_width = round(crop_width / crop_height * display_height)
    video_width, video_height = display_width * 2, display_height * 2
    clip = output / "idle.webm"
    cleaned_filter = f"chromakey={key}:0.12:0.02,format=rgba,crop={crop_width}:{crop_height}:{crop_x}:{crop_y},scale={video_width}:{video_height},format=rgba"
    frames = encode_clean_video(args.input, clip, cleaned_filter, video_width, video_height)
    subprocess.run(ffmpeg("-y", "-c:v", "libvpx-vp9", "-i", clip, "-frames:v", 1, output / "idle-poster.png"), check=True)

    mask, frames = alpha_union(ffmpeg("-c:v", "libvpx-vp9", "-i", clip, "-vf", f"scale={display_width}:{display_height}", "-an", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"), display_width, display_height)
    padding = 2
    rectangles = shape_rectangles(mask, display_width, display_height, padding)
    layout = {
        "displayWidth": display_width,
        "displayHeight": display_height,
        "padding": padding,
        "windowWidth": display_width + padding * 2,
        "windowHeight": display_height + padding * 2,
        "frames": frames,
        "shape": rectangles,
    }
    (output / "idle-layout.json").write_text(json.dumps(layout, separators=(",", ":")) + "\n", encoding="utf-8")
    (output / "idle-layout.css").write_text(f":root {{ --pet-width: {display_width}px; --pet-height: {display_height}px; --pet-inset: {padding}px; }}\n", encoding="utf-8")
    print(json.dumps({"display": [display_width, display_height], "window": [layout["windowWidth"], layout["windowHeight"]], "frames": frames, "shapeRectangles": len(rectangles), "clipBytes": clip.stat().st_size, "key": key}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
