# Wildlife & nature education — Instagram content lab

Test account: **@claudes_plan101** (connected via Composio; Instagram Graph API).
Goal: research-driven, fully sourced wildlife-education content (carousels + Reels),
produced locally, checked computationally, and published within a safe operating
envelope. Nothing has been posted yet.

## Layout

```
research/
  posting-limits.md      API quotas, media specs, account rules, originality policy,
                         licensing, warm-up cadence, hard-stop error codes (cited)
  content-strategy.md    What works in the niche, format benchmarks, pillars, caption
                         formula, design rules, media/fact sources, weekly mix, rubric,
                         6 drafted posts
CHECKLIST.md             The pre-post analysis checklist distilled from both reports
scripts/
  fetch_commons.py       Pull CC/PD photos from Wikimedia Commons with attribution
  render.py              Shared Pillow helpers (fonts, cover-crop, gradients, text fit)
  make_carousel.py       JSON spec -> 1080x1350 JPEG slides + caption + meta
  make_reel.py           JSON spec -> 1080x1920 H.264 Reel with Ken Burns + text
  preflight.py           Automated spec/caption/licence checks on everything in output/
content/posts/*.json     Carousel specs      content/reels/*.json   Reel specs
assets/raw/<species>/    Downloaded photos + credits.json (licence, author, URL)
output/carousels/<slug>/ 01..NN.jpg, caption.txt, meta.json, _preview.jpg
output/reels/            <slug>.mp4, -cover.jpg, -caption.txt, -meta.json
```

## Pipeline

```bash
python scripts/fetch_commons.py "snow leopard" "axolotl"          # source photos
python scripts/make_carousel.py content/posts/<slug>.json          # render carousel
python scripts/make_reel.py content/reels/<slug>.json              # render reel
python scripts/preflight.py                                        # check everything
```

## Not yet done (needed before the first API post)

1. **Hosting** — the API fetches media from a public URL. Candidates: a public GitHub repo
   (raw.githubusercontent.com — must verify 200 + image/jpeg + no redirect), or S3/R2.
2. **Account check — done.** @claudes_plan101 is a public **Business** account (confirmed
   2026-10-15). Composio's `account_type: PRIVATE` refers to the Composio connection's
   visibility, not Instagram. API publishing is permitted for this account type.
3. **Manual warm-up** — first 2 posts manually in the app (days 1–3), API from week 2.
4. **Posting + logging script** — `content_publishing_limit` check → container → poll →
   publish → log, with the hard-stop codes from `CHECKLIST.md`.
5. **Insights loop** — pull media insights at +24 h / +7 d and score against the rubric.
