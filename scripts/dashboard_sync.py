"""Build the documents behind the live insight dashboard (a claude.ai Artifact with a shared database).

    python scripts/dashboard_sync.py record-metrics <readings.json>   # append a run's Instagram readings to the logs
    python scripts/dashboard_sync.py build          # write every document to log/dashboard/out/, list changed ones
    python scripts/dashboard_sync.py batches        # the changed documents as ArtifactData batch writes
    python scripts/dashboard_sync.py mark-synced    # after a successful push: remember what the dashboard now holds
    python scripts/dashboard_sync.py thumbs         # slide strips for new posts -> log/dashboard/thumbs/<slug>.jpg

`build` reads only local files: post specs and render output, log/posts.jsonl, log/queue.json, log/insights.jsonl,
log/account.jsonl, the research docs, CHECKLIST.md, git history, and the insight agent's own files in log/agent/.
It prints a JSON manifest of documents whose content changed since the last `mark-synced`
(log/dashboard/changed.json holds the same list). The insight agent pushes those with ArtifactData `batch`
(file_path entries), then runs `mark-synced`. Nothing here talks to Instagram or claude.ai.

Account-specific values live in config.json and log/dashboard/config.json, so the pipeline can move to
another account by changing those two files.
"""
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "log"
AGENT = LOG / "agent"
DASH = LOG / "dashboard"
OUT = DASH / "out"
THUMBS = DASH / "thumbs"
SYNCED = DASH / "synced.json"
CHANGED = DASH / "changed.json"
HALTS = [LOG / "HALT", ROOT / "HALT", Path.home() / ".claude" / "platform-guardrails" / "HALT"]
GUARDRAILS = Path.home() / ".claude" / "plugins" / "cache" / "muddy-lessons-claude" / "platform-guardrails"
IST = timezone(timedelta(hours=5, minutes=30))


def now():
    return datetime.now(timezone.utc)


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def read_jsonl(p):
    p = Path(p)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def doc_id(s):
    return re.sub(r"[^A-Za-z0-9_\-.~:@+]", "-", str(s))[:120] or "x"


# ---------------------------------------------------------------- posts

def post_specs():
    """Every carousel and reel the pipeline has rendered, keyed by slug."""
    out = {}
    for d in sorted((ROOT / "output" / "carousels").glob("*/")):
        meta = read_json(d / "meta.json")
        if not meta:
            continue
        spec = read_json(ROOT / "content" / "posts" / f"{d.name}.json", {})
        cover = (spec.get("slides") or [{}])[0]
        out[d.name] = {
            "kind": "carousel", "meta": meta, "caption": (d / "caption.txt").read_text(encoding="utf-8") if (d / "caption.txt").exists() else "",
            "headline": cover.get("headline") or d.name, "kicker": cover.get("kicker", ""),
            "plan": read_json(d / "publish-plan.json"),
        }
    for m in sorted((ROOT / "output" / "reels").glob("*-meta.json")):
        slug = m.name[: -len("-meta.json")]
        meta = read_json(m, {})
        spec = read_json(ROOT / "content" / "reels" / f"{slug}.json", {})
        first = (spec.get("scenes") or [{}])[0]
        cap = ROOT / "output" / "reels" / f"{slug}-caption.txt"
        out[slug] = {
            "kind": "reel", "meta": meta, "caption": cap.read_text(encoding="utf-8") if cap.exists() else "",
            "headline": first.get("headline") or slug, "kicker": first.get("kicker", ""), "plan": None,
        }
    return out


def metric_history():
    hist = defaultdict(list)
    for r in read_jsonl(LOG / "insights.jsonl"):
        keep = {k: r.get(k) for k in ("fetched_at", "age_hours", "reach", "saved", "shares", "likes", "comments",
                                      "views", "total_interactions", "follows", "profile_visits", "permalink") if r.get(k) is not None}
        hist[r["slug"]].append(keep)
    for v in hist.values():
        v.sort(key=lambda x: x.get("fetched_at", ""))
    return hist


def rate(n, d):
    return round(n / d, 4) if d else None


