"""Fetch CC-licensed / public-domain wildlife VIDEO clips from Wikimedia Commons.

Usage:  python scripts/fetch_commons_video.py "tiger" "kingfisher" ...
Writes  assets/video/<slug>/<n>.webm  and  assets/video/<slug>/credits.json

Downloads a Commons transcode (720p or 480p) rather than the original. Keeps
CC0 / PD / CC BY / CC BY-SA only, 4–240 s long, with the species in the title.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "video"
API = "https://commons.wikimedia.org/w/api.php"
UA = "WildlifeEduContentBot/0.2 (local research project; Instagram_test on GitHub)"
PER_SPECIES = 3
OK_LICENSE = re.compile(r"^(cc0|cc-by(-sa)?-\d|cc by|pd|public domain)", re.I)
BAD = re.compile(r"(zoo show|circus|slaughter|hunting trophy|taxiderm|museum|cartoon|animation|"
                 r"diagram|lecture|interview|news|trailer|game)", re.I)
PREFERRED = ["720p.vp9.webm", "720p.webm", "480p.vp9.webm", "480p.webm", "360p.vp9.webm", "360p.webm"]


def get(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=180)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(8 * (attempt + 1))
                continue
            raise


def api(params):
    params = {"format": "json", "formatversion": "2", **params}
    return json.load(get(API + "?" + urllib.parse.urlencode(params)))


def strip_html(s):
    return re.sub(r"<[^>]+>", "", str(s) if s is not None else "").strip()


def candidates(species, words):
    data = api({
        "action": "query", "generator": "search", "gsrsearch": f"{species} filetype:video",
        "gsrnamespace": "6", "gsrlimit": "40",
        "prop": "videoinfo", "viprop": "url|size|mediatype|extmetadata|derivatives",
        "viextmetadatafilter": "LicenseShortName|Artist|ImageDescription",
    })
    out = []
    for p in data.get("query", {}).get("pages", []):
        vi = (p.get("videoinfo") or [None])[0]
        if not vi:
            continue
        meta = {k: strip_html(v.get("value")) for k, v in vi.get("extmetadata", {}).items()}
        lic = meta.get("LicenseShortName", "")
        title = p["title"]
        dur = float(vi.get("duration") or 0)
        if not OK_LICENSE.match(lic) or not (4 <= dur <= 240):
            continue
        if not any(w in title.lower() for w in words) or BAD.search(title):
            continue
        derivs = {d["src"].split(".")[-3] + "." + ".".join(d["src"].split(".")[-2:]): d["src"]
                  for d in vi.get("derivatives", []) if d.get("src")}
        src = next((s for key in PREFERRED for k, s in derivs.items() if k.endswith(key)), None)
        if not src:
            continue
        out.append({"title": title, "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}",
                    "src": src, "duration": round(dur, 1), "width": vi.get("width"), "height": vi.get("height"),
                    "license": lic, "artist": meta.get("Artist", "")[:120],
                    "description": meta.get("ImageDescription", "")[:300]})
    out.sort(key=lambda c: (-(c["width"] or 0), abs(c["duration"] - 30)))
    return out


def main(args):
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in args:
        species, _, extra = spec.partition("=")
        words = [species.lower()] + [w.strip().lower() for w in extra.split(",") if w.strip()]
        slug = re.sub(r"[^a-z0-9]+", "-", species.lower()).strip("-")
        d = OUT / slug
        d.mkdir(exist_ok=True)
        if (d / "credits.json").exists():
            print(f"{slug}: already fetched")
            continue
        try:
            picks = candidates(species, words)[:PER_SPECIES]
        except urllib.error.HTTPError as e:
            print(f"{slug}: search failed {e.code}")
            continue
        credits = []
        for i, c in enumerate(picks, 1):
            dest = d / f"{i:02d}.webm"
            try:
                with get(c["src"]) as r, open(dest, "wb") as f:
                    f.write(r.read())
            except Exception as e:  # noqa: BLE001
                print(f"  {slug} {i}: download failed {e}")
                continue
            c["file"] = dest.name
            credits.append(c)
            print(f"{slug}: {dest.name} {c['license']:14} {c['duration']:6.1f}s {c['width']}x{c['height']}  {c['title'][:70]}")
            time.sleep(2)
        (d / "credits.json").write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
        if not credits:
            print(f"{slug}: NO SUITABLE VIDEO")
        time.sleep(2)


if __name__ == "__main__":
    main(sys.argv[1:])
