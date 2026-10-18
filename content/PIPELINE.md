# Weekly content pipeline (carousels)

Run by the scheduled task `earthspirit-weekly-content` every Thursday, or by hand. Goal: keep
`log/queue.json` stocked so the autopost task (2 posts a day) never runs dry. New posts go to the END of
the queue, so the owner has several days to review them on the preview page before they post.

## 0. Decide how many
`python scripts/post_queue.py status` → `L` = posts left. Make `N = min(16, 18 - L)` new carousels
(18 = about 9 days at 2 a day). If `N <= 0`, stop: report "queue already has L posts".

## 1. Pick topics
- Never repeat a species or angle already in `content/posts/*.json` (list them first).
- Rotate the pillars from `research/content-strategy.md` §3 in this proportion per batch:
  Species spotlight, Myth-bust, How does it survive?, Conservation status, Weird nature, Scale/comparison.
- Lean on species with good wild CC photos on Wikimedia Commons. Mix regions; at least a third Indian
  subcontinent species (the owner's audience), the rest global. Mix mammals, birds, reptiles/amphibians,
  insects, ocean life.
- Write the list (slug, pillar, one-line angle) into the batch report before writing any spec.

## 2. Write, research, render (split across 3-4 parallel subagents, 3-5 posts each)
Each writer follows these rules exactly. The two reference specs to copy structure, tone and quality from are
`content/posts/axolotl-never-grows-up.json` and `content/posts/wolf-alpha-myth.json`; read `scripts/make_carousel.py`
for slide types (cover, fact, stat, compare, closing).

**Spec** `content/posts/<slug>.json`: 6-8 slides. Cover hook <= 10 words (a specific number, reversal or question).
3-5 fact/stat/compare slides, <= 25 words body each. Closing slide with a varied headline (save/send CTA, never
"tag a friend", never engagement bait), body ending "Follow @<handle>." where `<handle>` is `ig_username` in
`config.json`, and a sources list. Fields: slug, slides, caption, hashtags, sources (URLs), alt_texts (one per slide,
species name included), format_tags (only tags that already exist in other specs).

**House style (hard rules, preflight fails otherwise):**
- No em dashes (—) anywhere: slide text, caption, alt text. Use a comma, colon, full stop or brackets.
  En dashes in numeric ranges (10–18 cm) are fine.
- No emojis anywhere.
- The only @handle allowed is the account's own, from `config.json`. No other names, no tagging sources.

**Facts:** every claim traces to a Tier-1 source opened this run: IUCN Red List (status + assessment year),
Animal Diversity Web, Smithsonian, Cornell/All About Birds, NOAA, Britannica, or the primary paper. Wikipedia only as
a lead. Prefer ranges, say "estimated" where the source does, never upgrade "among the most" to "the most". If a fact
can't be verified, drop it. Put the short source on each slide's `source` field.

**Photos:** `python scripts/fetch_commons.py "<query>"` into a NEW folder (never `--refresh`, never overwrite or delete
anything in `assets/raw/`). Only CC0 / PD / CC BY / CC BY-SA. Look at every photo before using it (Read tool) and
reject zoo/captive shots (or label them "captive" in body, alt text and caption), watermarks, AI-looking images,
wrong species, low resolution. Never the same photo on adjacent slides.

**Caption:** hook line <= 125 chars with common + scientific name; 2-4 sentences with one detail not on the slides;
"Swipe for the full story. Sources on the last slide." or similar; a `Source:` line; a soft CTA (vary it); photo
credit line. 3-5 specific hashtags in the `hashtags` field, at most one of {#wildlifefacts, #naturestudy,
#animalfacts, #wildlifeeducation}, no mega-tags.

**Render and check:** `python scripts/make_carousel.py content/posts/<slug>.json`, then
`python scripts/preflight.py <slug>` must pass fully. Open every slide image and fix bad crops (`focus`), text over
the subject, cut-off text.

Writers must NOT run the publisher, call any Instagram/Composio/Meta API, open instagram.com, or commit/push.
Each writer keeps its scratch scripts in its own folder (shared scratch files have clobbered photos before).

## 3. Integrate (the coordinating run, after all writers finish)
1. `python scripts/preflight.py` → ALL CLEAR across everything.
2. Look at every new carousel yourself (all slides). Reject or fix anything that fails the rules above.
3. Append the new slugs to `order` in `log/queue.json`, interleaving pillars so no two neighbours share one.
4. `python scripts/post_queue.py check` → every line `[ok]` (hashtag rotation). Reorder if needed.
5. `python scripts/build_carousel_preview.py`.
6. Commit (`content/posts`, `output/carousels`, `assets/raw/*/credits.json`, `log/queue.json`) with a message
   listing the new posts, ending with the Co-Authored-By line, and `git push origin main`.
7. Wait until GitHub Pages serves the new slides (compare byte size of a few slides with local, retry every 30 s,
   up to 10 min). If it never does, still report, and say posting will retry.
8. Delete `log/QUEUE_EMPTY` if it exists.

## 4. Report
PushNotification: "Weekly content: N new carousels queued (<first slug> ... ). Review:
https://kaijingarou123.github.io/Instagram_test/output/carousels/index.html" and a final message listing each new
slug with its hook, pillar, sources and any fact or photo dropped.

## Never
Publish anything, touch the autopost task, edit already-posted specs, delete files outside your own new folders,
remove HALT files, or weaken a preflight check to make something pass.
