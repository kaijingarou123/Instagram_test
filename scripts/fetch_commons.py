"""Fetch CC-licensed / public-domain wildlife photos from Wikimedia Commons.

Usage:  python scripts/fetch_commons.py "snow leopard" "axolotl" ...
Writes  assets/raw/<slug>/<n>.jpg  and  assets/raw/<slug>/credits.json

Only keeps files whose license is CC0 / CC BY / CC BY-SA / public domain,
with a long edge >= MIN_PX, whose title/description mentions the species,
preferring Commons "Quality images" / "Featured pictures".
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
RAW = ROOT / "assets" / "raw"
API = "https://commons.wikimedia.org/w/api.php"
UA = "WildlifeEduContentBot/0.1 (local research project; contact via Composio test account)"
MIN_PX = 1600          # long edge of the original
FETCH_WIDTH = 1920     # a Wikimedia standard thumbnail step (non-standard sizes get throttled)
PER_SPECIES = 4
OK_LICENSE = re.compile(r"^(cc0|cc-by(-sa)?-\d|cc by|pd|public domain)", re.I)
BAD_WORDS = re.compile(r"(\bmap\b|range|skeleton|skull|diagram|drawing|illustration|painting|"
                       r"stamp|logo|svg|taxidermy|museum|fur skin|\bskin\b|pelt|coin|statue|"
                       r"sculpture|toy|costume|chart|anatomy|dissect|mhnt|specimen)", re.I)

# common name -> (Commons taxon category, alternative words that count as a match)
TAXA = {
    "snow leopard": ("Panthera uncia", ["uncia"]),
    "axolotl": ("Ambystoma mexicanum", ["ambystoma"]),
    "pangolin": ("Pholidota", ["manis", "phataginus", "smutsia"]),
    "mantis shrimp": ("Stomatopoda", ["odontodactylus", "stomatopod", "lysiosquillina"]),
    "octopus": ("Octopoda", ["octopus"]),
    "hummingbird": ("Trochilidae", ["hummingbird", "colibri", "archilochus", "calypte", "selasphorus"]),
    "barn owl": ("Tyto alba", ["tyto"]),
    "honey bee": ("Apis mellifera", ["apis mellifera", "honeybee", "honey bee"]),
    "orca": ("Orcinus orca", ["orcinus", "killer whale"]),
}


def api(params):
    params = {"format": "json", "formatversion": "2", **params}
    url = API + "?" + urllib.parse.urlencode(params)
    return json.load(get(url))


def get(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                wait = int(e.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
                print(f"  429 from Commons, waiting {wait}s")
                time.sleep(wait)
                continue
            raise


def search(query, limit=50):
    data = api({
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|mime",
        "iiurlwidth": str(FETCH_WIDTH),
        "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription|Credit",
    })
    return data.get("query", {}).get("pages", [])


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def candidates(species):
    taxon, alts = TAXA.get(species, (species, []))
    words = [species.lower(), taxon.lower(), *[a.lower() for a in alts]]
    seen, out = set(), []
    queries = [
        f'deepcat:"{taxon}" incategory:"Quality images"',
        f'deepcat:"{taxon}" incategory:"Featured pictures on Wikimedia Commons"',
        f'deepcat:"{taxon}" filetype:bitmap',
        f'"{species}" filetype:bitmap',
    ]
    for q in queries:
        curated = "incategory" in q
        try:
            pages = search(q)
        except urllib.error.HTTPError as e:
            print(f"  search failed ({e.code}) for {q}")
            pages = []
        for p in pages:
            if p["pageid"] in seen or not p.get("imageinfo"):
                continue
            seen.add(p["pageid"])
            ii = p["imageinfo"][0]
            meta = {k: strip_html(v.get("value")) for k, v in ii.get("extmetadata", {}).items()}
            lic = meta.get("LicenseShortName", "")
            text = (p["title"] + " " + meta.get("ImageDescription", "")).lower()
            if TITLE_ONLY:
                text = p["title"].lower()
            if ii.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if not OK_LICENSE.match(lic):
                continue
            if max(ii["width"], ii["height"]) < MIN_PX:
                continue
            if not any(w in text for w in words):
                continue
            if BAD_WORDS.search(text[:400]):
                continue
            out.append({
                "title": p["title"],
                "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(p['title'])}",
                "thumb": ii.get("thumburl", ii["url"]),
                "width": ii["width"], "height": ii["height"],
                "license": lic,
                "artist": meta.get("Artist", "")[:120],
                "credit": meta.get("Credit", "")[:120],
                "description": meta.get("ImageDescription", "")[:300],
                "curated": curated,
            })
        if len([c for c in out if c["curated"]]) >= PER_SPECIES:
            break
        time.sleep(1.0)
    out.sort(key=lambda c: (not c["curated"], -(c["width"] * c["height"])))
    return out


def download(url, dest):
    with get(url) as r, open(dest, "wb") as f:
        f.write(r.read())


def main(species_list):
    RAW.mkdir(parents=True, exist_ok=True)
    for species in species_list:
        slug = re.sub(r"[^a-z0-9]+", "-", species.lower()).strip("-")
        d = RAW / slug
        d.mkdir(exist_ok=True)
        cj = d / "credits.json"
        if cj.exists() and len(json.loads(cj.read_text(encoding="utf-8"))) >= 3 and "--refresh" not in sys.argv:
            print(f"{slug}: already fetched")
            continue
        for old in d.glob("*"):          # start clean so stale picks don't linger
            old.unlink()
        picks = candidates(species)[:PER_SPECIES]
        credits = []
        for i, c in enumerate(picks, 1):
            ext = ".png" if c["thumb"].lower().endswith(".png") else ".jpg"
            dest = d / f"{i:02d}{ext}"
            download(c["thumb"], dest)
            time.sleep(4)
            c["file"] = dest.name
            credits.append(c)
            print(f"{slug}: {dest.name}  {c['license']:14} {c['width']}x{c['height']}  {c['title']}")
        (d / "credits.json").write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
        if not picks:
            print(f"{slug}: NO SUITABLE IMAGES")


TITLE_ONLY = False

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--title-only" in args:          # stricter: species must appear in the file title
        TITLE_ONLY = True
        args.remove("--title-only")
    main(args)
