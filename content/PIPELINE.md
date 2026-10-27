# Weekly content pipeline (carousels and Reels)

Run by the scheduled task `earthspirit-weekly-content` every Thursday, or by hand. Goal: keep
`log/queue.json` stocked so the autopost task (3 posts a day from 29 Oct: 2 carousels + 1 owner-approved Reel)
never runs dry. New posts go to the END of the queue, so the owner has several days to review them on the preview
pages before they post.

## 0. Decide how many
`python scripts/post_queue.py status` → `Lc` = carousels left, `W` = Reels left (status prints both).
- Carousels: `C = min(16, 18 - Lc)` (18 = about 9 days at 2 a day).
- Reels: `R = min(7, 9 - W)`, so about 7 a week (1 a day) and never more than 9 waiting. Reels are the discovery
  format below 1,000 followers (research 28 Oct). Each one posts only after the owner approves it on the review
  page, so unapproved Reels count towards `W` and slow the next batch down instead of piling up.
If `C <= 0` and `R <= 0`, stop: report "queue already has Lc carousels and W Reels". `N = C + R`.

## 1. Pick topics
- Never repeat a species or angle already in `content/posts/*.json` or `content/reels/*.json` (list both first).
- Rotate the pillars from `research/content-strategy.md` §3 in this proportion per batch:
  Species spotlight, Myth-bust, How does it survive?, Conservation status, Weird nature, Scale/comparison.
- Lean on species with good wild CC photos on Wikimedia Commons. Mix regions; at least a third Indian
  subcontinent species (the owner's audience), the rest global. Mix mammals, birds, reptiles/amphibians,
  insects, ocean life.
- A Reel topic needs one fact that works on its own in 10 seconds (a reversal, a number, a "that is not X") AND a
  usable CC clip of that species. Check the footage before committing to a Reel topic (step 2R); if none is good,
  make it a carousel instead.
- Write the list (slug, kind, pillar, one-line angle) into the batch report before writing any spec.

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

## 2R. Reels: the loop format (`scripts/make_loop_reel.py`)
Give the Reels to their own 2 writers (3-4 Reels each) with these rules plus the house style, facts and caption
rules above. Reference specs: `content/reels/kingfisher-blue-not-pigment.json`, `peacock-train-not-tail.json` and
`leopard-tree-larder.json`; the renderer's docstring lists every field.

**Format** (Instagram ranks Reels on watch time and replays, sends per reach, and originality):
- 7-15 s by default (up to 30 s for the length experiment), ONE continuous real wildlife clip, cropped to 9:16. No photo slideshows, no pans over stills
  (`make_reel.py` is the old still-photo renderer; do not use it for new Reels).
- Beat 0 is the hook (<= 8 words), on screen from frame 0; that frame is also the cover. Then 1-2 beats deliver ONE
  sendable fact (<= 16 words each, about 3.5-4.5 s per beat). No intro, no logo sting, no "follow for more" card.
- The renderer loops it: the last 0.6 s dissolves back into the opening footage and the hook text, so the replay is
  seamless. Check its printout: `loop seam` must be no bigger than about the `frame step` printed next to it.
- Text stays inside the Reels safe zone (from y 380, clear of the right action rail); species, source and video
  credit sit above the caption area on every frame, and the credit is appended to the caption automatically.
- Audio comes from the spec's `audio` block (see Experiments for which to use):
  `"bed": true` = a pad the renderer synthesises (repeats exactly once per loop, plus a tick on each beat);
  `"natural": <gain>` = the clip's own soundtrack, loop-dissolved like the picture (ON HOLD: platform-guardrails
  allows only none, own/CC0 or Meta Sound Collection audio, so this arm needs the owner's ruling before any such
  Reel is queued; preflight fails it until then); `"music": {"file", "title", "licence"}` = a Meta Sound Collection
  track the owner downloaded (Claude cannot fetch these). Never trending audio, commercial music or any other track.

**Footage** (same licence rules as photos: CC0 / PD / CC BY / CC BY-SA only, never NC/ND, never a raw clip posted as is):
1. Find clips: `python scripts/fetch_commons_video.py "<species>=<alt name>"` writes up to 3 candidates into a
   NEW folder `assets/video/<slug>/` (it skips a folder that already has credits). Contact-sheet each candidate in
   your scratch folder (`ffmpeg -i X.webm -vf "fps=1,scale=320:-1,tile=6x5" -frames:v 1 sheet.jpg`) and look at it.
2. Reject captive / zoo / circus / pet footage (or say "captive" on screen and in the caption), the wrong species,
   watermarks or burned-in text, shaky footage or a tiny subject, and AI-generated video (`assets/video/ai-generated`
   is off-limits). Read the Commons description for where it was filmed and say so in the caption.
3. Fetch the chosen clip in HD: `python scripts/fetch_commons_video.py --file "File:<exact title>" <slug>-hd`
   (1080p transcode; the species search may only have 480p, which is too soft for a 9:16 crop).
4. Pick `clip.start` (>= 0.6 s, the loop needs footage before it) and `duration` so the subject stays in frame,
   and the end looks enough like the start for the dissolve to read as one motion.
