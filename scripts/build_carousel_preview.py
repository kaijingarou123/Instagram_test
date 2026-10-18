"""Build output/carousels/index.html — a scrollable, Instagram-style preview of every queued carousel.

    python scripts/build_carousel_preview.py
    python -m http.server 8766 --directory output/carousels     # open http://localhost:8766

Order follows log/queue.json; anything already in log/posts.jsonl is marked "Posted".
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAR = ROOT / "output" / "carousels"
HANDLE = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["ig_username"]


def load():
    order = json.loads((ROOT / "log" / "queue.json").read_text(encoding="utf-8"))["order"]
    posted = {}
    log = ROOT / "log" / "posts.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("status") == "published":
                    posted[r["slug"]] = r
    extra = [s for s in posted if s not in order and (CAR / s / "meta.json").exists()]
    return extra + order, posted


def card(i, slug, posted):
    meta = json.loads((CAR / slug / "meta.json").read_text(encoding="utf-8"))
    caption = (CAR / slug / "caption.txt").read_text(encoding="utf-8")
    first, _, rest = caption.partition("\n")
    slides = "".join(
        f'<img src="{slug}/{f}" alt="{html.escape(a)}" loading="lazy" width="1080" height="1350">'
        for f, a in zip(meta["slides"], meta["alt_texts"]))
    dots = "".join("<i></i>" for _ in meta["slides"])
    badge = ('<span class="badge done">Posted</span>' if slug in posted
             else f'<span class="badge">Queue #{i}</span>')
    return f"""
<article class="post" data-slug="{slug}">
  <header><span class="avatar"></span><b>{HANDLE}</b>{badge}<code>{slug}</code></header>
  <div class="frame">
    <div class="track">{slides}</div>
    <button class="nav prev" aria-label="Previous slide">‹</button>
    <button class="nav next" aria-label="Next slide">›</button>
    <span class="count">1/{len(meta['slides'])}</span>
  </div>
  <div class="dots">{dots}</div>
  <div class="caption"><b>{HANDLE}</b> {html.escape(first)}<details><summary>more</summary><pre>{html.escape(rest.strip())}</pre></details></div>
</article>"""


def main():
    order, posted = load()
    n = 0
    cards = []
    for slug in order:
        if slug not in posted:
            n += 1
        cards.append(card(n, slug, posted))
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carousel Queue Preview</title>
<style>
:root {{ --bg:#fafafa; --card:#fff; --ink:#111; --muted:#737373; --line:#dbdbdb; --accent:#e9a23b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#000; --card:#121212; --ink:#f5f5f5; --muted:#a8a8a8; --line:#262626; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
h1 {{ font-size:18px; text-align:center; margin:24px 16px 4px; }}
.sub {{ text-align:center; color:var(--muted); margin:0 16px 20px; }}
main {{ max-width:470px; margin:0 auto; padding:0 16px 60px; display:grid; gap:28px; }}
.post {{ background:var(--card); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
header {{ display:flex; align-items:center; gap:8px; padding:10px 12px; flex-wrap:wrap; }}
.avatar {{ width:28px; height:28px; border-radius:50%; background:linear-gradient(135deg,#1b4332,var(--accent)); }}
.badge {{ font-size:11px; padding:2px 8px; border-radius:99px; background:var(--accent); color:#111; font-weight:600; }}
.badge.done {{ background:#2e7d32; color:#fff; }}
header code {{ margin-left:auto; color:var(--muted); font-size:11px; }}
.frame {{ position:relative; }}
.track {{ display:flex; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; }}
.track::-webkit-scrollbar {{ display:none; }}
.track img {{ flex:0 0 100%; width:100%; height:auto; aspect-ratio:4/5; scroll-snap-align:start; display:block; }}
.nav {{ position:absolute; top:50%; transform:translateY(-50%); width:30px; height:30px; border-radius:50%; border:0;
  background:rgba(255,255,255,.85); color:#111; font-size:20px; line-height:1; cursor:pointer; }}
.prev {{ left:8px; }} .next {{ right:8px; }}
.count {{ position:absolute; top:10px; right:10px; background:rgba(0,0,0,.6); color:#fff; font-size:12px; padding:2px 8px; border-radius:99px; }}
.dots {{ display:flex; justify-content:center; gap:4px; padding:10px 0 4px; }}
.dots i {{ width:6px; height:6px; border-radius:50%; background:var(--line); }}
.dots i.on {{ background:#0095f6; }}
.caption {{ padding:4px 12px 12px; }}
summary {{ color:var(--muted); cursor:pointer; }}
pre {{ white-space:pre-wrap; font:inherit; margin:6px 0 0; }}
</style></head><body>
<h1>Carousel queue: @{HANDLE}</h1>
<p class="sub">{len(order)} carousels · swipe, scroll sideways or use the arrows (← → keys move the carousel under the pointer)</p>
<main>{''.join(cards)}</main>
<script>
document.querySelectorAll('.post').forEach(p => {{
  const t = p.querySelector('.track'), n = t.children.length, dots = p.querySelectorAll('.dots i'), c = p.querySelector('.count');
  const w = () => t.clientWidth || 1, idx = () => Math.min(n - 1, Math.round(t.scrollLeft / w()));
  const go = i => t.scrollTo({{left: Math.max(0, Math.min(n - 1, i)) * w(), behavior: 'smooth'}});
  const paint = () => {{ const i = idx(); dots.forEach((d, k) => d.classList.toggle('on', k === i)); c.textContent = (i + 1) + '/' + n;
    p.querySelector('.prev').style.visibility = i ? 'visible' : 'hidden'; p.querySelector('.next').style.visibility = i < n - 1 ? 'visible' : 'hidden'; }};
  p.querySelector('.prev').onclick = () => {{ go(idx() - 1); setTimeout(paint, 450); }};
  p.querySelector('.next').onclick = () => {{ go(idx() + 1); setTimeout(paint, 450); }};
  t.addEventListener('scroll', paint, {{passive: true}});
  p.addEventListener('mouseenter', () => window.current = {{go, idx}});
  paint();
}});
document.addEventListener('keydown', e => {{
  if (!window.current) return;
  if (e.key === 'ArrowRight') window.current.go(window.current.idx() + 1);
  if (e.key === 'ArrowLeft') window.current.go(window.current.idx() - 1);
}});
</script></body></html>"""
    (CAR / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {CAR / 'index.html'} ({len(order)} carousels)")


if __name__ == "__main__":
    main()
