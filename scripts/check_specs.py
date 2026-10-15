"""Validate format-library reel specs before rendering.

    python scripts/check_specs.py                 # all specs in content/formats/specs
    python scripts/check_specs.py <file.json> ... # selected specs

Checks: required fields, slug == file name, format tag exists in the social-media-knowledge
vocabulary (risk copied correctly), tactic tags exist, every media ref exists on disk,
layout-specific fields present, 2–7 scenes, total 8–35 s, text lengths sane, ≤ 5 hashtags.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "content" / "formats" / "specs"
VOCAB = Path(r"E:\claude\Claude-skills-agents-plugins\plugins\social-media-knowledge\knowledge\tags\reel-formats.json")
LAYOUT_NEEDS = {"full": ["media"], "stat": ["media", "stat", "label"], "meme": ["media", "top_text"],
                "split": ["media", "media_b"], "pip": ["media"], "card": [], "quote": ["headline"],
                "wipe": ["media", "media_b"], "grid": ["media_list"], "chart": ["bars", "headline"]}
TEXT_MAX = {"headline": 90, "body": 190, "kicker": 26, "top_text": 110, "bottom_text": 40, "label": 60,
            "stat": 10, "label_a": 22, "label_b": 22, "source": 70}


def media_ok(ref):
    kind, _, rest = ref.partition(":")
    path = rest.split("@")[0]
    base = {"photo": ROOT / "assets" / "raw", "video": ROOT / "assets" / "video"}.get(kind)
    return base is not None and (base / path).exists()


def check(path, vocab):
    errs = []
    try:
        s = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    for k in ("slug", "format_tag", "family", "variant", "title", "risk", "scenes", "caption", "hashtags"):
        if k not in s:
            errs.append(f"missing {k}")
    if errs:
        return errs
    if s["slug"] != path.stem:
        errs.append(f"slug {s['slug']} != file name {path.stem}")
    t = vocab.get(s["format_tag"])
    if not t or not s["format_tag"].startswith("format:"):
        errs.append(f"unknown format tag {s['format_tag']}")
    elif t["risk"] != s["risk"] or t["family"] != s["family"]:
        errs.append(f"risk/family should be {t['risk']}/{t['family']}")
    for tt in s.get("tactic_tags", []):
        if tt not in vocab:
            errs.append(f"unknown tactic tag {tt}")
    if s.get("audio", "bed") not in ("bed", "beat", "silent"):
        errs.append("audio must be bed|beat|silent")
    sc = s["scenes"]
    if not 2 <= len(sc) <= 7:
        errs.append(f"{len(sc)} scenes (want 2–7)")
    total = sum(x.get("duration", 0) for x in sc) - 0.4 * (len(sc) - 1)
    if not 8 <= total <= 35:
        errs.append(f"total {total:.1f}s (want 8–35)")
    for i, x in enumerate(sc, 1):
        lay = x.get("layout", "full")
        if lay not in LAYOUT_NEEDS:
            errs.append(f"scene {i}: unknown layout {lay}")
            continue
        for k in LAYOUT_NEEDS[lay]:
            if not x.get(k):
                errs.append(f"scene {i} ({lay}): missing {k}")
        if not 1.5 <= x.get("duration", 0) <= 9:
            errs.append(f"scene {i}: duration {x.get('duration')} (want 1.5–9)")
        refs = [x.get("media"), x.get("media_b"), *(x.get("media_list") or [])]
        for r in filter(None, refs):
            if not media_ok(r):
                errs.append(f"scene {i}: media not found {r}")
        for k, mx in TEXT_MAX.items():
            if isinstance(x.get(k), str) and len(x[k]) > mx:
                errs.append(f"scene {i}: {k} too long ({len(x[k])}>{mx})")
        if lay == "chart" and not all("label" in b and "value" in b for b in x.get("bars", [])):
            errs.append(f"scene {i}: chart bars need label+value")
    if len(s["hashtags"]) > 5:
        errs.append(f"{len(s['hashtags'])} hashtags (max 5)")
    if len(s["caption"]) > 1500:
        errs.append("caption > 1500 chars")
    return errs


def main(args):
    vocab = {t["tag"]: t for t in json.loads(VOCAB.read_text(encoding="utf-8"))["tags"]}
    paths = [Path(a) for a in args] if args else sorted(SPECS.glob("*.json"))
    bad = 0
    for p in paths:
        errs = check(p, vocab)
        if errs:
            bad += 1
            print(f"FAIL {p.name}")
            for e in errs:
                print(f"   - {e}")
    print(f"{len(paths) - bad}/{len(paths)} specs OK")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
