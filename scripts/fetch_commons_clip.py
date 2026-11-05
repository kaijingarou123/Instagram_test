"""Download a 1080p (or best <= 1080p) transcode of a CC-licensed Wikimedia Commons video into assets/video.

Usage:  python scripts/fetch_commons_clip.py <folder> "<search words>" "<title must contain>" [...more triples]
Writes assets/video/<folder>/NN.webm and appends to assets/video/<folder>/credits.json in the same shape the Reel
renderers read: {file, title, page, src, duration, width, height, license, artist, description}.
Only CC0, CC BY, CC BY-SA and public-domain files are accepted. Captive or zoo footage is refused.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VID = ROOT / "assets" / "video"
API = "https://commons.wikimedia.org/w/api.php"
UA = "EarthspiritReelBuilder/1.0 (educational wildlife account; contact via project owner)"
OK_LIC = ("CC0", "CC BY", "Public domain", "PD")
BAD = ("zoo", "aquarium", "captive", "tierpark", "wildpark", "gehege", "farm")


def get(url, tries=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (i + 1))
                continue
            raise


def api(**p):
    return json.load(get(API + "?" + urllib.parse.urlencode({"format": "json", "formatversion": "2", **p})))


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def find(search, contains):
    d = api(action="query", generator="search", gsrnamespace="6", gsrlimit="40", gsrsearch="filetype:video " + search,
            prop="videoinfo", viprop="size|url|extmetadata|derivatives|mediatype")
    for pg in d.get("query", {}).get("pages", []):
        if contains.lower() in pg["title"].lower():
            return pg
    raise SystemExit(f"not found: {search!r} containing {contains!r}")


def main(args):
    for folder, search, contains in zip(args[0::3], args[1::3], args[2::3]):
        pg = find(search, contains)
        vi = pg["videoinfo"][0]
        meta = vi.get("extmetadata", {})
        lic = strip(meta.get("LicenseShortName", {}).get("value"))
        title = pg["title"]
        if not lic.startswith(OK_LIC):
            raise SystemExit(f"{title}: licence {lic!r} not allowed")
        if any(b in title.lower() for b in BAD):
            raise SystemExit(f"{title}: looks captive, refused")
        ders = [d for d in vi.get("derivatives", []) if "webm" in d.get("type", "") and d.get("height", 0) <= 1080]
        best = max(ders, key=lambda d: d.get("height", 0)) if ders else {"src": vi["url"], "height": vi["height"], "width": vi["width"]}
        dest_dir = VID / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        cred_path = dest_dir / "credits.json"
        credits = json.loads(cred_path.read_text(encoding="utf-8")) if cred_path.exists() else []
        if any(c["title"] == title for c in credits):
            print(f"{folder}: already have {title}")
            continue
        name = f"{len(credits) + 1:02d}.webm"
        with get(best["src"]) as r, open(dest_dir / name, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        credits.append({"file": name, "title": title, "page": vi.get("descriptionurl", ""), "src": best["src"],
                        "duration": vi.get("duration"), "width": best.get("width"), "height": best.get("height"),
                        "license": lic, "artist": strip(meta.get("Artist", {}).get("value"))[:120],
                        "description": strip(meta.get("ImageDescription", {}).get("value"))[:400]})
        cred_path.write_text(json.dumps(credits, indent=1, ensure_ascii=False), encoding="utf-8")
        mb = (dest_dir / name).stat().st_size / 1e6
        print(f"{folder}/{name}: {title[5:70]} | {best.get('height')}p | {lic} | {mb:.1f} MB")
        time.sleep(2)


if __name__ == "__main__":
    main(sys.argv[1:])
