"""Multi-layout Reel engine (stills + video clips) for the format library.

    python scripts/make_reel2.py content/formats/specs/<slug>.json [...]
    python scripts/make_reel2.py --all [--jobs 8]          # every spec, in parallel

Output: output/formats/<slug>.mp4, <slug>.jpg (poster), <slug>.json (meta)

Media refs:  "photo:<species>/<file>"  (assets/raw)  |  "video:<species>/<file>[@start]"  (assets/video)
Layouts:     full, meme, split, pip, card, stat, wipe, grid, chart, quote
Overlays:    spec.storyboard -> "STORYBOARD" band naming what must be filmed
             spec.risk == "avoid" -> red "AVOID — DO NOT POST" band
             scene.subtitle -> list of caption chunks shown in sequence (voiceover style)
Audio:       spec.audio = "bed" (ambient noise bed) | "beat" (120 bpm synth kick) | "silent"
"""
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import PALETTE as P, cover, credit_line, draw_block, fit_text, font, gradient, pill, wrap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, VID = ROOT / "assets" / "raw", ROOT / "assets" / "video"
SPECS, OUT = ROOT / "content" / "formats" / "specs", ROOT / "output" / "formats"
W, H, FPS = 1080, 1920, 30
XF = 0.4                     # crossfade seconds
TX0, TX1 = 80, 920           # text column (clear of the right action rail)
TOP, BOT = 270, 1500         # vertical safe band for text
_CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
HANDLE = "@" + _CFG["ig_username"]
BG = {"ink": P["ink"], "amber": P["amber"], "moss": P["moss"], "cream": P["cream"],
      "night": (12, 18, 34), "white": (250, 250, 247), "red": (178, 40, 40)}


# --------------------------------------------------------------------------- media
def _credits(base, rel):
    p = base / rel
    try:
        cr = json.loads((p.parent / "credits.json").read_text(encoding="utf-8"))
        return next((c for c in cr if c.get("file") == p.name), {})
    except FileNotFoundError:
        return {}


def parse_ref(ref):
    kind, _, rest = ref.partition(":")
    path, _, start = rest.partition("@")
    return kind, path, float(start or 0)


def media_frames(ref, w, h, n, motion="in", focus=(0.5, 0.45)):
    """Yield n RGB PIL frames of size w x h for a photo (Ken Burns) or a video clip."""
    kind, path, start = parse_ref(ref)
    if kind == "photo":
        img = Image.open(RAW / path).convert("RGB")
        ov = 1.18
        plate = cover(img, round(w * ov), round(h * ov), tuple(focus))
        bw, bh = plate.size
        for i in range(n):
            t = i / max(n - 1, 1)
            t = t * t * (3 - 2 * t)
            z = 1 + 0.12 * (t if motion != "out" else 1 - t)
            cw, ch = round(bw / z / ov), round(bh / z / ov)
            dx = {"pan-left": -0.06, "pan-right": 0.06}.get(motion, 0) * (t - 0.5) * bw
            cx, cy = bw / 2 + dx, bh / 2
            left = int(min(max(cx - cw / 2, 0), bw - cw))
            top = int(min(max(cy - ch / 2, 0), bh - ch))
            yield plate.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BILINEAR)
        return
    src = VID / path
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{n / FPS + 0.5:.2f}",
           "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS}",
           "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size, frames = w * h * 3, []
    while len(frames) < n:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        frames.append(Image.frombuffer("RGB", (w, h), buf, "raw", "RGB", 0, 1))
    proc.stdout.close()
    proc.wait()
    if not frames:
        frames = [Image.new("RGB", (w, h), P["ink"])]
    k = 0
    for i in range(n):                       # ping-pong if the clip is shorter than the scene
        yield frames[k]
        if len(frames) > 1:
            k = (k + 1) % (2 * len(frames) - 2)
            k = k if k < len(frames) else 2 * len(frames) - 2 - k


def credit_for(ref):
    kind, path, _ = parse_ref(ref)
    c = _credits(RAW if kind == "photo" else VID, path)
    return credit_line(c) if c else ""


