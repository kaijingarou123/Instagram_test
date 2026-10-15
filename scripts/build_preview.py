"""Build output/formats/index.html: the format-library preview page.

    python scripts/build_preview.py

Groups rendered reels by family -> format, three per row, with risk, storyboard flag,
caption, tags, sources and credits. Videos load lazily (posters first).
"""
import html
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "formats"
VOCAB = Path(r"E:\claude\Claude-skills-agents-plugins\plugins\social-media-knowledge\knowledge\tags\reel-formats.json")

CSS = """
:root{--bg:#f4f1e8;--fg:#14201a;--muted:#5d6b62;--card:#fffdf7;--line:#ddd6c4;--amber:#c98f12;--moss:#4a6e54;
--low:#2f7d4f;--medium:#b07a0c;--high:#b2431f;--avoid:#a11d2b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1713;--fg:#eef0e8;--muted:#9fb0a5;--card:#16211b;--line:#2a3a31}}
:root[data-theme="dark"]{--bg:#0f1713;--fg:#eef0e8;--muted:#9fb0a5;--card:#16211b;--line:#2a3a31}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px}
header h1{margin:0 0 6px;font-size:20px}.sub{color:var(--muted);font-size:13px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:4px 11px;cursor:pointer;font-size:13px}
.filters button.on{background:var(--fg);color:var(--bg)}
nav{padding:10px 16px;display:flex;flex-wrap:wrap;gap:8px;font-size:13px}nav a{color:var(--moss)}
main{padding:0 16px 60px;max-width:1280px;margin:0 auto}
h2{margin:34px 0 4px;font-size:22px}h3{margin:22px 0 4px;font-size:17px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.fmtdesc{color:var(--muted);margin:0 0 10px;font-size:14px}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
video{width:100%;aspect-ratio:9/16;background:#000;display:block}
.meta{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px}
.title{font-weight:650}.badges{display:flex;gap:5px;flex-wrap:wrap}
.b{font-size:11px;font-weight:650;border-radius:6px;padding:2px 7px;color:#fff}
.b.low{background:var(--low)}.b.medium{background:var(--medium)}.b.high{background:var(--high)}.b.avoid{background:var(--avoid)}
.b.sb{background:#3b4a8a}.b.t{background:transparent;color:var(--muted);border:1px solid var(--line)}
details{font-size:13px}summary{cursor:pointer;color:var(--moss)}pre{white-space:pre-wrap;font:13px/1.45 inherit;margin:6px 0}
.small{font-size:12px;color:var(--muted)}a{color:var(--moss)}.missing{padding:40px 12px;text-align:center;color:var(--muted)}
"""

JS = """
const btns=[...document.querySelectorAll('.filters button')];
btns.forEach(b=>b.onclick=()=>{btns.forEach(x=>x.classList.toggle('on',x===b));const f=b.dataset.f;
document.querySelectorAll('.card').forEach(c=>{c.style.display=(f==='all'||c.dataset.risk===f||(f==='sb'&&c.dataset.sb==='1'))?'':'none'});});
document.querySelectorAll('video').forEach(v=>{v.addEventListener('play',()=>document.querySelectorAll('video').forEach(o=>{if(o!==v)o.pause()}))});
"""


def esc(s):
    return html.escape(str(s or ""))


def main():
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    metas = {}
    for p in OUT.glob("*.json"):
        if p.name.startswith("_"):
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        if "format_tag" in m:
            metas.setdefault(m["format_tag"], []).append(m)
    n_reels = sum(len(v) for v in metas.values())
    n_sb = sum(1 for v in metas.values() for m in v if m.get("storyboard"))
    total_s = sum(m.get("duration_s", 0) for v in metas.values() for m in v)
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>Reel Format Library</title><style>{CSS}</style></head><body>",
             "<header><h1>Reel format library — 3 examples per format</h1>"
             f"<div class=sub>{n_reels} reels · {len(metas)} formats · {total_s/60:.0f} min of video · {n_sb} storyboards "
             "· tags from <code>social-media-knowledge/reel-formats.json</code> · nothing here has been posted</div>"
             "<div class=filters><button class=on data-f=all>All</button><button data-f=low>Low risk</button>"
             "<button data-f=medium>Medium</button><button data-f=high>High</button><button data-f=avoid>Avoid</button>"
             "<button data-f=sb>Storyboards</button></div></header>"]
    fams = [f for f in vocab["families"] if f["id"] != "tactic"]
    parts.append("<nav>" + " · ".join(f"<a href='#{f['id']}'>{esc(f['name'])}</a>" for f in fams) + "</nav><main>")
    for fam in fams:
        parts.append(f"<h2 id='{fam['id']}'>{esc(fam['name'])}</h2>")
        for t in [t for t in vocab["tags"] if t["family"] == fam["id"]]:
            reels = sorted(metas.get(t["tag"], []), key=lambda m: m.get("variant", 0))
            parts.append(f"<h3>{esc(t['name'])} <code class=small>{esc(t['tag'])}</code>"
                         f"<span class='b {t['risk']}'>{t['risk'].upper()}</span></h3>"
                         f"<p class=fmtdesc>{esc(t['description'])} <em>Risk: {esc(t['risk_why'])}</em></p><div class=row>")
            if not reels:
                parts.append("<div class='card'><div class=missing>not rendered yet</div></div>")
            for m in reels:
                slug = m["slug"]
                sb = "1" if m.get("storyboard") else "0"
                tags = " ".join(f"<span class='b t'>{esc(x)}</span>" for x in m.get("tactic_tags") or [])
                srcs = "".join(f"<li><a href='{esc(u)}' target=_blank rel=noopener>{esc(u[:70])}</a></li>" for u in m.get("sources") or [])
                creds = "".join(f"<li>{esc(c)}</li>" for c in m.get("credits") or [])
                parts.append(
                    f"<div class=card data-risk='{t['risk']}' data-sb='{sb}'>"
                    f"<video controls preload=none playsinline poster='{slug}.jpg' src='{slug}.mp4'></video>"
                    f"<div class=meta><div class=title>{esc(m.get('title'))}</div>"
                    f"<div class=badges><span class='b {t['risk']}'>{t['risk']}</span>"
                    + ("<span class='b sb'>storyboard</span>" if sb == "1" else "") + f"{tags}"
                    f"<span class='b t'>{m.get('duration_s')} s</span></div>"
                    + (f"<div class=small><b>Film:</b> {esc(m['storyboard'].removeprefix('Film:').strip())}</div>" if sb == "1" else "")
                    + f"<details><summary>Caption & hashtags</summary><pre>{esc(m.get('caption'))}\n\n{esc(' '.join(m.get('hashtags') or []))}</pre></details>"
                    f"<details><summary>Sources & credits</summary><ul>{srcs}</ul><ul class=small>{creds}</ul></details>"
                    f"<div class=small><code>{esc(slug)}</code></div></div></div>")
            parts.append("</div>")
    parts.append(f"</main><script>{JS}</script></body></html>")
    (OUT / "index.html").write_text("".join(parts), encoding="utf-8")
    print(f"index.html: {n_reels} reels across {len(metas)} formats ({n_sb} storyboards)")


if __name__ == "__main__":
    main()