5. `clip.focus` [x, y] centres the crop. If the subject would sit under the text (close-ups), use blur-fill:
   `zoom` 0.6-0.75 and `top` 500-600 place the footage lower, over a blurred copy of itself.

**Spec** `content/reels/<slug>.json`: slug, format "loop", species "Common name (Genus species)", clip, duration,
beats [{at, text}] with the hook at 0, source (short, shown on screen), caption, hashtags, sources (URLs), alt_text,
format_tags (`format:fact-over-footage`, plus `format:myth-bust`, `format:explainer` or `format:predation`, plus
`tactic:hook-text`), audio, experiment, voice (if that arm), and `credit_artist` only when the Commons author field
is messy.
**Caption** as for carousels, except: the CTA is a send line that names who to send it to (vary it), never "tag a
friend" or "share if"; no "swipe" line. The renderer appends the video credit (author, licence, Commons file).

**Voice:** `"voice": {"name": "Microsoft Zira Desktop", "rate": 1}` narrates each beat (or its `say` text) with
Windows text-to-speech and retimes the beats to the narration (still within the length cap). The caption then gets
"Narration: computer-generated voice (text-to-speech)" and the meta gets `"synthetic_voice": true`, so whoever
publishes can apply Instagram's AI label (Meta asks for labels on realistic AI-made audio; check whether the
publishing route can set it, and post by hand with the label on if not).

**Experiments** (owner, 28 Oct; dashboard blocks E2-E5): every Reel carries an `experiment` object that the renderer
copies into its meta, e.g. `{"hook": "number", "audio": "voice+generated-bed", "length": "15s", "theme": "india"}`.
Spread each batch across the arms, changing one variable at a time where possible, so the insight agent can compare:
- hook: `number` (a concrete number first: "150 cm of feathers, and none of it is tail."), `question`
  ("Why does a leopard keep its dinner up a tree?"), `myth` (a flip: "This tarantula is not dead.")
- audio: `generated-bed`, `natural`, `voice+generated-bed`, `voice+natural`, `voice+music` (the last needs an
  owner-supplied Meta Sound Collection file; the natural arms are on hold, see above)
- length: `8s` (7-9 s loop), `15s` (about 15 s), `30s` (about 30 s; needs a clip of 31 s or more)
- theme: `india`, `global` (well-known icons), `tiny-weird` (insects, spiders, odd small creatures)
Evidence behind the format (coordinating session, 28 Oct): 23 of 26 top animal-fact Reels use original audio
(narration or natural sound), and the best captions are one short line with one concrete number.

**Render and check:** `python scripts/make_loop_reel.py content/reels/<slug>.json`, then
`python scripts/preflight.py <slug>` must pass fully. Open `output/reels/<slug>-frames.jpg` (9 frames across the
loop) and `<slug>-cover.jpg`: the text never covers the animal's head, the subject stays in frame, the credit is
readable and the hook is on frame 0.

## 3. Integrate (the coordinating run, after all writers finish)
1. `python scripts/preflight.py` → ALL CLEAR across everything.
2. Look at every new carousel yourself (all slides) and every new Reel (frames sheet, cover, and play the mp4).
   Reject or fix anything that fails the rules above.
3. Append the new slugs to `order` in `log/queue.json`, interleaving pillars so no two neighbours share one and
   spreading the Reels out (never two Reels next to each other). Never add a slug to `approved_reels`: only the owner
   approves Reels, and the autopost task posts a Reel only once its slug is there.
4. `python scripts/post_queue.py check` → every line `[ok]` (hashtag rotation). Reorder if needed.
5. `python scripts/build_carousel_preview.py` and `python scripts/build_reels_review.py`.
6. Commit (`content/posts`, `content/reels`, `output/carousels`, each new Reel's `output/reels/<slug>.mp4`,
   `-cover.jpg`, `-caption.txt` and `-meta.json`, `output/reels/index.html`, `assets/raw/*/credits.json`,
   `assets/video/*/credits.json`, `log/queue.json`) with a message
   listing the new posts, ending with the Co-Authored-By line, and `git push origin main`.
7. Wait until GitHub Pages serves the new slides and Reel mp4s (compare byte size of a few files with local, retry every 30 s,
   up to 10 min). If it never does, still report, and say posting will retry.
8. Delete `log/QUEUE_EMPTY` if it exists.

## 4. Report
PushNotification: "Weekly content: C new carousels and R new Reels queued (<first slug> ... ). Reels post only
after you approve them. Review: https://kaijingarou123.github.io/Instagram_test/output/carousels/index.html and
https://kaijingarou123.github.io/Instagram_test/output/reels/" and a final message listing each new slug with its
kind, hook, pillar, sources, video credit (Reels) and any fact, photo or clip dropped.

## Never
Publish anything, touch the autopost task, edit already-posted specs, delete files outside your own new folders,
remove HALT files, approve a Reel (edit `approved_reels`), add music to a Reel, or weaken a preflight check to make
something pass.