# --------------------------------------------------------------------------- text helpers
def text_block(d, s, y, max_h=700, head_size=92, color=None, shadow=True):
    """kicker pill + headline + body + source, top-left at y inside the text column."""
    color = color or P["cream"]
    width = TX1 - TX0
    if s.get("kicker"):
        pill(d, (TX0, y), s["kicker"].upper(), font("semi", 32), P["ink"], P["amber"])
        y += 96
    if s.get("headline"):
        f, lines, sz = fit_text(d, s["headline"], "bold", width, max_h * 0.55, head_size, 54, 1.06)
        y = draw_block(d, TX0, y, lines, f, sz, color, 1.06, shadow)
    if s.get("body"):
        f, lines, sz = fit_text(d, s["body"], "reg", width, max_h * 0.4, 46, 36, 1.3)
        y = draw_block(d, TX0, y + 22, lines, f, sz, P["mist"] if color == P["cream"] else color, 1.3, shadow)
    if s.get("source"):
        d.text((TX0, y + 18), "Source: " + s["source"], font=font("light", 28),
               fill=(P["mist"] if color == P["cream"] else color) + (210,))
        y += 50
    return y


def block_height(s, max_h=700, head_size=92):
    probe = ImageDraw.Draw(Image.new("RGBA", (W, H)))
    return text_block(probe, s, 0, max_h, head_size) + 10


def glow(lay, radius=16, strength=0.7):
    """Soft dark halo behind text so it stays readable on bright or busy photos (WCAG-ish contrast)."""
    a = lay.getchannel("A").filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(radius))
    halo = Image.new("RGBA", lay.size, (8, 12, 10, 0))
    halo.putalpha(a.point(lambda v: int(min(255, v * 1.8) * strength)))
    halo.alpha_composite(lay)
    return halo


def text_layer(s, anchor="bottom", color=None, shadow=True):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hgt = block_height(s)
    y = {"bottom": BOT - hgt, "center": (TOP + BOT) / 2 - hgt / 2, "top": TOP + 40}[anchor]
    text_block(d, s, max(TOP, y), color=color, shadow=shadow)
    return glow(lay)


def chrome(spec, scene, idx, total, credit):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.text((TX0, 200), HANDLE, font=font("semi", 30), fill=P["cream"] + (220,))
    tw = (TX1 - TX0 - (total - 1) * 10) / total
    for i in range(total):
        x0 = TX0 + i * (tw + 10)
        d.rounded_rectangle((x0, 176, x0 + tw, 182), radius=3, fill=P["amber"] + (255 if i <= idx else 90,))
    if credit:
        d.text((TX0, BOT + 30), credit[:95], font=font("light", 24), fill=P["cream"] + (175,))
    if spec.get("storyboard"):
        d.rectangle((0, 70, W, 150), fill=(20, 20, 20, 215))
        d.text((TX0, 82), "STORYBOARD", font=font("bold", 30), fill=P["amber"])
        f, lines, _ = fit_text(d, spec["storyboard"], "reg", W - TX0 - 60, 40, 26, 22)
        d.text((TX0, 116), lines[0] if lines else "", font=f, fill=P["cream"])
    if spec.get("risk") == "avoid":
        d.rectangle((0, H - 300, W, H - 230), fill=BG["red"] + (235,))
        d.text((TX0, H - 290), "AVOID — DO NOT POST · anti-pattern demo", font=font("bold", 34), fill=(255, 255, 255))
    return lay


def subtitle_layer(chunk):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = font("bold", 64)
    lines = wrap(d, chunk.upper(), f, TX1 - TX0)[:3]
    y = 820 - len(lines) * 76 / 2
    for ln in lines:
        x = (W - d.textlength(ln, font=f)) / 2
        d.text((x, y), ln, font=f, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))
        y += 76
    return lay