def build_posts(specs, published, queue, hist, thumbs, takeaways):
    order = queue.get("order", [])
    pub = {p["slug"]: p for p in published}
    docs = {}
    for slug, s in specs.items():
        meta = s["meta"]
        p = pub.get(slug)
        h = hist.get(slug, [])
        latest = h[-1] if h else {}
        if p:
            status = "published"
        elif slug in order:
            status = "queued"
        else:
            status = "draft"
        reach = latest.get("reach") or 0
        doc = {
            "slug": slug, "kind": s["kind"], "status": status, "headline": s["headline"], "kicker": s["kicker"],
            "caption": s["caption"], "hashtags": meta.get("hashtags", []), "format_tags": meta.get("format_tags", []),
            "sources": meta.get("sources", []), "photo_credits": sorted(set(meta.get("photo_credits", []))),
            "alt_texts": meta.get("alt_texts", []), "slide_count": len(meta.get("slides", [])) or meta.get("scenes"),
            "duration_s": meta.get("duration_s"), "caption_chars": meta.get("caption_chars"),
            "queue_position": (order.index(slug) + 1) if slug in order and not p else None,
            "thumb": thumbs.get(slug), "metrics": latest, "history": h[-60:],
            "save_rate": rate(latest.get("saved") or 0, reach), "share_rate": rate(latest.get("shares") or 0, reach),
            "takeaway": takeaways.get(slug),
            "checks_passed": (s["plan"] or {}).get("checks_passed"),
            "checked_at": (s["plan"] or {}).get("generated_at"),
        }
        if p:
            doc.update({"published_at": p.get("published_at"), "media_id": p.get("media_id"),
                        "permalink": p.get("permalink") or latest.get("permalink"), "route": p.get("route"), "via": p.get("via"),
                        "publish_notes": p.get("notes")})
        docs[doc_id(slug)] = doc
    return docs


# ---------------------------------------------------------------- state

def halt_text():
    for h in HALTS:
        if h.exists():
            return h.read_text(encoding="utf-8", errors="replace").strip() or "HALT marker present"
    return None


def schedule_estimate(queue, published_slugs):
    """Rough dates for the rest of the queue: next_due, then ~26 h apart (post_queue.py draws 24-28 h)."""
    left = [s for s in queue.get("order", []) if s not in published_slugs]
    nd = queue.get("next_due")
    if not nd:
        return []
    t = datetime.fromisoformat(nd)
    rows = []
    for i, slug in enumerate(left):
        rows.append({"slug": slug, "position": i + 1, "due": t.isoformat(), "estimated": i > 0})
        t += timedelta(hours=26)
    return rows


def build_state(cfg, published, queue, posts, account, hist):
    start = datetime.fromisoformat(cfg["account_start_date"]).replace(tzinfo=timezone.utc)
    day = (now() - start).days
    phase = 1 if day < 14 else 2 if day < 28 else 3
    phase_rules = {1: "1 post per day, 20 h gap, no Reels", 2: "2 posts per day, 8 h gap, up to 2 Reels a week",
                   3: "3 posts per day ceiling, 6 h gap, up to 4 Reels a week"}[phase]
    acct = account[-1] if account else {}
    prev = next((a for a in reversed(account[:-1]) if (now() - datetime.fromisoformat(a["fetched_at"])).days >= 6), None) if account else None
    pubs = [p for p in posts.values() if p["status"] == "published"]
    tot = Counter()
    for p in pubs:
        for k in ("reach", "saved", "shares", "likes", "comments", "views"):
            tot[k] += p["metrics"].get(k) or 0
    sched = schedule_estimate(queue, {p["slug"] for p in published})
    return {
        "handle": cfg.get("ig_username"), "account_start_date": cfg["account_start_date"], "account_day": day,
        "phase": phase, "phase_rules": phase_rules,
        "followers": acct.get("followers_count"), "following": acct.get("follows_count"),
        "media_count": acct.get("media_count"), "followers_7d_ago": (prev or {}).get("followers_count"),
        "account_fetched_at": acct.get("fetched_at"),
        "published_count": len(pubs), "queued_count": sum(1 for p in posts.values() if p["status"] == "queued"),
        "draft_count": sum(1 for p in posts.values() if p["status"] == "draft"),
        "totals": dict(tot), "save_rate": rate(tot["saved"], tot["reach"]), "share_rate": rate(tot["shares"], tot["reach"]),
        "next_post": sched[0] if sched else None, "queue_end": sched[-1]["due"] if sched else None,
        "halt": halt_text(), "metrics_fetched_at": max((h[-1].get("fetched_at", "") for h in hist.values() if h), default=None),
        "built_at": now().isoformat(),
    }


