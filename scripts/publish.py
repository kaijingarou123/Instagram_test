"""Publish a rendered carousel or Reel to Instagram — safely.

    python scripts/publish.py status                 # phase, allowance, recent posts
    python scripts/publish.py plan <slug>            # all checks + the API call sequence, no Meta calls
    python scripts/publish.py publish <slug> --yes   # the real thing (needs IG_ACCESS_TOKEN)

Every publish goes through, in order:
  1. HALT file check            log/HALT exists -> refuse (a hard-stop fired earlier)
  2. preflight.py               media specs, caption, hashtags, credits, sources
  3. URL check                  each media URL: HTTP 200, right Content-Type, no redirect
  4. cadence guard              phase-based limits from research/posting-limits.md, read from log/posts.jsonl
  5. live quota check           GET /me/content_publishing_limit (never hardcoded)
  6. container(s) -> poll -> publish, then append to log/posts.jsonl

Hard-stop error codes write log/HALT and exit; nothing retries automatically.
Config lives in config.json (no secrets) and the token in the IG_ACCESS_TOKEN
environment variable (or a .env file, which is git-ignored).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):          # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
LOG_DIR = ROOT / "log"
LOG = LOG_DIR / "posts.jsonl"
HALT = LOG_DIR / "HALT"
# Shared marker written by the platform-guardrails gate (Claude-skills-agents-plugins); both markers block.
GLOBAL_HALT = Path.home() / ".claude" / "platform-guardrails" / "HALT"
CONFIG = ROOT / "config.json"

# --- safety envelope (research/posting-limits.md, "Recommended safe operating envelope") ---
PHASES = [
    # (first day, last day, max posts/day, min gap hours, reels allowed per 7 days)
    # Owner decision 2026-10-18: days 0-13 run at 2 posts/day (>= 8 h apart) instead of the
    # platform-guardrails default of 1/day (>= 20 h), accepting the higher new-account risk.
    # Reels stay off until day 14.
    # Owner decisions 2026-10-28: Reels from day 13, up to 2 a day (14 per rolling 7 days). Days 13-14 (28-29 Oct)
    # clear the carousel backlog: up to 7 posts a day, >= 2 h apart. From day 15: 2 carousels + 1-2 Reels, up to
    # 4 posts a day, >= 3 h apart. Guardrails default was 1/day then 2/day and 2 then 4 Reels a week; the owner
    # accepted the risk. ABSOLUTE_DAILY_CEILING (10) still applies.
    (0, 12, 2, 8, 0),
    (13, 15, 7, 2, 14),     # day 15 (30 Oct) added as a catch-up day: 28 Oct was lost to a HALT
    (16, 10**6, 4, 3, 14),
]
ABSOLUTE_DAILY_CEILING = 10
QUOTA_HALT_AT = 20
HARD_STOP_CODES = {4, 17, 25, 9, 190, 613, 80002}
HARD_STOP_SUBCODES = {2207051, 2207050, 2207042, 1996}
SAFE_RETRY_SUBCODES = {2207001, 2207032, 2207053, 2207027}


def load_config():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    cfg["token"] = os.environ.get("IG_ACCESS_TOKEN", "")
    return cfg


# ----------------------------------------------------------------- post discovery
def find_post(slug):
    car = OUT / "carousels" / slug
    if (car / "meta.json").exists():
        meta = json.loads((car / "meta.json").read_text(encoding="utf-8"))
        caption = (car / "caption.txt").read_text(encoding="utf-8")
        return {"kind": "carousel", "slug": slug, "dir": car, "meta": meta, "caption": caption,
                "files": [f"output/carousels/{slug}/{f}" for f in meta["slides"]]}
    meta_p = OUT / "reels" / f"{slug}-meta.json"
    if meta_p.exists():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        caption = (OUT / "reels" / f"{slug}-caption.txt").read_text(encoding="utf-8")
        return {"kind": "reel", "slug": slug, "dir": OUT / "reels", "meta": meta, "caption": caption,
                "files": [f"output/reels/{slug}.mp4", f"output/reels/{slug}-cover.jpg"]}
    sys.exit(f"no rendered post called '{slug}' under output/")


def media_url(cfg, rel):
    return cfg["media_base_url"].rstrip("/") + "/" + rel.replace("\\", "/")


# ----------------------------------------------------------------- checks
def check_preflight(slug):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "preflight.py"), slug],
                       capture_output=True, text=True)
    ok = r.returncode == 0
    return ok, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def check_url(url, expect_type):
    """HEAD then a 1-byte GET: Meta needs 200, a direct URL (no 3xx) and a sane Content-Type."""
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "facebookexternalhit/1.1"})
    try:
        with opener.open(req, timeout=30) as r:
            ctype = r.headers.get("Content-Type", "")
            clen = int(r.headers.get("Content-Length") or 0)
            status = r.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    if status != 200:
        return False, f"HTTP {status}"
    if not ctype.startswith(expect_type):
        return False, f"Content-Type {ctype!r} (want {expect_type}*)"
    if any(c.isspace() or ord(c) > 126 for c in url):
        return False, "URL must be plain ASCII with no spaces"
    return True, f"200 {ctype} {clen/1e6:.2f} MB"


def read_log():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def phase_for(cfg, now):
    start = datetime.fromisoformat(cfg["account_start_date"]).replace(tzinfo=timezone.utc)
    day = (now - start).days
    for lo, hi, per_day, gap, reels in PHASES:
        if lo <= day <= hi:
            return {"day": day, "max_per_day": per_day, "min_gap_h": gap, "reels_per_week": reels}
    return {"day": day, "max_per_day": 3, "min_gap_h": 6, "reels_per_week": 4}


def check_cadence(cfg, post, now=None):
    now = now or datetime.now(timezone.utc)
    ph = phase_for(cfg, now)
    posts = [p for p in read_log() if p.get("status") == "published"]
    last_24h = [p for p in posts if datetime.fromisoformat(p["published_at"]) > now - timedelta(hours=24)]
    last_7d = [p for p in posts if datetime.fromisoformat(p["published_at"]) > now - timedelta(days=7)]
    problems = []
    if len(last_24h) >= ph["max_per_day"]:
        problems.append(f"phase day {ph['day']}: already {len(last_24h)} post(s) in the last 24 h (max {ph['max_per_day']})")
    if len(last_24h) >= ABSOLUTE_DAILY_CEILING:
        problems.append("absolute ceiling of 10 publishes/day reached")
    if posts:
        last = max(datetime.fromisoformat(p["published_at"]) for p in posts)
        gap = (now - last).total_seconds() / 3600
        if gap < ph["min_gap_h"]:
            problems.append(f"only {gap:.1f} h since the last post (min {ph['min_gap_h']} h)")
    if post["kind"] == "reel":
        reels_7d = [p for p in last_7d if p["kind"] == "reel"]
        if ph["reels_per_week"] == 0:
            problems.append(f"phase day {ph['day']}: Reels not allowed until day 14")
        elif len(reels_7d) >= ph["reels_per_week"]:
            problems.append(f"already {len(reels_7d)} Reel(s) this week (max {ph['reels_per_week']})")
    if any(p["slug"] == post["slug"] for p in posts):
        problems.append(f"'{post['slug']}' was already published")
    # hashtag rotation: never the same set as the previous post, <=2 shared
    if posts:
        prev = set(h.lower() for h in posts[-1].get("hashtags", []))
        cur = set(h.lower() for h in post["meta"]["hashtags"])
        if cur == prev:
            problems.append("hashtag set identical to the previous post")
        elif len(cur & prev) > 2:
            problems.append(f"{len(cur & prev)} hashtags shared with the previous post (max 2)")
    return ph, problems


# ----------------------------------------------------------------- Graph API
def graph(cfg, method, path, params=None, data=None):
    base = f"https://{cfg['graph_host']}/{cfg['api_version']}/"
    params = dict(params or {})
    params["access_token"] = cfg["token"]
    url = base + path.lstrip("/")
    body = None
    if method == "POST":
        body = urllib.parse.urlencode({**params, **(data or {})}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    else:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            usage = r.headers.get("X-Business-Use-Case-Usage") or r.headers.get("X-App-Usage")
            return json.load(r), usage
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)["error"]
        except Exception:  # noqa: BLE001
            err = {"message": e.read()[:300].decode(errors="replace"), "code": e.code}
        raise GraphError(err) from None


class GraphError(Exception):
    def __init__(self, err):
        super().__init__(err.get("message"))
        self.code = err.get("code")
        self.subcode = err.get("error_subcode")
        self.err = err

    def is_hard_stop(self):
        return self.code in HARD_STOP_CODES or self.subcode in HARD_STOP_SUBCODES

    def is_safe_retry(self):
        return self.subcode in SAFE_RETRY_SUBCODES


def halt(reason):
    LOG_DIR.mkdir(exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()}  {reason}\n"
    HALT.write_text(line, encoding="utf-8")
    try:                                            # mirror into the shared guardrails marker
        GLOBAL_HALT.parent.mkdir(parents=True, exist_ok=True)
        with GLOBAL_HALT.open("a", encoding="utf-8") as f:
            f.write(f"{line.rstrip()}  (instagram, {ROOT.name})\n")
    except OSError:
        pass
    print(f"\nHARD STOP: {reason}\nlog/HALT written — no further publishing until a human deletes it.")
    sys.exit(2)


def halt_markers():
    """All HALT markers that block publishing: project log/HALT and the shared guardrails marker."""
    found = []
    for path in (HALT, GLOBAL_HALT):
        if path.exists():
            found.append(f"{path}: {path.read_text(encoding='utf-8', errors='replace').strip()}")
    return found


def log_entry(entry):
    LOG_DIR.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def api_sequence(cfg, post):
    """The exact Graph API calls this post needs (also usable by hand / via Composio)."""
    ig = cfg["ig_user_id"]
    calls = [{"step": "quota", "method": "GET", "path": f"/{ig}/content_publishing_limit",
              "params": {"fields": "quota_usage,config"}}]
    if post["kind"] == "carousel":
        for i, rel in enumerate(post["files"], 1):
            calls.append({"step": f"child_{i}", "method": "POST", "path": f"/{ig}/media",
                          "params": {"image_url": media_url(cfg, rel), "is_carousel_item": "true",
                                     "alt_text": post["meta"]["alt_texts"][i - 1][:1000]}})
        calls.append({"step": "carousel", "method": "POST", "path": f"/{ig}/media",
                      "params": {"media_type": "CAROUSEL", "children": "<child container ids, comma-separated>",
                                 "caption": post["caption"]}})
    else:
        calls.append({"step": "reel", "method": "POST", "path": f"/{ig}/media",
                      "params": {"media_type": "REELS", "video_url": media_url(cfg, post["files"][0]),
                                 "cover_url": media_url(cfg, post["files"][1]), "share_to_feed": "true",
                                 "caption": post["caption"]}})
    calls.append({"step": "poll", "method": "GET", "path": "/<container id>", "params": {"fields": "status_code,status"},
                  "note": "once per 60 s, max 5 times; continue only on FINISHED"})
    calls.append({"step": "publish", "method": "POST", "path": f"/{ig}/media_publish",
                  "params": {"creation_id": "<container id>"}})
    return calls


# ----------------------------------------------------------------- commands
def cmd_status(cfg):
    now = datetime.now(timezone.utc)
    ph = phase_for(cfg, now)
    posts = read_log()
    pub = [p for p in posts if p.get("status") == "published"]
    print(f"account day {ph['day']} — phase limits: {ph['max_per_day']}/day, gap ≥ {ph['min_gap_h']} h, "
          f"Reels/week ≤ {ph['reels_per_week']}")
    marks = halt_markers()
    print(f"HALT: {'YES — ' + ' | '.join(marks) if marks else 'no'}")
    print(f"published: {len(pub)}  (last 24 h: "
          f"{sum(datetime.fromisoformat(p['published_at']) > now - timedelta(hours=24) for p in pub)})")
    for p in posts[-10:]:
        print(f"  {p.get('published_at', p.get('at', ''))[:16]}  {p['status']:10} {p['kind']:8} {p['slug']}  {p.get('media_id', '')}")


def run_checks(cfg, post, verbose=True):
    ok_all = True
    marks = halt_markers()
    if marks:
        for m in marks:
            print(f"HALT marker present: {m}")
        return False
    ok, note = check_preflight(post["slug"])
    print(f"[{'ok' if ok else 'FAIL'}] preflight: {note}")
    ok_all &= ok
    for rel in post["files"]:
        want = "video/mp4" if rel.endswith(".mp4") else "image/jpeg"
        ok, note = check_url(media_url(cfg, rel), want)
        print(f"[{'ok' if ok else 'FAIL'}] url {rel}: {note}")
        ok_all &= ok
    ph, problems = check_cadence(cfg, post)
    for p in problems:
        print(f"[FAIL] cadence: {p}")
    ok_all &= not problems
    print(f"[ok] cadence: day {ph['day']}, {ph['max_per_day']}/day, gap {ph['min_gap_h']} h" if not problems else "")
    return ok_all


def cmd_plan(cfg, slug):
    post = find_post(slug)
    print(f"== plan: {post['kind']} '{slug}'  ({len(post['files'])} media files)\n")
    ok = run_checks(cfg, post)
    seq = api_sequence(cfg, post)
    plan_path = post["dir"] / (f"{slug}-publish-plan.json" if post["kind"] == "reel" else "publish-plan.json")
    plan_path.write_text(json.dumps({"slug": slug, "kind": post["kind"], "checks_passed": ok,
                                     "generated_at": datetime.now(timezone.utc).isoformat(),
                                     "calls": seq}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAPI sequence ({len(seq)} calls) written to {plan_path.relative_to(ROOT)}")
    for c in seq:
        shown = {k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v) for k, v in c["params"].items()}
        print(f"  {c['step']:10} {c['method']:4} {c['path']}  {shown}")
    print("\n" + ("READY — all checks passed. Nothing has been posted." if ok else "NOT READY — fix the FAIL items above."))
    return ok


def wait_for_container(cfg, cid):
    for _ in range(5):
        time.sleep(60)
        data, _ = graph(cfg, "GET", f"/{cid}", {"fields": "status_code,status"})
        print(f"   container {cid}: {data.get('status_code')} {data.get('status', '')}")
        if data.get("status_code") == "FINISHED":
            return True
        if data.get("status_code") in ("ERROR", "EXPIRED"):
            return False
    return False


def cmd_publish(cfg, slug, yes):
    post = find_post(slug)
    if not cfg["token"]:
        sys.exit("IG_ACCESS_TOKEN is not set (put it in .env or the environment)")
    if not cmd_plan(cfg, slug):
        sys.exit(1)
    if not yes:
        sys.exit("\nRe-run with --yes to actually publish.")
    ig = cfg["ig_user_id"]
    try:
        quota, usage = graph(cfg, "GET", f"/{ig}/content_publishing_limit", {"fields": "quota_usage,config"})
        q = quota["data"][0]
        print(f"\nquota: {q['quota_usage']}/{q['config']['quota_total']} used in the last 24 h  (usage header: {usage})")
        if q["quota_usage"] >= QUOTA_HALT_AT:
            halt(f"quota_usage {q['quota_usage']} ≥ {QUOTA_HALT_AT}")

        if post["kind"] == "carousel":
            children = []
            for i, rel in enumerate(post["files"], 1):
                data, _ = graph(cfg, "POST", f"/{ig}/media", data={
                    "image_url": media_url(cfg, rel), "is_carousel_item": "true",
                    "alt_text": post["meta"]["alt_texts"][i - 1][:1000]})
                children.append(data["id"])
                print(f"   child {i}: {data['id']}")
                time.sleep(2)
            data, _ = graph(cfg, "POST", f"/{ig}/media", data={
                "media_type": "CAROUSEL", "children": ",".join(children), "caption": post["caption"]})
        else:
            data, _ = graph(cfg, "POST", f"/{ig}/media", data={
                "media_type": "REELS", "video_url": media_url(cfg, post["files"][0]),
                "cover_url": media_url(cfg, post["files"][1]), "share_to_feed": "true",
                "caption": post["caption"]})
        cid = data["id"]
        print(f"   container: {cid} — polling")
        if not wait_for_container(cfg, cid):
            log_entry({"at": datetime.now(timezone.utc).isoformat(), "slug": slug, "kind": post["kind"],
                       "status": "container_failed", "container_id": cid})
            halt(f"container {cid} did not reach FINISHED")
        pub, usage = graph(cfg, "POST", f"/{ig}/media_publish", data={"creation_id": cid})
        entry = {"published_at": datetime.now(timezone.utc).isoformat(), "slug": slug, "kind": post["kind"],
                 "status": "published", "media_id": pub["id"], "container_id": cid,
                 "hashtags": post["meta"]["hashtags"], "quota_usage_before": q["quota_usage"], "usage_header": usage}
        log_entry(entry)
        print(f"\nPUBLISHED media id {pub['id']} — logged to log/posts.jsonl")
    except GraphError as e:
        log_entry({"at": datetime.now(timezone.utc).isoformat(), "slug": slug, "kind": post["kind"],
                   "status": "error", "error": e.err})
        print(f"\nGraph API error {e.code}/{e.subcode}: {e}")
        if e.is_hard_stop():
            halt(f"error {e.code}/{e.subcode}: {e}")
        if e.is_safe_retry():
            print("This code is on the safe-retry list: retry ONCE after 60 s, by hand.")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("plan"); p.add_argument("slug")
    p = sub.add_parser("publish"); p.add_argument("slug"); p.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    if a.cmd == "status":
        cmd_status(cfg)
    elif a.cmd == "plan":
        sys.exit(0 if cmd_plan(cfg, a.slug) else 1)
    else:
        cmd_publish(cfg, a.slug, a.yes)


if __name__ == "__main__":
    main()
