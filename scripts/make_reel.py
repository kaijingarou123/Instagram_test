"""Render a vertical Reel (1080x1920, 30 fps, H.264/AAC) from a JSON spec.

Usage:  python scripts/make_reel.py content/reels/mantis-shrimp-punch.json
Output: output/reels/<slug>.mp4 + <slug>-cover.jpg + caption.txt + meta.json

Each scene is a CC photo with Ken Burns motion and animated text kept
inside the Reels safe zone (clear of the top UI and the bottom caption /
action rail). Audio is a quiet generated ambient bed (no copyright risk);
swap in a royalty-free track before real publishing if wanted.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from render import (PALETTE as P, ROOT, cover, credit_line, draw_block, fit_text, font,
                    gradient, load_photo, pill)

W, H, FPS = 1080, 1920, 30
M = 72
SAFE_TOP, SAFE_BOTTOM = 270, 1600      # text lives between these y values
OVERSCAN = 1.2                          # photo rendered larger so we can pan/zoom
XFADE = 0.5                             # seconds of crossfade between scenes
_CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
HANDLE = "@" + _CFG["ig_username"]


def ease(t):
    return t * t * (3 - 2 * t)


def scene_plate(scene):
    """Oversized photo plate with bottom darkening baked in."""
    img, credit = load_photo(scene["image"])
    bw, bh = round(W * OVERSCAN), round(H * OVERSCAN)
    plate = cover(img, bw, bh, tuple(scene.get("focus", (0.5, 0.45)))).convert("RGBA")
    plate.alpha_composite(gradient(bw, bh, P["ink"], 0, 225, start=0.40))
    if scene.get("dim_top"):
        plate.alpha_composite(gradient(bw, bh, P["ink"], 160, 0, start=0.0).transpose(Image.FLIP_TOP_BOTTOM))
    return plate, credit


def text_layer(scene, credit, idx, total):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((M, SAFE_TOP), HANDLE, font=font("semi", 32), fill=P["cream"] + (220,))
    # measure the block first so it is anchored above the credit / safe zone
    hf, hl, hs = fit_text(d, scene["headline"], "bold", W - 2 * M, 420, 96, 60, 1.05)
    bf, bl, bs = (fit_text(d, scene["body"], "reg", W - 2 * M, 260, 46, 38, 1.3)
                  if scene.get("body") else (None, [], 0))
    block = ((100 if scene.get("kicker") else 0) + len(hl) * hs * 1.05
             + (24 + len(bl) * bs * 1.3 if bl else 0) + (60 if scene.get("source") else 0))
    y = min(scene.get("text_y", 1040), SAFE_BOTTOM - 70 - block)
    if scene.get("kicker"):
        pill(d, (M, y), scene["kicker"].upper(), font("semi", 32), P["ink"], P["amber"])
        y += 100
    y = draw_block(d, M, y, hl, hf, hs, P["cream"], 1.05)
    if bl:
        y = draw_block(d, M, y + 24, bl, bf, bs, P["mist"], 1.3)
    if scene.get("source"):
        d.text((M, y + 20), "Source: " + scene["source"], font=font("light", 28), fill=P["mist"] + (210,))
    if credit:
        d.text((M, SAFE_BOTTOM - 36), credit_line(credit), font=font("light", 24), fill=P["cream"] + (170,))
    # scene progress ticks (top, inside safe zone)
    tick_w = (W - 2 * M - (total - 1) * 10) / total
    for i in range(total):
        x0 = M + i * (tick_w + 10)
        d.rounded_rectangle((x0, SAFE_TOP - 26, x0 + tick_w, SAFE_TOP - 20), radius=3,
                            fill=P["amber"] + (255 if i <= idx else 90,))
    return layer


def frames_for(scene, plate, layer):
    n = round(scene["duration"] * FPS)
    bw, bh = plate.size
    zoom_in = scene.get("zoom", "in") == "in"
    fx, fy = scene.get("focus", (0.5, 0.45))
    pan = scene.get("pan", (0.0, 0.0))     # fraction of plate to drift (dx, dy)
    for i in range(n):
        t = ease(i / max(n - 1, 1))
        z = 1.0 + 0.14 * (t if zoom_in else 1 - t)       # 1.00 -> 1.14
        cw, ch = round(bw / z / OVERSCAN * 1.0), round(bh / z / OVERSCAN * 1.0)
        cw, ch = min(cw, bw), min(ch, bh)
        cx = bw * (fx + pan[0] * (t - 0.5))
        cy = bh * (fy + pan[1] * (t - 0.5))
        left = int(min(max(cx - cw / 2, 0), bw - cw))
        top = int(min(max(cy - ch / 2, 0), bh - ch))
        frame = plate.crop((left, top, left + cw, top + ch)).resize((W, H), Image.BILINEAR)
        # text: fade + rise over the first 0.45 s, hold, no exit (crossfade handles it)
        a = min(1.0, i / (0.45 * FPS))
        ea = ease(a)
        if ea < 1.0:
            moved = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            moved.paste(layer, (0, round((1 - ea) * 36)))
            alpha = moved.getchannel("A").point(lambda v: int(v * ea))
            moved.putalpha(alpha)
            frame.alpha_composite(moved)
        else:
            frame.alpha_composite(layer)
        yield np.asarray(frame.convert("RGB"))


def render(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    out_dir = ROOT / "output" / "reels"
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / f"{spec['slug']}.mp4"
    scenes = spec["scenes"]
    total_s = sum(s["duration"] for s in scenes) - XFADE * (len(scenes) - 1)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.035:seed=7,lowpass=f=320,"
                             "afade=t=in:d=1,volume=0.8",
        "-t", f"{total_s:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", "-shortest", str(mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    credits, cover_frame = [], None
    tail = []                                           # frames held back for crossfade
    nx = round(XFADE * FPS)
    for idx, scene in enumerate(scenes):
        plate, credit = scene_plate(scene)
        credits.append(credit)
        layer = text_layer(scene, credit, idx, len(scenes))
        frames = list(frames_for(scene, plate, layer))
        if cover_frame is None:
            cover_frame = frames[min(len(frames) - 1, round(0.6 * FPS))]
        if tail:
            for k in range(nx):                         # blend previous tail into this head
                a = ease((k + 1) / nx)
                mixed = (tail[k].astype(np.float32) * (1 - a) + frames[k].astype(np.float32) * a)
                proc.stdin.write(mixed.astype(np.uint8).tobytes())
            frames = frames[nx:]
        if idx < len(scenes) - 1:
            tail, frames = frames[-nx:], frames[:-nx]
        for f in frames:
            proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")

    Image.fromarray(cover_frame).save(out_dir / f"{spec['slug']}-cover.jpg", "JPEG", quality=90)
    caption = spec["caption"].strip() + "\n\n" + " ".join(spec.get("hashtags", []))
    (out_dir / f"{spec['slug']}-caption.txt").write_text(caption, encoding="utf-8")
    meta = {
        "slug": spec["slug"], "format": "reel", "size": f"{W}x{H}", "fps": FPS,
        "duration_s": round(total_s, 2), "scenes": len(scenes), "audio": "generated ambient bed (CC0-equivalent)",
        "caption_chars": len(caption), "hashtags": spec.get("hashtags", []),
        "format_tags": spec.get("format_tags", []),
        "sources": spec.get("sources", []), "photo_credits": [credit_line(c) for c in credits],
        "file_mb": round(mp4.stat().st_size / 1e6, 2),
    }
    (out_dir / f"{spec['slug']}-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{spec['slug']}: {total_s:.1f}s, {len(scenes)} scenes, {meta['file_mb']} MB -> {mp4}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        render(p)