# ---------------------------------------------------------------- agent-owned collections

def agent_items(name):
    """log/agent/<name>.json is a list of objects with an `id`. The insight agent edits these files."""
    items = read_json(AGENT / f"{name}.json", []) or []
    return {doc_id(i["id"]): i for i in items if isinstance(i, dict) and i.get("id")}


# ---------------------------------------------------------------- audience, hashtags, library

def build_audience(account, posts):
    series = [{"at": a["fetched_at"], "followers": a.get("followers_count"), "following": a.get("follows_count"),
               "media": a.get("media_count"), "profile_views": a.get("profile_views"), "reach": a.get("reach"),
               "accounts_engaged": a.get("accounts_engaged")} for a in account][-180:]
    tags = defaultdict(lambda: {"posts": [], "queued": 0, "reach": 0, "saved": 0, "shares": 0})
    hours = defaultdict(lambda: {"posts": 0, "reach": 0})
    for p in posts.values():
        for t in p["hashtags"]:
            row = tags[t.lower()]
            if p["status"] == "published":
                row["posts"].append(p["slug"])
                row["reach"] += p["metrics"].get("reach") or 0
                row["saved"] += p["metrics"].get("saved") or 0
                row["shares"] += p["metrics"].get("shares") or 0
            elif p["status"] == "queued":
                row["queued"] += 1
        if p["status"] == "published" and p.get("published_at"):
            h = datetime.fromisoformat(p["published_at"]).astimezone(IST).hour
            hours[h]["posts"] += 1
            hours[h]["reach"] += p["metrics"].get("reach") or 0
    hashtag_rows = []
    for t, r in tags.items():
        n = len(r["posts"])
        hashtag_rows.append({"tag": t, "used": n, "queued": r["queued"], "avg_reach": round(r["reach"] / n, 1) if n else None,
                             "save_rate": rate(r["saved"], r["reach"]), "posts": r["posts"]})
    hashtag_rows.sort(key=lambda r: (-r["used"], -(r["avg_reach"] or 0), -r["queued"], r["tag"]))
    hour_rows = [{"hour_ist": h, "posts": v["posts"], "avg_reach": round(v["reach"] / v["posts"], 1)} for h, v in sorted(hours.items())]
    return {"followers": series, "hashtags": hashtag_rows, "posting_hours": hour_rows, "built_at": now().isoformat()}


def licence_of(credit):
    m = re.search(r"(CC[ -]?BY(?:-SA)?[ \d.]*|CC0[ \d.]*|Public domain)", credit, re.I)
    return m.group(1).strip() if m else "Other"


def build_library(posts):
    species, fmt, src, lic = [], Counter(), Counter(), Counter()
    for p in posts.values():
        species.append({"slug": p["slug"], "kind": p["kind"], "status": p["status"], "headline": p["headline"],
                        "formats": p["format_tags"], "sources": len(p["sources"]), "credits": len(p["photo_credits"])})
        fmt.update(p["format_tags"])
        for u in p["sources"]:
            src[re.sub(r"^https?://(www\.)?", "", u).split("/")[0]] += 1
        lic.update(licence_of(c) for c in p["photo_credits"])
    return {"items": species, "formats": [{"tag": k, "count": v} for k, v in fmt.most_common()],
            "source_domains": [{"domain": k, "count": v} for k, v in src.most_common()],
            "licences": [{"licence": k, "count": v} for k, v in lic.most_common()], "built_at": now().isoformat()}


# ---------------------------------------------------------------- activity

