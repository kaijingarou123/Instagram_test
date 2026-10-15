"""Render an Instagram carousel (1080x1350 JPEGs) from a JSON post spec.

Usage:  python scripts/make_carousel.py content/posts/snow-leopard-facts.json
Output: output/carousels/<slug>/01.jpg ... + caption.txt + meta.json

Slide types: cover | fact | stat | compare | closing
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from render import (PALETTE as P, ROOT, cover, credit_line, draw_block, fit_text, font,
                    gradient, load_photo, pill, wrap)

W, H = 1080, 1350
M = 72                       # side margin
HANDLE = "@claudes_plan101"


def base(slide):
    img, credit = load_photo(slide["image"])
    photo = cover(img, W, H, tuple(slide.get("focus", (0.5, 0.45))))
    canvas = photo.convert("RGBA")
    return canvas, credit


def chrome(canvas, idx, total, credit, kicker=None):
    """Handle top-left, slide counter top-right, credit bottom-left."""
    d = ImageDraw.Draw(canvas)
    small = font("semi", 30)
    d.text((M, 48), HANDLE, font=small, fill=P["cream"] + (230,))
    counter = f"{idx}/{total}"
    d.text((W - M - d.textlength(counter, font=small), 48), counter, font=small, fill=P["cream"] + (200,))
    if credit:
        tiny = font("light", 24)
        d.text((M, H - 54), credit_line(credit), font=tiny, fill=P["cream"] + (170,))


def slide_cover(s, idx, total):
    canvas, credit = base(s)
    canvas.alpha_composite(gradient(W, H, P["ink"], 0, 235, start=0.35))
    d = ImageDraw.Draw(canvas)
    y = H * 0.50
    if s.get("kicker"):
        pill(d, (M, y), s["kicker"].upper(), font("semi", 30), P["ink"], P["amber"])
        y += 96
    fnt, lines, size = fit_text(d, s["headline"], "bold", W - 2 * M, 440, 108, 64, 1.05)
    y = draw_block(d, M, y, lines, fnt, size, P["cream"], 1.05)
    if s.get("sub"):
        fnt, lines, size = fit_text(d, s["sub"], "reg", W - 2 * M, 160, 44, 36)
        draw_block(d, M, y + 28, lines, fnt, size, P["mist"])
    arrow = font("semi", 34)
    txt = "swipe  →"
    d.text((W - M - d.textlength(txt, font=arrow), H - 118), txt, font=arrow, fill=P["amber"])
    chrome(canvas, idx, total, credit)
    return canvas


BOTTOM = H - 120             # text must end above the credit line


def slide_fact(s, idx, total):
    canvas, credit = base(s)
    d = ImageDraw.Draw(canvas)
    # measure first, then anchor the block so it never runs into the credit line
    hf, hl, hs = fit_text(d, s["headline"], "bold", W - 2 * M, 260, 76, 52, 1.08)
    bf, bl, bs = fit_text(d, s["body"], "reg", W - 2 * M, 320, 42, 36, 1.3)
    block = (76 if s.get("number") else 0) + len(hl) * hs * 1.08 + 26 + len(bl) * bs * 1.3 + (60 if s.get("source") else 0)
    y = min(H * 0.56, BOTTOM - block)
    canvas.alpha_composite(gradient(W, H, P["ink"], 0, 245, start=max(0.2, y / H - 0.16)))
    d = ImageDraw.Draw(canvas)
    if s.get("number"):
        d.text((M, y - 10), s["number"], font=font("serif", 54), fill=P["amber"])
        y += 76
    y = draw_block(d, M, y, hl, hf, hs, P["cream"], 1.08)
    y = draw_block(d, M, y + 26, bl, bf, bs, P["mist"], 1.3)
    if s.get("source"):
        d.text((M, y + 20), "Source: " + s["source"], font=font("light", 28), fill=P["mist"] + (200,))
    chrome(canvas, idx, total, credit)
    return canvas


def slide_stat(s, idx, total):
    canvas, credit = base(s)
    canvas.alpha_composite(gradient(W, H, P["ink"], 60, 250, start=0.0))
    d = ImageDraw.Draw(canvas)
    big = font("bold", 220 if len(s["stat"]) <= 5 else 160)
    y = H * 0.30
    d.text((M, y), s["stat"], font=big, fill=P["amber"])
    y += big.size * 1.0 + 10
    fnt, lines, size = fit_text(d, s["label"], "semi", W - 2 * M, 160, 60, 44, 1.1)
    y = draw_block(d, M, y, lines, fnt, size, P["cream"], 1.1)
    fnt, lines, size = fit_text(d, s["body"], "reg", W - 2 * M, 320, 42, 36, 1.3)
    y = draw_block(d, M, y + 36, lines, fnt, size, P["mist"], 1.3)
    if s.get("source"):
        d.text((M, min(y + 24, BOTTOM - 40)), "Source: " + s["source"], font=font("light", 28), fill=P["mist"] + (200,))
    chrome(canvas, idx, total, credit)
    return canvas


def slide_compare(s, idx, total):
    """Two photos side by side (top), headline + body below."""
    canvas = Image.new("RGBA", (W, H), P["ink"] + (255,))
    ih = 640
    left, cl = load_photo(s["left"]["image"])
    right, cr = load_photo(s["right"]["image"])
    canvas.paste(cover(left, W // 2 - 6, ih), (0, 0))
    canvas.paste(cover(right, W // 2 - 6, ih), (W // 2 + 6, 0))
    d = ImageDraw.Draw(canvas)
    lab = font("semi", 34)
    for x, label in ((M // 2, s["left"]["label"]), (W // 2 + M // 2, s["right"]["label"])):
        pill(d, (x, ih - 90), label, lab, P["ink"], P["amber"])
    y = ih + 70
    fnt, lines, size = fit_text(d, s["headline"], "bold", W - 2 * M, 240, 72, 52, 1.08)
    y = draw_block(d, M, y, lines, fnt, size, P["cream"], 1.08, shadow=False)
    fnt, lines, size = fit_text(d, s["body"], "reg", W - 2 * M, 300, 42, 36, 1.3)
    y = draw_block(d, M, y + 26, lines, fnt, size, P["mist"], 1.3, shadow=False)
    if s.get("source"):
        d.text((M, min(y + 24, H - 150)), "Source: " + s["source"], font=font("light", 28), fill=P["mist"] + (200,))
    tiny = font("light", 24)
    d.text((M, H - 84), credit_line(cl), font=tiny, fill=P["cream"] + (170,))
    d.text((M, H - 54), credit_line(cr), font=tiny, fill=P["cream"] + (170,))
    chrome(canvas, idx, total, None)
    return canvas


def slide_closing(s, idx, total, all_credits):
    canvas, credit = base(s)
    canvas.alpha_composite(gradient(W, H, P["ink"], 120, 250, start=0.0))
    d = ImageDraw.Draw(canvas)
    y = H * 0.22
    fnt, lines, size = fit_text(d, s["headline"], "bold", W - 2 * M, 300, 96, 60, 1.05)
    y = draw_block(d, M, y, lines, fnt, size, P["cream"], 1.05)
    fnt, lines, size = fit_text(d, s["body"], "reg", W - 2 * M, 200, 44, 36, 1.3)
    y = draw_block(d, M, y + 30, lines, fnt, size, P["mist"], 1.3)
    y += 50
    d.text((M, y), "SOURCES", font=font("semi", 28), fill=P["amber"])
    y += 44
    small = font("reg", 30)
    for src in s.get("sources", []):
        for line in wrap(d, "• " + src, small, W - 2 * M):
            d.text((M, y), line, font=small, fill=P["cream"] + (220,))
            y += 40
    y += 30
    d.text((M, y), "PHOTOS", font=font("semi", 28), fill=P["amber"])
    y += 44
    tiny = font("reg", 26)
    seen = set()
    for c in all_credits:
        line = credit_line(c)
        if line and line not in seen and y < H - 120:
            seen.add(line)
            d.text((M, y), line, font=tiny, fill=P["cream"] + (200,))
            y += 34
    chrome(canvas, idx, total, None)
    return canvas


def render(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    out = ROOT / "output" / "carousels" / spec["slug"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    slides = spec["slides"]
    total = len(slides)
    all_credits = []
    for s in slides:
        for key in ("image",):
            if key in s:
                all_credits.append(load_photo(s[key])[1])
        for side in ("left", "right"):
            if side in s:
                all_credits.append(load_photo(s[side]["image"])[1])
    files = []
    for i, s in enumerate(slides, 1):
        fn = {"cover": slide_cover, "fact": slide_fact, "stat": slide_stat,
              "compare": slide_compare}.get(s["type"])
        canvas = slide_closing(s, i, total, all_credits) if s["type"] == "closing" else fn(s, i, total)
        path = out / f"{i:02d}.jpg"
        canvas.convert("RGB").save(path, "JPEG", quality=90, optimize=True, progressive=False)
        files.append(path.name)
    caption = spec["caption"].strip() + "\n\n" + " ".join(spec.get("hashtags", []))
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    meta = {
        "slug": spec["slug"], "format": "carousel", "size": f"{W}x{H}", "slides": files,
        "alt_texts": spec.get("alt_texts", []), "caption_chars": len(caption),
        "hashtags": spec.get("hashtags", []), "format_tags": spec.get("format_tags", []), "sources": spec.get("sources", []),
        "photo_credits": [credit_line(c) for c in all_credits],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    sizes = [round((out / f).stat().st_size / 1024) for f in files]
    print(f"{spec['slug']}: {total} slides -> {out}  sizes(KB)={sizes}  caption={len(caption)} chars")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        render(p)
