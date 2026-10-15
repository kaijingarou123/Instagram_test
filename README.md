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

## Publishing

```bash
python scripts/publish.py status                 # account phase, allowance, HALT state, recent posts
python scripts/publish.py plan <slug>            # preflight + URL + cadence checks, prints the API calls; no Meta calls
python scripts/publish.py publish <slug> --yes   # real publish (needs IG_ACCESS_TOKEN in .env)
python scripts/insights.py [<slug>]              # reach/saves/shares per post -> log/insights.jsonl
```

- **Hosting — done.** Media is served by GitHub Pages from this repo:
  `https://kaijingarou123.github.io/Instagram_test/output/...` — verified 2026-10-15 to return
  200, no redirect, `image/jpeg` / `video/mp4`. (raw.githubusercontent.com serves MP4 as
  `application/octet-stream`; jsDelivr failed to fetch the MP4 — both rejected.)
- **Account — done.** @claudes_plan101 is a public **Business** account (confirmed 2026-10-15).
  Composio's `account_type: PRIVATE` refers to the Composio connection's visibility, not Instagram.
- **Safety** — `publish.py` enforces the envelope from `CHECKLIST.md` §A (phase limits by
  account age, min gap, Reels allowance, hashtag rotation, live quota, hard-stop codes →
  `log/HALT`). Decision 2026-10-15: the manual warm-up is skipped — the first post goes
  through the API on day 0 (the phase-1 limits of 1 post/day, 20 h gap, no Reels still apply).
- **Token** — publishing directly needs a long-lived Instagram user token in `.env`; the
  Composio connection can be used instead by executing the call sequence that `plan` prints.

## Status

- **2026-10-15** — first post published via Composio: `mantis-shrimp-punch` carousel,
  media id 18077211017439635, https://www.instagram.com/p/Deg8St8FavB/ (see `log/posts.jsonl`).
  Lessons: `share_to_feed` is rejected on a CAROUSEL container (400 Invalid parameter) —
  only send it for Reels; a client-side network drop mid-batch left container state unknown,
  re-issuing the child creates once was safe (unpublished containers expire in 24 h).
- Five more example posts are rendered and pass preflight; the cadence guard now blocks
  further publishing until ≥ 20 h after the last post (phase 1).