def git_log(n=200):
    try:
        out = subprocess.run(["git", "log", f"-{n}", "--format=%H|%aI|%an|%s"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8").stdout
    except OSError:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            rows.append({"at": parts[1], "type": "commit", "title": parts[3], "detail": f"{parts[0][:7]} by {parts[2]}"})
    return rows


def build_activity(published):
    ev = git_log()
    for p in published:
        ev.append({"at": p["published_at"], "type": "publish", "title": f"Published {p['slug']}",
                   "detail": f"media {p.get('media_id')} via {p.get('via') or p.get('route')}" + (f". {p['notes']}" if p.get("notes") else "")})
    for a in read_jsonl(AGENT / "activity.jsonl"):
        if a.get("at") and a.get("title"):
            ev.append({k: a.get(k) for k in ("at", "type", "title", "detail")})
    for e in ev:
        e["at"] = datetime.fromisoformat(e["at"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    ev.sort(key=lambda e: e["at"], reverse=True)
    months = defaultdict(list)
    for e in ev:
        months[e["at"][:7]].append(e)
    return {m: {"month": m, "events": v[:400]} for m, v in months.items()}


# ---------------------------------------------------------------- docs

def guardrail_rules_path():
    vers = sorted((p for p in GUARDRAILS.glob("*/") if re.match(r"\d+\.\d+\.\d+$", p.name)),
                  key=lambda p: tuple(int(x) for x in p.name.split(".")))
    for v in reversed(vers):
        f = v / "skills" / "platform-guardrails" / "RULES.md"
        if f.exists():
            return f
    return None


def build_docs():
    docs = {}
    entries = [
        ("checklist", "Pre-post checklist", "CHECKLIST.md", "guardrails"),
        ("posting-limits", "Posting limits and API rules", "research/posting-limits.md", "guardrails"),
        ("growth-plan", "Growth plan", "research/growth-plan.md", "plans"),
        ("content-strategy", "Content strategy", "research/content-strategy.md", "plans"),
    ]
    for key, title, rel, group in entries:
        f = ROOT / rel
        if f.exists():
            docs[key] = {"title": title, "group": group, "path": rel, "text": f.read_text(encoding="utf-8")[:240000],
                         "updated": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()}
    r = guardrail_rules_path()
    if r:
        docs["platform-rules"] = {"title": "Platform guardrails (shared skill)", "group": "guardrails",
                                  "path": f"platform-guardrails {r.parent.parent.parent.name}",
                                  "text": r.read_text(encoding="utf-8")[:240000],
                                  "updated": datetime.fromtimestamp(r.stat().st_mtime, timezone.utc).isoformat()}
    house = read_json(DASH / "config.json", {}).get("house_style")
    if house:
        docs["house-style"] = {"title": "House style", "group": "guardrails", "path": "log/dashboard/config.json",
                               "text": house, "updated": None}
    return docs


# ---------------------------------------------------------------- build / diff

def build():
    cfg = read_json(ROOT / "config.json", {})
    published = [p for p in read_jsonl(LOG / "posts.jsonl") if p.get("status") == "published"]
    queue = read_json(LOG / "queue.json", {})
    hist = metric_history()
    account = read_jsonl(LOG / "account.jsonl")
    thumbs = read_json(DASH / "thumbs.json", {})
    takeaways = read_json(AGENT / "takeaways.json", {})
    specs = post_specs()
    posts = build_posts(specs, published, queue, hist, thumbs, takeaways)
    state = build_state(cfg, published, queue, posts, account, hist)
    sched = schedule_estimate(queue, {p["slug"] for p in published})

    coll = {
        "dash": {"state": state,
                 "pipeline": {"schedule": sched, "queue_note": "Dates after the first are estimates (24 to 28 h gaps, 08:00 to 21:30 IST window).",
                              "built_at": now().isoformat()},
                 "audience": build_audience(account, posts),
                 "library": build_library(posts)},
        "posts": posts,
        "insights": agent_items("insights"),
        "plans": agent_items("plans"),
        "experiments": agent_items("experiments"),
        "competitors": agent_items("competitors"),
        "connectors": agent_items("connectors"),
        "decisions": agent_items("decisions"),
        "activity": build_activity(published),
        "docs": build_docs(),
    }

    synced = read_json(SYNCED, {})
    changed, current = [], {}
    for c, docs in coll.items():
        (OUT / c).mkdir(parents=True, exist_ok=True)
        for d, body in docs.items():
            text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True)
            path = OUT / c / f"{d}.json"
            path.write_text(text, encoding="utf-8")
            # build stamps change every run; leave them out of the hash so unchanged docs are not re-pushed
            h = hashlib.sha1(re.sub(r'"built_at": "[^"]*"', "", text).encode()).hexdigest()
            current[f"{c}/{d}"] = h
            if synced.get(f"{c}/{d}") != h:
                changed.append({"collection": c, "doc_id": d, "file_path": str(path)})
    removed = [k for k in synced if k not in current]
    manifest = {"built_at": now().isoformat(), "changed": changed,
                "removed": [{"collection": k.rsplit("/", 1)[0], "doc_id": k.rsplit("/", 1)[1]} for k in removed],
                "hashes": current}
    CHANGED.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"changed": len(changed), "removed": len(removed),
                      "docs": [f"{x['collection']}/{x['doc_id']}" for x in changed],
                      "removed_docs": [f"{x['collection']}/{x['doc_id']}" for x in manifest["removed"]]}, indent=1))


