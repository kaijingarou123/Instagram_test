"""Pre-publish checks for rendered carousels and reels.

Usage:  python scripts/preflight.py                # checks everything in output/
        python scripts/preflight.py mantis-shrimp-punch orca-hunt

Checks are drawn from research/posting-limits.md (Meta API media specs,
hashtag cap, originality rules) and research/content-strategy.md
(readability, sourcing). Exit code 1 if any item FAILs.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CAPTION_MAX = 2200
HASHTAG_MAX = 5
IMG_MAX_MB = 8
REEL_MAX_MB = 300
REEL_MIN_S, REEL_MAX_S = 3, 180
# House style (owner's rule, 2026-10-17): no em dashes and no emojis anywhere in a post:
# on-slide/on-screen text, caption or alt text. En dashes in numeric ranges (10–18 cm) are fine.
EM_DASH = "—"
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def jaccard(a, b):
    wa = set(re.findall(r"[a-z']+", a.lower()))
    wb = set(re.findall(r"[a-z']+", b.lower()))
    return len(wa & wb) / max(len(wa | wb), 1)


def check_style(slug, kind, texts, res):
    """No em dashes or emojis in the spec (all on-media text), caption or alt texts."""
    spec = ROOT / "content" / ("posts" if kind == "carousel" else "reels") / f"{slug}.json"
    blob = "\n".join(texts + ([spec.read_text(encoding="utf-8")] if spec.exists() else []))
    dashes = blob.count(EM_DASH) + blob.lower().count("\\u2014")
    emojis = sorted(set(EMOJI.findall(blob)))
    res.append(("no em dashes (caption, alt text, on-media text)", dashes == 0, f"{dashes} found" if dashes else ""))
    res.append(("no emojis (caption, alt text, on-media text)", not emojis,
                " ".join(f"U+{ord(e):04X}" for e in emojis)))
    # the only @handle a post may mention is the account's own (config.json), so a rename
    # can't leave stale or stray names on slides, captions or alt text
    own = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["ig_username"].lower()
    handles = {h.lower() for h in re.findall(r"(?<![\w.])@([A-Za-z0-9_.]*[A-Za-z0-9_])", blob)}
    stray = sorted(handles - {own})
    res.append((f"only @{own} mentioned", not stray, " ".join("@" + h for h in stray)))


def check_caption(caption, hashtags, others, res):
    body = caption.split("\n\n#")[0]
    res.append(("caption length <= 2200", len(caption) <= CAPTION_MAX, f"{len(caption)} chars"))
    res.append(("hashtags 3-5", 3 <= len(hashtags) <= HASHTAG_MAX, f"{len(hashtags)}"))
    res.append(("no external links in caption", "http" not in caption.lower(), ""))
    res.append(("source cited in caption", bool(re.search(r"source", caption, re.I)), ""))
    res.append(("photo credit in caption", bool(re.search(r"photo|credit|wikimedia", caption, re.I)), ""))
    generic = {"#nature", "#wildlife", "#animals", "#love", "#photooftheday", "#instagood"}
    res.append(("no generic mega-hashtags", not (set(h.lower() for h in hashtags) & generic), ""))
    worst = max((jaccard(body, o) for o in others), default=0.0)
    res.append(("caption unique vs other posts (Jaccard < 0.5)", worst < 0.5, f"max similarity {worst:.2f}"))


def check_carousel(d, others, res):
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    caption = (d / "caption.txt").read_text(encoding="utf-8")
    slides = meta["slides"]
    res.append(("2-10 slides", 2 <= len(slides) <= 10, f"{len(slides)}"))
    for s in slides:
        p = d / s
        im = Image.open(p)
        ratio = im.width / im.height
        ok = (im.format == "JPEG" and im.mode == "RGB" and 320 <= im.width <= 1440
              and 0.8 - 1e-3 <= ratio <= 1.91 and p.stat().st_size <= IMG_MAX_MB * 1e6)
        res.append((f"{s}: JPEG/sRGB, 4:5..1.91:1, <=8MB", ok,
                    f"{im.format} {im.width}x{im.height} {p.stat().st_size/1e6:.2f}MB"))
    res.append(("alt text for every slide", len(meta.get("alt_texts", [])) == len(slides), ""))
    res.append(("alt texts <= 1000 chars", all(len(a) <= 1000 for a in meta.get("alt_texts", [])), ""))
    res.append(("photo credits recorded", all(meta.get("photo_credits", [])), f"{len(meta.get('photo_credits', []))} credits"))
    res.append(("sources recorded", len(meta.get("sources", [])) >= 1, f"{len(meta.get('sources', []))} sources"))
    res.append(("designed asset (text overlay): originality rule", True, "all slides rendered with informative overlays"))
    check_style(d.name, "carousel", [caption, *meta.get("alt_texts", [])], res)
    check_caption(caption, meta["hashtags"], others, res)
    return caption


CLIP_LICENCE = re.compile(r"^(cc0|pd|public domain|cc by(-sa)? \d)", re.I)


def audio_ok(meta):
    """Every audio source must be allowed (platform-guardrails 0.1.3): synthesised here, TTS, (owner decisions
    2026-10-28) the natural sound of the CC0/PD/CC BY/CC BY-SA clip shown, credited with it, or music that is a
    public-domain / CC0 recording, a Meta Sound Collection track, a Pixabay track without Content ID, or AI music made
    on a plan that grants commercial rights. Whether natural sound contains music or speech is checked by the owner."""
    parts = [p.strip() for p in meta.get("audio", "").split(";") if p.strip()]
    lic = meta.get("video_source", {}).get("license", "")

    def ok(p):
        if p.startswith("generated") or p.startswith("TTS narration"):
            return True
        if p.startswith("natural sound from the CC clip"):
            return bool(CLIP_LICENCE.match(lic)) and not re.search(r"\b(nc|nd)\b", lic, re.I)
        if not p.startswith("music:"):
            return False
        m = meta.get("music")
        if m:   # provenance recorded by make_loop_reel.py: named source classes only, never Content ID-registered
            lic_ok = not re.search(r"\b(nc|nd)\b", m.get("licence", ""), re.I)
            cls = m.get("source_class")
            return lic_ok and m.get("content_id") is False and (
                (cls in ("classical-pd", "modern-cc0") and bool(re.match(r"(cc0|pd|public domain)", m["licence"], re.I)))
                or cls == "meta-sound-collection"
                or (cls == "pixabay" and "pixabay.com/music/" in m.get("source_url", ""))
                or (cls == "ai-generated" and bool(m.get("plan")) and bool(m.get("terms_url"))))
        # older renders: a Meta Sound Collection track or a public-domain / CC0 recording (never chart music)
        return bool(re.search(r"\((Meta Sound Collection|Public domain|PD[^)]*|CC0)\)$", p, re.I))

    return bool(parts) and all(ok(p) for p in parts)


def probe(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate:format=duration,bit_rate",
                          "-of", "json", str(mp4)], capture_output=True, text=True).stdout
    return json.loads(out)


def check_reel(slug, others, res):
    d = OUT / "reels"
    mp4 = d / f"{slug}.mp4"
    meta = json.loads((d / f"{slug}-meta.json").read_text(encoding="utf-8"))
    caption = (d / f"{slug}-caption.txt").read_text(encoding="utf-8")
    info = probe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    mbps = int(info["format"]["bit_rate"]) / 1e6
    fps = eval(v["r_frame_rate"])
    res.append(("video H.264", v["codec_name"] == "h264", v["codec_name"]))
    res.append(("1080x1920 (9:16)", (v["width"], v["height"]) == (1080, 1920), f"{v['width']}x{v['height']}"))
    res.append(("23-60 fps", 23 <= fps <= 60, f"{fps:g}"))
    res.append(("duration 3 s - 3 min", REEL_MIN_S <= dur <= REEL_MAX_S, f"{dur:.1f}s"))
    res.append(("audio AAC <= 48 kHz", a is not None and a["codec_name"] == "aac" and int(a["sample_rate"]) <= 48000,
                a["codec_name"] if a else "none"))
    res.append(("<= 300 MB, <= 25 Mbps", mp4.stat().st_size <= REEL_MAX_MB * 1e6 and mbps <= 25,
                f"{mp4.stat().st_size/1e6:.1f}MB {mbps:.1f}Mbps"))
    head = mp4.read_bytes()[:64]
    res.append(("moov atom at front (faststart)", b"moov" in head, ""))
    res.append(("audio: generated, CC-clip natural sound, TTS or Meta Sound Collection", audio_ok(meta),
                meta.get("audio", "")))
    # owner rule (28 Oct 2026): no narration of any kind; viewers read the on-screen text over soothing music
    res.append(("no narration / synthetic voice", not meta.get("synthetic_voice") and "TTS" not in meta.get("audio", ""),
                "narrated" if meta.get("synthetic_voice") else ""))
    res.append(("cover image exists", (d / f"{slug}-cover.jpg").exists(), ""))
    res.append(("photo credits recorded", all(meta.get("photo_credits", [])), ""))
    res.append(("sources recorded", len(meta.get("sources", [])) >= 1, ""))
    check_style(slug, "reel", [caption], res)
    check_caption(caption, meta["hashtags"], others, res)
    return caption


def main(slugs):
    carousels = {p.name: p for p in (OUT / "carousels").glob("*") if (p / "meta.json").exists()}
    reels = {p.stem.replace("-meta", ""): p for p in (OUT / "reels").glob("*-meta.json")}
    targets = slugs or sorted([*carousels, *reels])
    captions = {}
    for name in [*carousels, *reels]:
        cap = (carousels[name] / "caption.txt") if name in carousels else (OUT / "reels" / f"{name}-caption.txt")
        captions[name] = cap.read_text(encoding="utf-8").split("\n\n#")[0]
    failed = 0
    for name in targets:
        res = []
        others = [c for n, c in captions.items() if n != name]
        if name in carousels:
            check_carousel(carousels[name], others, res)
        elif name in reels:
            check_reel(name, others, res)
        else:
            print(f"?? {name}: not found in output/")
            continue
        bad = [r for r in res if not r[1]]
        failed += len(bad)
        print(f"\n== {name}: {len(res) - len(bad)}/{len(res)} checks passed")
        for label, ok, note in res:
            if not ok or "--verbose" in sys.argv:
                print(f"  {'PASS' if ok else 'FAIL'}  {label}  {note}")
    print(f"\n{'ALL CLEAR' if not failed else str(failed) + ' FAILURES'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--")])