# --------------------------------------------------------------------------- layouts
def scene_frames(spec, s, idx, total):
    """Yield RGBA frames for one scene."""
    n = round(s["duration"] * FPS)
    lay, kind = s.get("layout", "full"), None
    motion, focus = s.get("motion", "in"), s.get("focus", (0.5, 0.45))
    credit = credit_for(s["media"]) if s.get("media") else (credit_for(s["media_list"][0]) if s.get("media_list") else "")
    ch = chrome(spec, s, idx, total, credit)

    def finish(frame, text, i, scrim=True):
        frame = frame.convert("RGBA")
        if scrim:
            frame.alpha_composite(SCRIM)
        a = min(1.0, i / (0.4 * FPS))
        if text is not None:
            if a < 1:
                t2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                t2.paste(text, (0, round((1 - a) * 30)))
                t2.putalpha(t2.getchannel("A").point(lambda v: int(v * a)))
                frame.alpha_composite(t2)
            else:
                frame.alpha_composite(text)
        subs = s.get("subtitle")
        if subs:
            k = min(len(subs) - 1, int(i / n * len(subs)))
            frame.alpha_composite(SUBS.setdefault(subs[k], subtitle_layer(subs[k])))
        frame.alpha_composite(ch)
        return frame

    if lay in ("full", "stat"):
        text = stat_layer(s) if lay == "stat" else text_layer(s, s.get("anchor", "bottom"))
        for i, fr in enumerate(media_frames(s["media"], W, H, n, motion, focus)):
            yield finish(fr, text, i)

    elif lay == "meme":
        band = 430
        top = Image.new("RGBA", (W, band), BG["white"] + (255,))
        d = ImageDraw.Draw(top)
        f, lines, sz = fit_text(d, s["top_text"], "bold", W - 120, band - 140, 72, 44, 1.12)
        y = 150 + (band - 150 - len(lines) * sz * 1.12) / 2
        for ln in lines:
            d.text(((W - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=(15, 15, 15))
            y += sz * 1.12
        bottom = None
        if s.get("bottom_text"):
            bottom = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            bd = ImageDraw.Draw(bottom)
            f2 = font("bold", 64)
            for j, ln in enumerate(wrap(bd, s["bottom_text"].upper(), f2, W - 160)[:2]):
                bd.text(((W - bd.textlength(ln, font=f2)) / 2, 1330 + j * 74), ln, font=f2,
                        fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
        for i, fr in enumerate(media_frames(s["media"], W, H - band, n, motion, focus)):
            canvas = Image.new("RGBA", (W, H), BG["white"] + (255,))
            canvas.paste(fr, (0, band))
            canvas.alpha_composite(top, (0, 0))
            yield finish(canvas, bottom, i, scrim=False)

    elif lay == "split":
        hh = H // 2
        lab = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lab)
        if s.get("label_a"):
            pill(d, (TX0, hh - 100), s["label_a"], font("semi", 34), P["ink"], P["amber"])
        if s.get("label_b"):
            pill(d, (TX0, H - 520), s["label_b"], font("semi", 34), P["ink"], P["amber"])
        if s.get("headline") or s.get("body"):
            sub = {k: s.get(k) for k in ("kicker", "headline", "body", "source")}
            hgt = block_height(sub, 360, 72)
            d.rectangle((0, TOP - 20, W, TOP + hgt + 10), fill=(10, 14, 12, 170))
            text_block(d, sub, TOP, 360, 72)
        a_fr = media_frames(s["media"], W, hh, n, motion, focus)
        b_fr = media_frames(s["media_b"], W, hh, n, s.get("motion_b", "out"), s.get("focus_b", (0.5, 0.5)))
        for i, (fa, fb) in enumerate(zip(a_fr, b_fr)):
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            canvas.paste(fa, (0, 0))
            canvas.paste(fb, (0, hh))
            ImageDraw.Draw(canvas).rectangle((0, hh - 3, W, hh + 3), fill=P["amber"])
            yield finish(canvas, lab, i, scrim=False)

    elif lay == "pip":
        text = text_layer(s, "bottom")
        bw_, bh_ = 380, 500
        mask = Image.new("L", (bw_, bh_), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw_, bh_), radius=40, fill=255)
        inset = media_frames(s["media_b"], bw_, bh_, n, "in", (0.5, 0.4)) if s.get("media_b") else None
        label = s.get("pip_label", "REACTOR")
        for i, fr in enumerate(media_frames(s["media"], W, H, n, motion, focus)):
            frame = fr.convert("RGBA")
            box = next(inset).convert("RGBA") if inset else placeholder(bw_, bh_, label)
            frame.paste(box, (W - bw_ - 60, TOP + 20), mask)
            ImageDraw.Draw(frame).rounded_rectangle((W - bw_ - 60, TOP + 20, W - 60, TOP + 20 + bh_),
                                                   radius=40, outline=P["amber"], width=6)
            yield finish(frame, text, i)

    elif lay in ("card", "quote"):
        bg = Image.new("RGBA", (W, H), BG.get(s.get("bg", "ink")) + (255,))
        dark = s.get("bg", "ink") in ("ink", "night", "moss", "red")
        col = P["cream"] if dark else P["ink"]
        d = ImageDraw.Draw(bg)
        y = TOP + 120
        if s.get("big"):
            f = font("bold", 300)
            d.text((TX0, y - 40), s["big"], font=f, fill=P["amber"] if dark else P["moss"])
            y += 330
        thumb = s.get("media")
        sub = {k: s.get(k) for k in ("kicker", "headline", "body", "source")}
        if lay == "quote":
            f, lines, sz = fit_text(d, "“" + s["headline"] + "”", "serif", TX1 - TX0, 900, 96, 56, 1.15)
            yy = (TOP + BOT) / 2 - len(lines) * sz * 1.15 / 2
            draw_block(d, TX0, yy, lines, f, sz, col, 1.15, shadow=False)
            if s.get("body"):
                d.text((TX0, yy + len(lines) * sz * 1.15 + 40), "— " + s["body"], font=font("semi", 40), fill=col)
            sub = {}
        text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if sub:
            text_block(ImageDraw.Draw(text), sub, y, BOT - y - (520 if thumb else 0), 96, color=col, shadow=False)
        frames = media_frames(thumb, W - 2 * TX0, 520, n, motion, focus) if thumb else None
        for i in range(n):
            frame = bg.copy()
            if frames:
                th = next(frames).convert("RGBA")
                m = Image.new("L", th.size, 0)
                ImageDraw.Draw(m).rounded_rectangle((0, 0, *th.size), radius=36, fill=255)
                frame.paste(th, (TX0, BOT - 520), m)
            yield finish(frame, text, i, scrim=False)

    elif lay == "wipe":
        text = text_layer(s, "top")
        la, lb = s.get("label_a", "BEFORE"), s.get("label_b", "AFTER")
        fa_it = media_frames(s["media"], W, H, n, "in", focus)
        fb_it = media_frames(s["media_b"], W, H, n, "in", s.get("focus_b", (0.5, 0.45)))
        for i, (fa, fb) in enumerate(zip(fa_it, fb_it)):
            t = min(1, max(0, (i / n - 0.25) / 0.5))
            t = t * t * (3 - 2 * t)
            x = int(W * (1 - t))
            canvas = fa.convert("RGBA")
            canvas.paste(fb.crop((x, 0, W, H)), (x, 0))
            d = ImageDraw.Draw(canvas)
            d.rectangle((x - 4, 0, x + 4, H), fill=P["amber"])
            pill(d, (TX0, BOT - 90), la, font("semi", 34), P["ink"], P["cream"])
            if t > 0.5:
                pill(d, (TX1 - 220, BOT - 90), lb, font("semi", 34), P["ink"], P["amber"])
            yield finish(canvas, text, i)

    elif lay == "grid":
        refs = (s["media_list"] * 4)[:4]
        gw, gh = W // 2, (BOT - TOP + 200) // 2
        its = [media_frames(r, gw - 6, gh - 6, n, "in") for r in refs]
        text = text_layer(s, "top") if (s.get("headline") or s.get("kicker")) else None
        for i in range(n):
            canvas = Image.new("RGBA", (W, H), P["ink"] + (255,))
            for k, it in enumerate(its):
                canvas.paste(next(it), ((k % 2) * gw + 3, TOP + 260 + (k // 2) * gh + 3))
            yield finish(canvas, text, i, scrim=False)

    elif lay == "chart":
        bars = s["bars"]
        vmax = max(b["value"] for b in bars)
        base = Image.new("RGBA", (W, H), BG.get(s.get("bg", "night")) + (255,))
        text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        text_block(ImageDraw.Draw(text), {k: s.get(k) for k in ("kicker", "headline", "source")}, TOP, 420, 80, shadow=False)
        f_l, f_v = font("semi", 38), font("bold", 40)
        y0, rowh = TOP + 470, min(150, (BOT - TOP - 520) / len(bars))
        for i in range(n):
            t = min(1, i / (n * 0.6))
            t = t * t * (3 - 2 * t)
            frame = base.copy()
            d = ImageDraw.Draw(frame)
            for k, b in enumerate(bars):
                y = y0 + k * rowh
                d.text((TX0, y), b["label"], font=f_l, fill=P["cream"])
                bw = (TX1 - TX0 - 10) * b["value"] / vmax * t
                d.rounded_rectangle((TX0, y + 50, TX0 + max(bw, 8), y + 50 + rowh * 0.42), radius=10,
                                    fill=P["amber"] if k == s.get("highlight", 0) else P["moss"])
                val = f"{b['value'] * t:,.0f}{s.get('unit', '')}" if t < 1 else b.get("display", f"{b['value']:,}{s.get('unit', '')}")
                d.text((TX0 + max(bw, 8) + 14, y + 46), val, font=f_v, fill=P["cream"])
            yield finish(frame, text, i, scrim=False)
    else:
        raise ValueError(f"unknown layout {lay}")


def stat_layer(s):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    big = font("bold", 230 if len(s["stat"]) <= 5 else 150)
    y = 640
    d.text((TX0, y), s["stat"], font=big, fill=P["amber"], stroke_width=2, stroke_fill=(0, 0, 0))
    text_block(d, {"headline": s.get("label"), "body": s.get("body"), "source": s.get("source")},
               y + big.size + 20, 560, 60)
    return glow(lay)


def placeholder(w, h, label):
    im = Image.new("RGBA", (w, h), (40, 46, 42, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((w / 2 - 80, 110, w / 2 + 80, 270), fill=(90, 100, 94))
    d.rounded_rectangle((w / 2 - 140, 290, w / 2 + 140, 460), radius=70, fill=(90, 100, 94))
    f = font("bold", 34)
    d.text(((w - d.textlength(label, font=f)) / 2, 30), label, font=f, fill=P["amber"])
    return im


SCRIM = gradient(W, H, P["ink"], 0, 230, start=0.45)
SUBS = {}


# --------------------------------------------------------------------------- render
def render(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = OUT / f"{spec['slug']}.mp4"
    scenes = spec["scenes"]
    total = sum(s["duration"] for s in scenes) - XF * (len(scenes) - 1)
    audio = spec.get("audio", "bed")
    a_in = {"bed": ["-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.03:seed=3,lowpass=f=320,afade=t=in:d=1"],
            "beat": ["-f", "lavfi", "-i", "aevalsrc=0.5*sin(2*PI*55*t)*exp(-28*mod(t\\,0.5))+0.12*sin(2*PI*880*t)*exp(-60*mod(t+0.25\\,0.5)):s=44100"],
            "silent": ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]}[audio]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *a_in, "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", "-shortest", str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nx, tail, poster = round(XF * FPS), [], None
    for idx, s in enumerate(scenes):
        frames = [np.asarray(f.convert("RGB")) for f in scene_frames(spec, s, idx, len(scenes))]
        if poster is None:
            poster = frames[min(len(frames) - 1, round(0.7 * FPS))]
        if tail:
            for k in range(nx):
                a = (k + 1) / nx
                proc.stdin.write((tail[k] * (1 - a) + frames[k] * a).astype(np.uint8).tobytes())
            frames = frames[nx:]
        if idx < len(scenes) - 1:
            tail, frames = [f.astype(np.float32) for f in frames[-nx:]], frames[:-nx]
        for f in frames:
            proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {spec['slug']}")
    Image.fromarray(poster).resize((360, 640)).save(OUT / f"{spec['slug']}.jpg", "JPEG", quality=82)
    refs = [r for s in scenes for r in [s.get("media"), s.get("media_b"), *(s.get("media_list") or [])] if r]
    meta = {k: spec.get(k) for k in ("slug", "format_tag", "family", "variant", "title", "risk", "tactic_tags",
                                     "storyboard", "caption", "hashtags", "sources")}
    meta.update({"duration_s": round(total, 1), "file_mb": round(mp4.stat().st_size / 1e6, 2),
                 "credits": sorted({c for c in (credit_for(r) for r in refs) if c})})
    (OUT / f"{spec['slug']}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"{spec['slug']}: {total:.1f}s {meta['file_mb']} MB"


def main(argv):
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    argv = [a.strip() for a in argv]          # a CRLF list file once dropped 129 of 130 jobs silently
    paths = sorted(SPECS.glob("*.json")) if "--all" in argv else [Path(a) for a in argv if a.endswith(".json")]
    if not "--all" in argv and len(paths) != sum(1 for a in argv if a and not a.startswith("--") and not a.isdigit()):
        sys.exit("some arguments are not .json spec paths — refusing to skip them silently")
    if "--missing" in argv:
        paths = [p for p in paths if not (OUT / f"{p.stem}.mp4").exists()]
    if len(paths) == 1:
        print(render(paths[0]))
        return
    ok = bad = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(render, p): p for p in paths}
        for fu in as_completed(futs):
            try:
                print(fu.result(), flush=True)
                ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {futs[fu].stem}: {type(e).__name__}: {e}", flush=True)
                bad += 1
    print(f"done: {ok} ok, {bad} failed")


if __name__ == "__main__":
    main(sys.argv[1:])
