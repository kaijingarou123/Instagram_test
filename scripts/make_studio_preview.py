"""Make a light 720p preview of rendered Reels for the Field Desk's Reel Studio tab.

Usage:  python scripts/make_studio_preview.py <slug> [...]
Reads output/reels/<slug>.mp4 and -cover.jpg; writes output/studio/<slug>-preview.mp4 (720x1280, about 1 to 4 MB)
and output/studio/<slug>-cover.jpg (540 px wide). Prints one JSON line per slug with the file paths and sizes, ready
for the Artifact tool's asset upload (page assets must stay under 15 MB each).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "output" / "reels", ROOT / "output" / "studio"


def main(slugs):
    OUT.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        mp4, cover = SRC / f"{slug}.mp4", SRC / f"{slug}-cover.jpg"
        prev, pcover = OUT / f"{slug}-preview.mp4", OUT / f"{slug}-cover.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "scale=720:1280:flags=lanczos",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-movflags", "+faststart", str(prev)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cover), "-vf", "scale=540:-1", "-q:v", "4", str(pcover)], check=True)
        meta = json.loads((SRC / f"{slug}-meta.json").read_text(encoding="utf-8"))
        print(json.dumps({"slug": slug, "preview": str(prev), "cover": str(pcover), "preview_mb": round(prev.stat().st_size / 1e6, 2),
                          "duration_s": meta.get("duration_s"), "line": " / ".join(meta.get("lines", [])[:1]),
                          "music": (meta.get("music") or {}).get("title", "")}))


if __name__ == "__main__":
    main(sys.argv[1:])
