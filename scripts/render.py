"""Shared drawing helpers for carousel slides and video frames (Pillow)."""
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "assets" / "raw"
FONTS = Path(r"C:\Windows\Fonts")

PALETTE = {
    "ink": (15, 26, 20),        # deep forest
    "cream": (243, 239, 228),
    "amber": (232, 184, 74),
    "mist": (178, 190, 180),
    "moss": (74, 110, 84),
}


def font(kind, size):
    name = {"bold": "segoeuib.ttf", "semi": "seguisb.ttf", "reg": "segoeui.ttf",
            "light": "segoeuil.ttf", "serif": "georgiab.ttf"}[kind]
    return ImageFont.truetype(str(FONTS / name), size)


def cover(img, w, h, focus=(0.5, 0.45)):
    """Scale-and-crop img to exactly w x h, keeping the focus point (fractions) in frame."""
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    fx, fy = focus
    left = min(max(round(img.width * fx - w / 2), 0), img.width - w)
    top = min(max(round(img.height * fy - h / 2), 0), img.height - h)
    return img.crop((left, top, left + w, top + h))


def load_photo(rel):
    """rel like 'snow-leopard/02.jpg' -> (RGB image, credit dict)."""
    p = RAW / rel
    img = Image.open(p).convert("RGB")
    credits = json.loads((p.parent / "credits.json").read_text(encoding="utf-8"))
    credit = next((c for c in credits if c["file"] == p.name), {})
    return img, credit


def gradient(w, h, color, top_alpha, bottom_alpha, start=0.0):
    """Vertical alpha gradient layer (RGBA) from start fraction to bottom."""
    layer = Image.new("RGBA", (w, h), color + (0,))
    mask = Image.linear_gradient("L").resize((w, max(1, round(h * (1 - start)))))
    mask = mask.point(lambda v: int(top_alpha + (bottom_alpha - top_alpha) * v / 255))
    full = Image.new("L", (w, h), top_alpha if start == 0 else 0)
    full.paste(mask, (0, round(h * start)))
    layer.putalpha(full)
    return layer


def wrap(draw, text, fnt, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_text(draw, text, kind, max_w, max_h, max_size, min_size=36, leading=1.12):
    """Largest font size (<= max_size) whose wrapped block fits max_w x max_h."""
    size = max_size
    while size >= min_size:
        fnt = font(kind, size)
        lines = wrap(draw, text, fnt, max_w)
        height = len(lines) * size * leading
        if height <= max_h and all(draw.textlength(l, font=fnt) <= max_w for l in lines):
            return fnt, lines, size
        size -= 4
    fnt = font(kind, min_size)
    return fnt, wrap(draw, text, fnt, max_w), min_size


def draw_block(draw, x, y, lines, fnt, size, fill, leading=1.12, shadow=True):
    """Draw wrapped lines top-left at (x, y); returns bottom y."""
    for line in lines:
        if shadow:
            draw.text((x + 2, y + 3), line, font=fnt, fill=(0, 0, 0, 140))
        draw.text((x, y), line, font=fnt, fill=fill)
        y += round(size * leading)
    return y


def credit_line(credit):
    """Short attribution string for a Commons photo."""
    if not credit:
        return ""
    artist = html.unescape(credit.get("artist") or "Unknown")
    artist = artist.split("(")[0].strip()[:40]
    return f"Photo: {artist} · Wikimedia Commons · {credit.get('license', '')}"


def pill(draw, xy, text, fnt, fg, bg, pad=(22, 10), radius=26):
    x, y = xy
    tw = draw.textlength(text, font=fnt)
    th = fnt.size
    box = (x, y, x + tw + pad[0] * 2, y + th + pad[1] * 2 + 4)
    draw.rounded_rectangle(box, radius=radius, fill=bg)
    draw.text((x + pad[0], y + pad[1] - 2), text, font=fnt, fill=fg)
    return box


def soften(img, radius=0):
    return img.filter(ImageFilter.GaussianBlur(radius)) if radius else img
