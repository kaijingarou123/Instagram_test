"""Build the Reels music library from public-domain / CC0 recordings on Wikimedia Commons.

Usage:  python scripts/fetch_commons_music.py            # fetch every LIBRARY entry not yet in assets/music/
        python scripts/fetch_commons_music.py --list     # show the library with licences and moods

Writes assets/music/<slug>.<ext> and assets/music/library.json (title, page, licence, performer, moods).

Why not chart / trending tracks: they are commercial music. platform-guardrails forbids them (Instagram business
accounts have no licence for them; Rights Manager mutes or blocks the Reel). Allowed music is own/CC0 (public domain
counts) or Meta Sound Collection. The pieces below are the classic "nature documentary" repertoire, composed long ago
and recorded by performers who released the recording into the public domain (Musopen, US military bands, PDM).
A licence is re-checked at fetch time; anything not PD/CC0/PDM is skipped.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commons_video import api, get, strip_html  # noqa: E402  (same UA, 429 back-off)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "music"
OK = re.compile(r"^(cc0|pd|public domain)", re.I)          # PD, PDM-owner, Public domain, CC0

# slug, Commons search, text the title must contain, moods (used to match a track to a Reel)
LIBRARY = [
    ("morning-mood", "Musopen Morning Grieg", "Musopen - Morning", ["calm", "dawn", "birds", "wonder", "india"]),
    ("hall-of-the-mountain-king", "Peer Gynt Mountain King Musopen", "Mountain Kin", ["tension", "stalking", "predator", "build"]),
    ("anitras-dance", "Peer Gynt Anitra Musopen", "Anitra", ["playful", "curious", "light"]),
    ("flight-of-the-bumblebee-band", "Flight of the Bumblebee Air Force Band", "Concert Band", ["frantic", "insects", "chase", "tiny"]),
    ("flight-of-the-bumblebee-piano", "Jaan Patterson Flight of the Bumblebee", "Jaan Patterson", ["frantic", "insects", "tiny"]),
    ("vivaldi-spring-allegro", "Modena Chamber Orchestra Vivaldi Spring Allegro", "Spring, RV 269 - I. Allegro", ["bright", "birds", "lively"]),
    ("vivaldi-summer-presto", "Modena Chamber Orchestra Vivaldi Summer Presto", "Summer, RV 315 - III. Presto", ["storm", "action", "hunt", "drama"]),
    ("vivaldi-winter-allegro", "Modena Chamber Orchestra Vivaldi Winter Allegro", "Winter, RV 297 - I.", ["tense", "cold", "urgent"]),
    ("vivaldi-winter-largo", "Modena Chamber Orchestra Vivaldi Winter Largo", "Winter, RV 297 - II. Largo", ["calm", "warm", "gentle"]),
    ("vivaldi-autumn-adagio", "Modena Chamber Orchestra Vivaldi Autumn Adagio", "Autumn, RV 293 - II", ["mysterious", "slow", "night"]),
    ("gymnopedie-1", "Gymnopedie No. 1", "Gymnopedie No. 1..ogg", ["gentle", "wonder", "slow", "tall"]),
    ("clair-de-lune", "Clair de Lune Debussy piano solo 1905", "Clair de Lune by Claude Debussy (1905", ["night", "ocean", "dreamy"]),
    ("the-swan", "Alisa Weilerstein Swan Saint-Saens", "Weilerstein", ["graceful", "water", "birds", "display"]),
    ("swan-lake-act-2", "Tchaikovsky Swan Lake Extract from Act 2", "Swan Lake- Extract from Act 2", ["dramatic", "epic", "display"]),
]


def find(search, contains):
    pages = api({"action": "query", "generator": "search", "gsrsearch": f"{search} filetype:audio",
                 "gsrnamespace": "6", "gsrlimit": "20", "prop": "imageinfo",
                 "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription"}
                ).get("query", {}).get("pages", [])
    for p in pages:
        ii = (p.get("imageinfo") or [None])[0]
        if not ii or contains.lower() not in p["title"].lower() or p["title"].endswith(".mid"):
            continue
        meta = {k: strip_html(v.get("value")) for k, v in ii.get("extmetadata", {}).items()}
        if OK.match(meta.get("LicenseShortName", "")) and ii["size"] < 60e6:
            return p["title"], ii, meta
    return None


def main(args):
    OUT.mkdir(parents=True, exist_ok=True)
    lib_p = OUT / "library.json"
    lib = json.loads(lib_p.read_text(encoding="utf-8")) if lib_p.exists() else []
    if args[:1] == ["--list"]:
        for t in lib:
            print(f"{t['slug']:30} {t['license']:14} {', '.join(t['moods'])}")
        return
    have = {t["slug"] for t in lib}
    for slug, search, contains, moods in LIBRARY:
        if slug in have:
            continue
        try:
            hit = find(search, contains)
        except Exception as e:  # noqa: BLE001  (429 after retries: skip, the next run picks it up)
            print(f"{slug}: search failed ({e}); run again later")
            time.sleep(10)
            continue
        if not hit:
            print(f"{slug}: no PD/CC0 match")
            time.sleep(3)
            continue
        title, ii, meta = hit
        dest = OUT / f"{slug}{Path(ii['url']).suffix.lower()}"
        try:
            with get(ii["url"]) as r:
                data = r.read()
        except Exception as e:  # noqa: BLE001
            print(f"{slug}: download failed ({e}); run again later")
            time.sleep(10)
            continue
        dest.write_bytes(data)
        lib.append({"slug": slug, "file": dest.name, "title": title,
                    "page": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
                    "license": meta.get("LicenseShortName", ""), "artist": meta.get("Artist", "")[:160],
                    "moods": moods})
        lib_p.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{slug}: {meta.get('LicenseShortName')}  {ii['size'] // 1000} kB  {title}")
        time.sleep(6)


if __name__ == "__main__":
    main(sys.argv[1:])
