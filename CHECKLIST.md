# Pre-post checklist — wildlife & nature education (@claudes_plan101)

Everything here is derived from `research/posting-limits.md` and
`research/content-strategy.md`. Automated items are enforced by
`scripts/preflight.py`; the rest are a human/LLM judgement pass.

## A. Account & cadence (safety envelope)

| Phase | Max posts/day | Min gap | Reels | Notes |
|---|---|---|---|---|
| Days 1–3 | 0–1, **manual** in the app | — | none | Finish profile (photo, bio, no external link for 2 weeks). No follow bursts. |
| Weeks 1–2 | 1 | ≥ 20 h | none | First API post only after ≥ 2 manual posts have gone up cleanly. |
| Weeks 3–4 | 2 | ≥ 8 h | ≤ 2 / week | Start Reels. Watch Account Status weekly. |
| Week 5+ | 3 ceiling | ≥ 6 h | per weekly mix | Never > 10 publishes/day; halt if `quota_usage` ≥ 20/50. |

- Read `content_publishing_limit` **live** before every publish; never hardcode the quota (Meta docs disagree: 50 vs 100 per 24 h).
- API call budget per post: 1 limit check + 1 container create + ≤ 5 status polls + 1 publish.
- Hard stops (halt the pipeline, alert a human): error codes 4/2207051, 25/2207050, 9/2207042, 4 / 17 / 613 / 80002, token error 190, `estimated_time_to_regain_access > 0`, two consecutive media-fetch failures, any Account Status warning, or zero reach on 3 consecutive posts.

## B. Originality (the biggest single risk for CC-photo content)

Since 30 Apr 2026 an account that *primarily* posts unoriginal media in a rolling 30-day window loses all recommendation reach. Crop, border, credit, watermark or a caption change do **not** count as original. Overlaid text that adds information, graphics, narration or a storyline **does**.

- [ ] Every slide / scene carries designed, informative text (fact, stat, comparison). No raw photo ever goes out.
- [ ] The post adds a framing not found on page 1 of a Google search for the species (comparison, scale, myth-bust, "how does it survive").

## C. Licensing & attribution

- [ ] Every photo is CC0 / public domain / CC BY / CC BY-SA (checked from Commons `extmetadata`, stored in `assets/raw/<species>/credits.json`). No NC / ND.
- [ ] Credit line rendered on every slide that uses the photo **and** full credits on the closing slide **and** a credit line in the caption (Wikimedia Legal: caption attribution suffices).
- [ ] If any photo is BY-SA, the whole graphic is treated as BY-SA (we don't claim exclusivity over it).
- [ ] Reels audio: generated ambient bed, CC0 track, or none. Never commercial music (business accounts lack the licensed library; Rights Manager auto-mutes).
- [ ] Photos of captive animals (zoo, falconry) are labelled as such in the caption; marine-park show photos are never used.

## D. Factual accuracy

- [ ] Every claim traces to a Tier-1 source (IUCN Red List, Animal Diversity Web, Cornell Lab, NOAA, peer-reviewed paper). Wikipedia may lead, never finish.
- [ ] Conservation status + assessment year quoted exactly as IUCN states it.
- [ ] Source shown on the slide/scene that makes the claim, plus the closing slide, plus a `Source:` line in the caption.
- [ ] Numbers that could not be verified are softened or dropped (e.g. "9 mm vocal folds" → "no fibro-elastic pad").

## E. Media specs (automated in `preflight.py`)

Carousel: 2–10 JPEG slides, sRGB, 1080×1350 (4:5), ≤ 8 MB each, alt text ≤ 1000 chars per slide.
Reel: MP4, H.264 + AAC ≤ 48 kHz, 1080×1920, 23–60 fps, 3 s–3 min, ≤ 300 MB, ≤ 25 Mbps, moov atom at front, cover image supplied.
Both: media must sit at a public, direct, no-redirect URL Meta can fetch; containers expire after 24 h.

## F. Caption & hashtags (automated where possible)

- [ ] Hook with a number/reversal/question in the first line (search-indexed).
- [ ] ≤ 2200 chars, no external links, a `Source:` line, a photo-credit line.
- [ ] 3–5 specific hashtags, rotated from a pool; never the same set twice; no `#nature`/`#wildlife` mega-tags; never animal-selfie/pet-trade tags.
- [ ] Caption Jaccard similarity < 0.5 versus the last 30 captions.

## G. Readability & design

- [ ] Body text ≥ 36 px, headlines 60–110 px on a 1080-wide canvas; ≤ ~25 words per slide.
- [ ] Reel text inside the safe zone (y 270–1600, x 72–1008); nothing under the bottom action rail.
- [ ] Contrast ≥ 4.5:1 (dark gradient under all text); subject not hidden by text where avoidable.
- [ ] Slide 1 and slide 2 each work standalone (Instagram re-serves slide 2 to non-engagers).

## H. Scoring rubric (score before publishing; publish at ≥ 42/60, no criterion < 5)

Hook strength · Visual quality · Factual accuracy w/ source · Originality/edit value · Readability · Caption/hashtag compliance — each 0–10.

## I. After publishing

- Log post id, time, quota usage, hashtags used, score.
- At +24 h and +7 d pull `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` (reach, saves, shares, likes, comments; Reel watch time) — note insights need ≥ 100 followers for some metrics.
- Review weekly: saves/reach, shares/reach, follows per 1k reach, Reel 3-second hold. Feed results back into the hook/pillar mix.