def record_metrics():
    """Append one run's readings to log/insights.jsonl and log/account.jsonl.

    Input: a JSON file {"account": {followers_count, follows_count, media_count, reach, accounts_engaged, profile_views},
    "posts": [{"media_id", "permalink"?, "metrics": {reach, saved, shares, likes, comments, total_interactions, views}}]}.
    Slugs come from log/posts.jsonl by media_id; unknown media ids are skipped and reported."""
    if len(sys.argv) < 3:
        sys.exit("usage: dashboard_sync.py record-metrics <readings.json>")
    data = read_json(sys.argv[2])
    if not data:
        sys.exit("could not read " + sys.argv[2])
    t = now()
    pub = {p["media_id"]: p for p in read_jsonl(LOG / "posts.jsonl") if p.get("status") == "published"}
    done, skipped = [], []
    with (LOG / "insights.jsonl").open("a", encoding="utf-8") as f:
        for r in data.get("posts", []):
            p = pub.get(str(r.get("media_id")))
            if not p:
                skipped.append(r.get("media_id"))
                continue
            age = (t - datetime.fromisoformat(p["published_at"])).total_seconds() / 3600
            row = {"fetched_at": t.isoformat(), "slug": p["slug"], "kind": p["kind"], "media_id": p["media_id"],
                   "age_hours": round(age, 1), "source": "composio", **({"permalink": r["permalink"]} if r.get("permalink") else {}),
                   **{k: v for k, v in (r.get("metrics") or {}).items() if v is not None}}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            done.append(p["slug"])
    a = data.get("account")
    if a:
        with (LOG / "account.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"fetched_at": t.isoformat(), "window": "last 24 h", "source": "composio", **a}, ensure_ascii=False) + "\n")
    print(json.dumps({"recorded_posts": done, "skipped_media_ids": skipped, "account": bool(a)}))


def batches():
    """Print the changed documents as ready-to-use ArtifactData batch `writes` lists (at most 40 per batch).
    Entries for documents that already exist need `if_version` added from a list/get of that collection."""
    m = read_json(CHANGED)
    if not m:
        sys.exit("run build first")
    w = [{"op": "set", "collection": c["collection"], "doc_id": c["doc_id"], "file_path": c["file_path"].replace("\\", "/"),
          "new": c["collection"] + "/" + c["doc_id"] not in read_json(SYNCED, {})} for c in m["changed"]]
    w += [{"op": "delete", "collection": r["collection"], "doc_id": r["doc_id"], "new": False} for r in m["removed"]]
    for i in range(0, len(w), 40):
        print(json.dumps(w[i:i + 40], ensure_ascii=False))


def mark_synced():
    m = read_json(CHANGED)
    if not m:
        sys.exit("run build first")
    SYNCED.write_text(json.dumps(m["hashes"], indent=1), encoding="utf-8")
    print(f"marked {len(m['hashes'])} documents as synced")


def thumbs():
    """One horizontal strip of slides per post (240 px tall), only for posts without one yet."""
    from PIL import Image
    THUMBS.mkdir(parents=True, exist_ok=True)
    made = []
    for slug, s in post_specs().items():
        out = THUMBS / f"{slug}.jpg"
        if out.exists():
            continue
        if s["kind"] == "carousel":
            files = [ROOT / "output" / "carousels" / slug / f for f in s["meta"].get("slides", [])]
        else:
            files = [ROOT / "output" / "reels" / f"{slug}-cover.jpg"]
        ims = []
        for f in files:
            if f.exists():
                im = Image.open(f).convert("RGB")
                im.thumbnail((10000, 240))
                ims.append(im)
        if not ims:
            continue
        gap = 6
        strip = Image.new("RGB", (sum(i.width for i in ims) + gap * (len(ims) - 1), 240), (20, 24, 22))
        x = 0
        for im in ims:
            strip.paste(im, (x, 0))
            x += im.width + gap
        strip.save(out, quality=78, optimize=True)
        made.append(str(out))
    print(json.dumps(made, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "record-metrics": record_metrics, "batches": batches, "mark-synced": mark_synced, "thumbs": thumbs}.get(cmd, lambda: sys.exit(__doc__))()
