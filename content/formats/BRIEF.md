# Format library — scriptwriter brief

Goal: **3 example reels for every `format:` tag** in the social-media-knowledge vocabulary, for an internal preview page. They are examples of each format done *our* way: a wildlife & nature-education account (@claudes_plan101, run for Muddy Lessons, a nature-education company in Bengaluru running school nature clubs, nature study camps, day trails and tiger-reserve trips). Nothing here gets posted without review.

## Files you need
- Vocabulary (tags, family, risk): `E:\claude\Claude-skills-agents-plugins\plugins\social-media-knowledge\knowledge\tags\reel-formats.json`
- Media you may use: `assets/catalog.md` (refs, duration, orientation, what each shot shows). **Only use refs listed there.** Video refs can take a start time: `video:tiger/01.webm@4.5`.
- Validator: `python scripts/check_specs.py content/formats/specs/<slug>.json` — must print `OK`.
- Engine (read only if needed): `scripts/make_reel2.py`.

## Output
One JSON file per reel: `content/formats/specs/<slug>.json`, slug = `<format id without prefix>-<n>` e.g. `meme-1`, `meme-2`, `meme-3`. The three variants of a format must differ in species, angle and layout mix — not three copies.

```json
{
  "slug": "meme-1",
  "format_tag": "format:meme",
  "family": "humor",                 // copy from vocabulary
  "risk": "medium",                  // copy from vocabulary
  "variant": 1,
  "title": "Short human title for the preview page",
  "tactic_tags": ["tactic:hook-text"],   // optional, vocabulary only
  "storyboard": null,                // or "Film: <what must be shot>" — see below
  "audio": "bed",                    // bed (ambient) | beat (120 bpm, for edits/dance/trend formats) | silent
  "scenes": [ { "layout": "...", "duration": 3.5, ... } ],
  "caption": "Hook line\n\nBody (1–3 sentences, one fact not on screen)\n\nSource: …  Photos/video: Wikimedia Commons (credits on screen).",
  "hashtags": ["#species", "#topic", "#wildlifefacts"],   // 3–5, specific, no #nature/#wildlife
  "sources": ["https://… Tier-1 source URL for every factual claim"],
  "notes": "One line: why this is a good/representative example of the format, and what makes it original."
}
```

Total length **10–20 s** (validator allows 8–35), **2–6 scenes**, each 2–6 s. First scene = the hook, readable in under 1.5 s.

## Layouts (scene fields)
| layout | required | optional | use for |
|---|---|---|---|
| `full` | media | kicker, headline, body, source, subtitle[], anchor (bottom/center/top), motion (in/out/pan-left/pan-right), focus [x,y] | default full-bleed shot + text |
| `stat` | media, stat (≤10 chars), label | body, source | one big number |
| `meme` | media, top_text (≤110) | bottom_text (≤40) | white caption band above the clip |
| `split` | media, media_b | label_a, label_b, kicker, headline, body | comparisons, reaction, brainrot (top clip + bottom clip) |
| `pip` | media | media_b (inset) or pip_label (placeholder silhouette), headline, body | reaction / commentary, picture-in-picture |
| `card` | — | bg (ink/amber/moss/cream/night/white/red), big (huge number/emoji-free text), kicker, headline, body, source, media (thumbnail) | list numbers, quiz questions, title cards |
| `quote` | headline | bg, body (attribution) | text-only quote |
| `wipe` | media, media_b | label_a, label_b, headline | before/after, transformation, then/now |
| `grid` | media_list (4 refs) | kicker, headline | compilations |
| `chart` | headline, bars [{label, value, display?}] | kicker, unit, highlight (index), source, bg | data visual, comparisons with numbers |

`subtitle`: list of short caption chunks (2–5 words each) shown in sequence, big white text — use for voiceover-style formats (faceless-voiceover, storytime, split-screen-brainrot, clipfarming, news-commentary). There is no real voice; the subtitles carry the script.

Text limits (validator): headline ≤ 90, body ≤ 190, kicker ≤ 26, label ≤ 60, source ≤ 70 characters. Keep body ≤ 25 words. Headlines ≤ 10 words read best.

## Storyboard reels
Some formats need a human performance or footage we don't have (skit, prank, vlog, GRWM/routine, fitness, food, dance, music cover, art process, testimonial, UGC ad, product demo, unboxing, behind the scenes, field vlog, reaction with a real reactor, AI-generated formats, trending audio lip-sync). For those, still build a complete reel from the available media and text, and set `"storyboard": "Film: <the exact shot(s) to film, e.g. naturalist to camera at a trailhead, 2 takes>"` (≤ 110 chars). Write the on-screen text as the real reel would have it. Tie commercial formats to Muddy Lessons offerings (nature study camps, day trails in Bengaluru, school nature clubs) — no prices, no dates, no fake testimonials attributed to real people (use "Parent, Bengaluru" style, and note it's a placeholder in `notes`).

## Risk handling
- `low`: make it properly.
- `medium`: make it, and say in `notes` what makes our version original.
- `high` (clipfarming, compilation, aggregator-repost, fan-edit, split-screen-brainrot, predation, cute-animal): make the example **with our CC media**, and in `notes` state that the real format is high-risk with third-party footage and only OK with our own.
- `avoid` (rescue-story, ai-animal): make an **anti-pattern explainer** — what the format looks like and why we never post it (e.g. "5 signs a rescue video is staged"). The engine stamps an AVOID band automatically. Never fabricate a fake rescue narrative presented as real.

## Accuracy rules (non-negotiable)
- Every factual claim on screen or in the caption must be true and backed by a Tier-1 source in `sources` (IUCN Red List, Animal Diversity Web, Cornell Lab, NOAA, Smithsonian, National Geographic, peer-reviewed papers, Britannica). Verify numbers with a quick web search when unsure; prefer ranges and "about"; say "estimated" when the source does.
- Media must match the words: don't caption a leopard clip as a tiger. Check `catalog.md`'s "shows" column; zoo/captive shots must not be described as wild behaviour.
- No engagement bait ("comment YES", "tag 3 friends"), no clickbait that isn't paid off, no external links.
- Indian species are welcome and on-brand (tiger, leopard, elephant, kingfisher, peafowl, hornbill, macaque, sloth bear, king cobra, gharial…).

## Done
All your specs pass `check_specs.py`. Report: list of slugs written, which are storyboard, and any format where media was thin.
