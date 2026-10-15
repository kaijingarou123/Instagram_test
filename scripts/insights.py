"""Pull performance data for published posts and keep a running scoreboard.

    python scripts/insights.py            # every published post in log/posts.jsonl
    python scripts/insights.py <slug>     # one post

Writes log/insights.jsonl (one row per fetch, so +24 h and +7 d snapshots coexist)
and prints a table. Needs IG_ACCESS_TOKEN (see .env.example). Metric names follow
research/posting-limits.md: `impressions` is deprecated, `views` replaces it; some
account-level insights need >= 100 followers, but per-media reach/saves/shares work
from the first post.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import LOG_DIR, GraphError, graph, load_config, read_log  # noqa: E402

INSIGHTS = LOG_DIR / "insights.jsonl"
METRICS = {
    "carousel": ["reach", "saved", "shares", "likes", "comments", "total_interactions", "views"],
    "reel": ["reach", "saved", "shares", "likes", "comments", "total_interactions", "views",
             "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"],
}


def fetch(cfg, post):
    data, _ = graph(cfg, "GET", f"/{post['media_id']}/insights",
                    {"metric": ",".join(METRICS[post["kind"]]), "period": "lifetime"})
    out = {}
    for item in data.get("data", []):
        vals = item.get("values") or []
        out[item["name"]] = vals[0].get("value") if vals else item.get("value")
    return out


def main(slugs):
    cfg = load_config()
    if not cfg["token"]:
        sys.exit("IG_ACCESS_TOKEN is not set")
    posts = [p for p in read_log() if p.get("status") == "published" and (not slugs or p["slug"] in slugs)]
    if not posts:
        sys.exit("nothing published yet")
    now = datetime.now(timezone.utc)
    print(f"{'slug':30} {'kind':8} {'age_h':>6} {'reach':>7} {'saves':>6} {'shares':>6} {'likes':>6} {'cmts':>5}  save/reach")
    for p in posts:
        age_h = (now - datetime.fromisoformat(p["published_at"])).total_seconds() / 3600
        try:
            m = fetch(cfg, p)
        except GraphError as e:
            print(f"{p['slug']:30} error {e.code}/{e.subcode}: {e}")
            continue
        row = {"fetched_at": now.isoformat(), "slug": p["slug"], "kind": p["kind"], "media_id": p["media_id"],
               "age_hours": round(age_h, 1), **m}
        with INSIGHTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        reach = m.get("reach") or 0
        ratio = (m.get("saved") or 0) / reach if reach else 0
        print(f"{p['slug']:30} {p['kind']:8} {age_h:6.0f} {reach:7} {m.get('saved', 0):6} {m.get('shares', 0):6} "
              f"{m.get('likes', 0):6} {m.get('comments', 0):5}  {ratio:.1%}")


if __name__ == "__main__":
    main(sys.argv[1:])
