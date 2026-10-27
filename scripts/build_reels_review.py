"""Build output/reels/index.html: every rendered Reel, playable, with caption and approval status.

    python scripts/build_reels_review.py
    open http://localhost:8767/reels/  (launch config "reels-review")  or, after a push,
    https://kaijingarou123.github.io/Instagram_test/output/reels/

A Reel is posted only after the owner approves it (its slug in `approved_reels` in log/queue.json).
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REELS = ROOT / "output" / "reels"


def main():
    q = json.loads((ROOT / "log" / "queue.json").read_text(encoding="utf-8"))
    approved, queued = set(q.get("approved_reels", [])), set(q["order"])
    posted = set()
    log = ROOT / "log" / "posts.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(line) if line.strip() else {}
            if r.get("status") == "published":
                posted.add(r["slug"])
    cards = []
    for meta_p in sorted(REELS.glob("*-meta.json")):
        slug = meta_p.name[: -len("-meta.json")]
        if not (REELS / f"{slug}.mp4").exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        cap_p = REELS / f"{slug}-caption.txt"
        caption = cap_p.read_text(encoding="utf-8") if cap_p.exists() else ""
        if slug in posted:
            status, cls = "Posted", "posted"
        elif slug in approved:
            status, cls = "Approved, queued", "ok"
        elif slug in queued:
            status, cls = "Waiting for your approval", "wait"
        else:
            status, cls = "Sample, not queued", "sample"
        facts = [f"{meta.get('duration_s', '?')} s", meta.get("audio", "audio not recorded"),
                 " ".join(meta.get("format_tags", []))]
        cover = f"{slug}-cover.jpg" if (REELS / f"{slug}-cover.jpg").exists() else ""
        cards.append(f"""
<article class="reel">
  <video src="{slug}.mp4" {'poster="' + cover + '"' if cover else ''} controls playsinline preload="metadata"></video>
  <div class="body">
    <div class="row"><code>{html.escape(slug)}</code><span class="st {cls}">{status}</span></div>
    <p class="facts">{html.escape(' · '.join(f for f in facts if f))}</p>
    <pre>{html.escape(caption.strip())}</pre>
  </div>
</article>""")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reels Review</title>
<style>
:root {{ --bg:#f6f7f4; --card:#fff; --ink:#15201a; --muted:#5f6b63; --line:#d9ded8; --ok:#1f7a45; --wait:#a35a00; --accent:#2f6b4f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1310; --card:#161d19; --ink:#e8eee9; --muted:#9aa79f; --line:#2a332d; --ok:#5cc58a; --wait:#f0a64a; --accent:#7fc2a0; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
header, main {{ max-width:1100px; margin:0 auto; padding-inline:max(16px, env(safe-area-inset-left)); }}
header {{ padding-block:24px 8px; }}
h1 {{ font-size:22px; margin:0 0 6px; }}
header p {{ margin:0; color:var(--muted); max-width:70ch; }}
main {{ display:grid; gap:20px; grid-template-columns:repeat(auto-fill, minmax(min(100%, 300px), 1fr)); padding-block:16px 48px; }}
.reel {{ background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; display:grid; align-content:start; }}
video {{ width:100%; aspect-ratio:9/16; background:#000; display:block; }}
.body {{ padding:12px 14px 16px; display:grid; gap:8px; min-width:0; }}
.row {{ display:flex; gap:8px; align-items:center; justify-content:space-between; flex-wrap:wrap; }}
code {{ font-size:13px; color:var(--muted); }}
.st {{ font-size:12px; font-weight:600; padding:2px 8px; border-radius:99px; border:1px solid currentColor; }}
.st.ok {{ color:var(--ok); }} .st.wait {{ color:var(--wait); }} .st.posted {{ color:var(--accent); }} .st.sample {{ color:var(--muted); }}
.facts {{ margin:0; font-size:13px; color:var(--muted); }}
pre {{ white-space:pre-wrap; font:inherit; font-size:13px; margin:0; max-height:220px; overflow:auto; }}
</style></head><body>
<header><h1>Reels review: @{html.escape(json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))['ig_username'])}</h1>
<p>Nothing here posts until you approve it. Tell Claude which Reels to approve or change, by the name under each video.</p></header>
<main>{''.join(cards) or '<p>No Reels rendered yet.</p>'}</main>
</body></html>"""
    (REELS / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {REELS / 'index.html'} ({len(cards)} Reels)")


if __name__ == "__main__":
    main()
