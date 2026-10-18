# Wildlife & nature education — Instagram content lab

Test account: **@earthspirit_nature** (renamed from @claudes_plan101 on 2026-10-17/18) (connected via Composio; Instagram Graph API).
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
- **Account — done.** @earthspirit_nature is a public **Business** account (confirmed 2026-10-15).
  Composio's `account_type: PRIVATE` refers to the Composio connection's visibility, not Instagram.
- **Safety** — `publish.py` enforces the envelope from `CHECKLIST.md` §A (phase limits by
  account age, min gap, Reels allowance, hashtag rotation, live quota, hard-stop codes →
  `log/HALT`). Decision 2026-10-15: the manual warm-up is skipped — the first post goes
  through the API on day 0 (the phase-1 limits of 1 post/day, 20 h gap, no Reels still apply).
- **Token** — publishing directly needs a long-lived Instagram user token in `.env`; the
  Composio connection can be used instead by executing the call sequence that `plan` prints.

## Guardrails

Every agent, skill or scheduled task that publishes here follows the `platform-guardrails`
skill in `kaijingarou123/Claude-skills-agents-plugins` (`plugins/platform-guardrails/`): read
`RULES.md`, run the pre-action checklist, record the pass with `hooks/guardrails_gate.py pass`,
and stop on any hard-stop code. Two HALT markers block publishing and both are honoured by
`publish.py`: `log/HALT` (written here on a hard stop) and `~/.claude/platform-guardrails/HALT`
(written by the gate for either platform). `publish.py` mirrors its own HALT into the shared one.
Only a human deletes a marker, after checking Account Status and the quota.

## Format library (internal preview, nothing posted)

159 example reels — 3 for each of the 53 `format:` tags in the `social-media-knowledge` vocabulary
(`kaijingarou123/Claude-skills-agents-plugins`). 50 are storyboards (a "STORYBOARD — Film: …" band names
the shot a person must film); 6 are anti-pattern demos stamped "AVOID — DO NOT POST".

```bash
python scripts/catalog.py                         # media catalog -> assets/catalog.md
python scripts/check_specs.py                     # validate content/formats/specs/*.json
python scripts/make_reel2.py --all --jobs 10      # render -> output/formats/<slug>.mp4 (+ poster, meta)
python scripts/build_preview.py                   # output/formats/index.html
python -m http.server 8765 --directory output/formats   # open http://localhost:8765
```

- Brief for scriptwriters: `content/formats/BRIEF.md`. Engine layouts: full, stat, meme, split, pip, card, quote, wipe, grid, chart.
- Media: CC0 / CC BY / CC BY-SA from Wikimedia Commons, vetted by eye (zoo, captive, AI and mislabelled files removed;
  the Veo 3 owl clip lives in `assets/video/ai-generated/` for AI-format demos only).
- MP4s (~770 MB) and downloaded media stay local (`.gitignore`); specs, posters, metadata and the page are committed.

## Status

- **2026-10-15** — first post published via Composio: `mantis-shrimp-punch` carousel,
  media id 18077211017439635, https://www.instagram.com/p/Deg8St8FavB/ (see `log/posts.jsonl`).
  Lessons: `share_to_feed` is rejected on a CAROUSEL container (400 Invalid parameter) —
  only send it for Reels; a client-side network drop mid-batch left container state unknown,
  re-issuing the child creates once was safe (unpublished containers expire in 24 h).
- Five more example posts are rendered and pass preflight; the cadence guard now blocks
  further publishing until ≥ 20 h after the last post (phase 1).
- **2026-10-17** — 14 more carousels added; 16 queued in `log/queue.json`. The scheduled task
  `instagram-autopost` (Claude desktop, hourly) asks `scripts/post_queue.py next` whether a post is due
  (random 9–13 h gaps, 2 posts a day; 08:00–21:30 IST), runs `publish.py plan`, then publishes
  via Composio behind the guardrails gate. It disables itself and notifies when the queue ends or on HALT.
  Reels stay out of the queue until day 14.

## Insight dashboard

Live dashboard (claude.ai Artifact, private to the owner; share it from its Share menu):
https://claude.ai/artifact/XnM4F7V4xrTXyHGBNEdXmQ

- Page source: `dashboard/index.html`. Data lives in the artifact's own database, not in the page.
- `scripts/dashboard_sync.py` builds the database documents from local files (`build`, `batches`, `mark-synced`,
  `record-metrics`, `thumbs`).
- The insight agent's judgement lives in `log/agent/` (insights, plans, experiments, competitors, connectors,
  decisions, takeaways, activity). Each item keeps its own history, so added, updated and dropped items stay visible.
- Scheduled task `instagram-insight-agent` runs every 6 h (xx:17 local): reads own metrics through Composio,
  scans links queued on the "Scan a post" page with web tools only, revises insights and the plan, pushes changes.
- To move this to another account: change `config.json`, `log/dashboard/config.json`, the artifact URL in the
  task prompt, and the Composio account name.
- **2026-10-18**: owner decision: 2 posts a day (at least 8 h apart) from day 0, overriding the
  platform-guardrails weeks 1–2 limit of 1/day. The owner accepted the higher new-account risk. Implemented
  in `publish.py` PHASES and `post_queue.py`; every other guardrail (quota halt, hard stops, HALT markers,
  no Reels before day 14) is unchanged.
