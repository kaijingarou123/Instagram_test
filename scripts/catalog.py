"""Build assets/catalog.json and catalog.md: every photo and video clip available to the reel engine.

    python scripts/catalog.py

Each entry gives the media ref to put in a spec ("photo:tiger/01.jpg", "video:tiger/01.webm"),
orientation, duration (video), licence and the Commons title (what the shot shows).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW, VID = ROOT / "assets" / "raw", ROOT / "assets" / "video"


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True).stdout
    j = json.loads(out or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("width"), s.get("height"), float(j.get("format", {}).get("duration") or 0)


def main():
    cat = {"photo": {}, "video": {}}
    for kind, base, pat in (("photo", RAW, "*.jpg"), ("video", VID, "*.webm")):
        for d in sorted(p for p in base.glob("*") if p.is_dir()):
            cj = d / "credits.json"
            credits = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else []
            items = []
            for f in sorted(d.glob(pat)):
                c = next((x for x in credits if x.get("file") == f.name), {})
                if kind == "photo":
                    from PIL import Image
                    with Image.open(f) as im:
                        w, h = im.size
                    dur = None
                else:
                    w, h, dur = probe(f)
                items.append({"ref": f"{kind}:{d.name}/{f.name}", "w": w, "h": h,
                              "orientation": "portrait" if h and w and h > w else "landscape",
                              "duration_s": round(dur, 1) if dur else None,
                              "shows": c.get("title", "").replace("File:", "").rsplit(".", 1)[0][:90],
                              "license": c.get("license", "")})
            if items:
                cat[kind][d.name] = items
    tmp = ROOT / "assets" / f"catalog.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ROOT / "assets" / "catalog.json")
    lines = ["# Media catalog", "", "Use the `ref` exactly in specs. Video refs may add `@<start seconds>`.", ""]
    for kind in ("video", "photo"):
        lines += [f"## {kind}s ({sum(len(v) for v in cat[kind].values())} across {len(cat[kind])} species)", ""]
        for sp, items in cat[kind].items():
            for it in items:
                extra = f"{it['duration_s']}s " if it["duration_s"] else ""
                lines.append(f"- `{it['ref']}` — {extra}{it['orientation']} — {it['shows']}")
        lines.append("")
    (ROOT / "assets" / "catalog.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"photos: {sum(len(v) for v in cat['photo'].values())} in {len(cat['photo'])} species; "
          f"videos: {sum(len(v) for v in cat['video'].values())} in {len(cat['video'])} species")


if __name__ == "__main__":
    main()
