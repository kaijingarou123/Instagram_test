"""Render a "mood" Reel: real CC motion footage, 1 to 4 cuts, ONE short line of soft serif text, calm music.

Usage:  python scripts/make_mood_reel.py content/reels/<slug>.json [...]
Output: output/reels/<slug>.mp4, -cover.jpg, -caption.txt, -meta.json, -frames.jpg (review sheet)

Why this format (owner review, 4 Nov 2026): the saved Reels that work (120K to 2.3M likes) are moving video with
2 to 8 words on screen and a feeling, not fact cards. The fact, sources and full credits go in the caption.

Spec fields:
  slug, format "mood", duration is the sum of the cuts minus crossfades
  cuts: [{media "folder/01.webm", start s, dur s, focus x (0-1) or [x0, x1] to track across the cut}]
        or {card: "black", dur s} for a plain black card (the contrast-reveal opener)
  lines: [{text, from s, to s (optional, default end), pos "top"|"center" (default top)}]   keep it to 8 words
  music: library slug from assets/music/library.json, music_start s (optional)
  caption, hashtags, sources, alt_text, format_tags, experiment, species
Rules kept from the main pipeline: real footage only, no narration or AI voice, music from assets/music only,
CC credits and sources in the caption only, nothing on screen but the line.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
VID, OUT, MUSIC = ROOT / "assets" / "video", ROOT / "output" / "reels", ROOT / "assets" / "music"
W, H, FPS, XF = 1080, 1920, 30, 0.45
FONT_DIR = Path("C:/Windows/Fonts")
SERIF = FONT_DIR / "constanb.ttf"          # Constantia Bold: calm serif that stays readable on busy footage (owner, 4 Nov)
SMALL = FONT_DIR / "segoeui.ttf"
# Colour grades per Reel (spec "grade", or per cut). Gentle: footage should still look real.
GRADES = {
    "natural": "eq=saturation=1.06:contrast=1.03",
    "warm-autumn": "colorbalance=rs=.05:gs=.01:bs=-.05:rm=.04:bm=-.04,eq=saturation=1.12:contrast=1.05",
    "teal-gold": "colorbalance=rs=-.03:bs=.05:rh=.06:gh=.02:bh=-.05,eq=saturation=1.08:contrast=1.06",
    "soft-pastel": "eq=saturation=0.94:contrast=0.97:brightness=0.02,colorbalance=rm=.02:bm=.03",
    "deep-green": "colorbalance=rs=-.02:gs=.03:gm=.04,eq=saturation=1.14:contrast=1.06",
    "moody-river": "eq=saturation=0.92:contrast=1.1:brightness=-0.02:gamma=0.96,colorbalance=bs=.04:bm=.02,vignette=PI/5",
}
HANDLE = "@" + json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["ig_username"]


def credit_for(media):
    rel = Path(media)
    credits = json.loads((VID / rel.parent / "credits.json").read_text(encoding="utf-8"))
    c = next(c for c in credits if c["file"] == rel.name)
    artist = (c.get("artist") or "Unknown").replace("\n", " ").split("(")[0].strip()
    return {"artist": artist[:60], "license": c["license"], "title": c["title"].replace("File:", ""), "page": c["page"]}


def text_png(path, text, pos, size=88, y=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = ImageFont.truetype(str(SERIF), size)
    d = ImageDraw.Draw(img)
    lines = []
    for para in text.split("\n"):                     # explicit breaks first, then wrap inside the safe column
        cur = ""
        for w_ in para.split():
            t = (cur + " " + w_).strip()
            if d.textlength(t, font=f) > 940 and cur:
                lines.append(cur); cur = w_
            else:
                cur = t
        lines.append(cur)
    lh = int(size * 1.25)
    y0 = y if y is not None else 330 if pos == "top" else (H - lh * len(lines)) // 2 - 80
    if pos == "top":                                 # soft dark wash behind top text so it reads on any clip
        scrim = ImageDraw.Draw(img)
        for y in range(0, 760):
            scrim.line([(0, y), (W, y)], fill=(0, 0, 0, int(105 * (1 - y / 760))))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, ln in enumerate(lines):
        x = (W - d.textlength(ln, font=f)) / 2
        sd.text((x, y0 + i * lh + 3), ln, font=f, fill=(0, 0, 0, 150))
        d.text((x, y0 + i * lh), ln, font=f, fill=(255, 255, 255, 245))
    out = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), img)
    out.save(path)


def credit_png(path, text):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(SMALL), 24)
    d.text((90, 1440), text, font=f, fill=(255, 255, 255, 150))
    d.text((90, 1472), HANDLE, font=f, fill=(255, 255, 255, 150))
    img.save(path)


def render(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    slug = spec["slug"]
    tmp = OUT / f".{slug}-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    cuts = spec["cuts"]
    args, chains, labels, credits = ["ffmpeg", "-v", "error", "-y"], [], [], []
    for i, c in enumerate(cuts):
        if c.get("card"):
            args += ["-f", "lavfi", "-t", str(c["dur"]), "-i", f"color=c=black:s={W}x{H}:r={FPS}"]
            chains.append(f"[{i}:v]format=yuv420p,setsar=1[v{i}]")
        else:
            src = VID / c["media"]
            credits.append(credit_for(c["media"]))
            args += ["-ss", str(c["start"]), "-t", str(c["dur"]), "-i", str(src)]
            fx = c.get("focus", 0.5)
            f0, f1 = (fx, fx) if isinstance(fx, (int, float)) else fx
            z, fy = c.get("zoom", 1), c.get("focus_y", 0.5)   # zoom > 1 crops tighter on a small subject
            xexpr = f"clip(iw*({f0}+({f1}-{f0})*t/{c['dur']})-ow/2\\,0\\,iw-ow)"
            yexpr = f"clip(ih*{fy}-oh/2\\,0\\,ih-oh)"
            chains.append(f"[{i}:v]fps={FPS},crop=w=ih/{z}*9/16:h=ih/{z}:x='{xexpr}':y='{yexpr}',scale={W}:{H}:flags=lanczos,"
                          f"{c.get('speed') and f'setpts={1 / c['speed']:.4f}*PTS,' or ''}"
                          f"{GRADES[c.get('grade', spec.get('grade', 'natural'))]},unsharp=5:5:0.55:5:5:0,setsar=1,format=yuv420p[v{i}]")
        labels.append(f"v{i}")
    # crossfade chain
    xf = spec.get("xfade", XF)                      # 0.1 to 0.15 for fast montage cuts
    for c in cuts:                                  # on-screen length; "speed" < 1 is slow motion (use 50/60 fps sources)
        c["_out"] = c["dur"] / c.get("speed", 1)
    total = cuts[0]["_out"]
    cur = labels[0]
    for i in range(1, len(cuts)):
        off = total - xf
        chains.append(f"[{cur}][{labels[i]}]xfade=transition=fade:duration={xf}:offset={off:.3f}[x{i}]")
        cur, total = f"x{i}", total + cuts[i]["_out"] - xf
    n = len(cuts)
    # text lines and credit as overlays
    pngs = []
    for j, ln in enumerate(spec["lines"]):
        p = tmp / f"line{j}.png"
        text_png(p, ln["text"], ln.get("pos", "top"), size=ln.get("size", 88), y=ln.get("y"))
        pngs.append((p, ln["from"], ln.get("to", total)))
    # Credits and sources live in the caption only (owner, 4 Nov): nothing but the one line on screen.
    for k, (p, a, b) in enumerate(pngs):
        idx = n + k
        args += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(p)]
        fade_in = f"fade=in:st={a}:d=0.5:alpha=1" if a > 0 else "null"
        fade_out = f",fade=out:st={max(a, b - 0.4):.2f}:d=0.4:alpha=1" if b < total - 0.05 else ""
        chains.append(f"[{idx}:v]format=rgba,{fade_in}{fade_out}[t{k}]")
        chains.append(f"[{cur}][t{k}]overlay=0:0:format=auto[o{k}]")
        cur = f"o{k}"
    chains.append(f"[{cur}]fade=in:st=0:d=0.3,fade=out:st={total - 0.6:.2f}:d=0.6,format=yuv420p[vout]")
    lib = {t["slug"]: t for t in json.loads((MUSIC / "library.json").read_text(encoding="utf-8"))}
    track = lib[spec["music"]]
    mfile = next(MUSIC.glob(spec["music"] + ".*"))
    aidx = n + len(pngs)
    args += ["-ss", str(spec.get("music_start", 0)), "-i", str(mfile)]
    chains.append(f"[{aidx}:a]atrim=0:{total:.3f},afade=t=in:d=0.8,afade=t=out:st={total - 1.4:.2f}:d=1.4,volume=0.9[aout]")
    mp4 = OUT / f"{slug}.mp4"
    args += ["-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(mp4)]
    subprocess.run(args, check=True)
    cover_at = spec.get("cover_at", min(1.0, total / 3))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(cover_at), "-i", str(mp4), "-frames:v", "1", "-q:v", "2", str(OUT / f"{slug}-cover.jpg")], check=True)
    step = total / 10
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps=1/{step:.3f},scale=270:-1,tile=10x1", "-frames:v", "1", str(OUT / f"{slug}-frames.jpg")], check=True)
    credit_lines = [f"Video: {c['title']} by {c['artist']}, {c['license']}, via Wikimedia Commons" for c in credits]
    music_line = f"Music: {track['title'].replace('File:', '')} ({track['license']}, Wikimedia Commons)"
    caption = "\n\n".join([spec["caption"].strip(), "\n".join(credit_lines + [music_line]), " ".join(spec.get("hashtags", []))])
    (OUT / f"{slug}-caption.txt").write_text(caption, encoding="utf-8")
    meta = {"slug": slug, "format": "reel", "reel_format": "mood", "size": f"{W}x{H}", "fps": FPS, "duration_s": round(total, 2),
            "lines": [l["text"] for l in spec["lines"]], "cuts": len(cuts), "experiment": spec.get("experiment", {}),
            "audio": f"music: {track['title'].replace('File:', '')} ({track['license']})",
            "music": {"title": track["title"].replace("File:", ""), "licence": track["license"], "source_class": track.get("source_class"),
                      "content_id": False, "source_url": track.get("page", "")},
            "photo_credits": [f"{c['title']} by {c['artist']}, {c['license']}" for c in credits],
            "video_source": {"license": "; ".join(sorted({c["license"] for c in credits}))},
            "synthetic_voice": False, "ai_music": False, "ai_disclosure": "none needed (real footage, no AI imagery or voice)",
            "caption_chars": len(caption), "hashtags": spec.get("hashtags", []), "format_tags": spec.get("format_tags", []),
            "sources": spec.get("sources") or [c["page"] for c in credits], "video_credits": credits, "alt_text": spec.get("alt_text", ""),
            "variant_of": spec.get("variant_of"), "needs_owner_approval": True}
    (OUT / f"{slug}-meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    print(f"{slug}: {total:.1f} s, {len(cuts)} cuts, caption {len(caption)} chars -> {mp4.relative_to(ROOT)}")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        render(a)
