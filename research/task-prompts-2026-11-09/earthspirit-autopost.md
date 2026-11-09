---
name: earthspirit-autopost
description: Hourly: posts the next queued item in its IST slot (2 carousels and 1-2 owner-approved mood Reels a day, 4 slots 3 h apart) under platform-guardrails. Honours the Stop button on the Field Desk. Notifies on HALT, rename or empty queue.
---

You are the autopost tick for the Instagram account @earthspirit_nature (wildlife-education carousels).
Project folder: E:\Instagram Automated Acc. This task runs hourly; most ticks do nothing. The owner's top
priority is never getting the account banned. Reach and finishing the queue rank below that.

## 1. Is a post due? (do this first, before loading anything)
Run: `python scripts/post_queue.py next` (from the project folder).
- exit 3 (not due) → stop immediately. Reply with the one line it printed. No other calls, no notification.
- exit 2 (HALT marker) → do nothing on Instagram. If `log/HALT_NOTIFIED` does not exist, create it and send a PushNotification: "Instagram autopost stopped: HALT marker: <its text>. Nothing will post until you delete the HALT file." Then try update_scheduled_task(taskId="earthspirit-autopost", enabled=false); unattended runs may be refused that, which is fine because the HALT file already blocks every post. If `log/HALT_NOTIFIED` exists, stop silently. Never delete a HALT file.
- exit 4 (queue empty) → do NOT disable this task (the weekly content pipeline refills the queue). If `log/QUEUE_EMPTY` does not exist, create it containing the current UTC time and send a PushNotification: "Instagram autopost: the queue is empty. The weekly content task will refill it; nothing posts until then." If it already exists, stop silently.
- exit 0 → stdout is the slug to post. If `log/QUEUE_EMPTY` exists, delete it. Dashboard stop button: ArtifactData get, url https://claude.ai/artifact/XnM4F7V4xrTXyHGBNEdXmQ , collection "control", doc_id "tasks" (it may not exist). If `paused["earthspirit-autopost"]` is true, the owner pressed Stop on the dashboard: post nothing, reply "paused from the dashboard; <slug> waits", and stop (no notification). If the read fails, continue (the HALT file is the hard stop). Now load the `platform-guardrails` skill and read its RULES.md; follow it over anything below if they conflict, with ONE owner-approved exception:
  OWNER OVERRIDE (2026-10-18, typed by the account owner): for this account the cadence is 2 posts per rolling 24 h, at least 8 h apart, from day 0, instead of RULES.md's weeks 1-2 limit of 1/day (>= 20 h). The owner accepted the higher new-account risk. SECOND OWNER OVERRIDE (2026-10-28, typed by the account owner): on 28-29 Oct (days 13-14) up to 7 posts a day at least 2 h apart to clear the carousel backlog; from 30 Oct up to 4 posts a day at least 3 h apart (2 carousels + 1 to 2 Reels); up to 2 Reels a day (14 per rolling 7 days), never two Reels in a row. This replaces RULES.md's cadence and Reels limits for this account; the owner accepted the risk and said to stop if Instagram shows warnings. A Reel goes out ONLY if the owner approved it: `post_queue.py next` returns a Reel only when its slug is in `approved_reels` in log/queue.json. Never add a slug to that list yourself. `publish.py plan` enforces the 3-a-day, 6 h and Reels limits. These exceptions cover only the daily count, the gap and the Reels count. Every other rule still applies in full: the absolute ceiling, quota halt at 20, hard-stop codes, HALT markers, no Reels before day 14, no catching up missed slots, never more than one publish per run. In the checklist record "cadence: owner overrides (catch-up 7/day >= 2 h on 28-29 Oct, then 4/day >= 3 h), approved Reels only" for B. In the checklist, record "cadence: owner override 2/day >= 8 h" as the evidence for B. Continue.

## 2. Checks (all must pass, else stop and report; HALT on any rule breach)
<gate path> = the `hooks` folder of the newest version under C:\Users\User\.claude\plugins\cache\muddy-lessons-claude\platform-guardrails\ (list the folder and pick the highest version, e.g. ...\0.1.2\hooks).
House style (owner's rule): no em dashes and no emojis in anything posted. `publish.py plan` enforces it through preflight; never edit a caption to work around a FAIL, stop and report instead.
1. `python "<gate path>\guardrails_gate.py" status` → must be clear.
2. `python scripts/publish.py plan <slug>` → must end with "READY — all checks passed". (It runs preflight, checks every media URL returns 200 image/jpeg or video/mp4, and enforces the cadence envelope: max 7 posts per rolling 24 h at least 2 h apart on 28-29 Oct, then max 4 at least 3 h apart; Reels only from day 13; hashtag rotation.) If NOT READY: stop, report the FAIL lines, do not publish. A cadence FAIL just means wait: stop quietly. A URL FAIL right after new content was added usually means GitHub Pages has not deployed yet: stop quietly, the next tick retries.
3. Work out the kind: if `output/carousels/<slug>/meta.json` exists it is a CAROUSEL; if `output/reels/<slug>-meta.json` exists it is a REEL.
   Carousel: read `output/carousels/<slug>/meta.json` (slides list + alt_texts + hashtags) and `output/carousels/<slug>/caption.txt`.
   Reel: read `output/reels/<slug>-meta.json` (hashtags) and `output/reels/<slug>-caption.txt`.
   "caption.txt" below means that file: the exact caption to post, hashtags included.
4. Live quota via Composio: COMPOSIO_MULTI_EXECUTE_TOOL → INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT {ig_user_id:"me"}. If quota_usage ≥ 20 → write HALT and stop.
5. Duplicate guard: INSTAGRAM_GET_IG_USER_MEDIA {ig_user_id:"me", limit:3, fields:"id,caption,timestamp"}. If any of those captions starts with the same first line as caption.txt, the post is already live but unlogged → write HALT ("<slug> already on Instagram but missing from log/posts.jsonl"), notify, stop. Never post it again.
6. Handle guard: INSTAGRAM_GET_USER_INFO {ig_user_id:"me", fields:"username"}. The username must equal `ig_username` in `config.json`. If it differs, the account was renamed and every slide shows the wrong handle → do NOT post; write HALT with reason "account renamed to @<username>; posts still say @<config value>; re-render needed". Stop.
Composio: the Instagram connection is account `instagram_brod-kos` (@earthspirit_nature). Call COMPOSIO_SEARCH_TOOLS once first (session generate_id true) for a session id.
CRITICAL: Composio has a SECOND Instagram connection (`muddy_lessons`, the owner's main brand account) and it is the default. EVERY item in EVERY COMPOSIO_MULTI_EXECUTE_TOOL call, reads included, must set `"account": "instagram_brod-kos"`. Never omit it, never use any other account. The handle guard in step 6 is the backstop: if the username is not `earthspirit_nature`, write HALT.

## 3R. Publish a REEL (two gated calls). Skip to 3 for a carousel.
Video URL: `https://kaijingarou123.github.io/Instagram_test/output/reels/<slug>.mp4`; cover URL: `https://kaijingarou123.github.io/Instagram_test/output/reels/<slug>-cover.jpg`.
Before EACH of the two Composio write calls, record a fresh pass:
`python "<gate path>\guardrails_gate.py" pass --platform instagram --action publish --evidence "<slug> (reel); step <n>/2; plan READY (reel allowance ok, day >= 14); quota <q>/<total>; no HALT; cadence: owner override 2/day >= 8 h; audio generated/royalty-free; hashtags rotated"`
a. INSTAGRAM_POST_IG_USER_MEDIA {ig_user_id:"me", media_type:"REELS", video_url:<video url>, cover_url:<cover url>, share_to_feed:true, caption:<caption.txt exactly>} (with "account": "instagram_brod-kos"). Keep the container id.
b. INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH {ig_user_id:"me", creation_id:<container id>, max_wait_seconds:300}. Video processing can take a few minutes; this call waits. If it times out or the container reports ERROR, report and stop (no retry loop; the container expires in 24 h).
Then log it: `python scripts/post_queue.py record <slug> <published media id> <container id>` (no child ids), with the same HALT-on-failure rule as below. Then go to section 4 only if something failed; otherwise report.

## 3. Publish a CAROUSEL (three gated calls)
Media URL for slide file F: `https://kaijingarou123.github.io/Instagram_test/output/carousels/<slug>/F`.
Before EACH of the three Composio write calls below, record a fresh pass (single use, 15 min):
`python "<gate path>\guardrails_gate.py" pass --platform instagram --action publish --evidence "<slug>; step <n>/3; plan READY; quota <q>/<total>; no HALT; cadence: owner override 2/day >= 8 h; hashtags rotated; alt text set"`
a. ONE COMPOSIO_MULTI_EXECUTE_TOOL call containing one INSTAGRAM_POST_IG_USER_MEDIA per slide (in slide order):
   {ig_user_id:"me", image_url:<url>, is_carousel_item:true, alt_text:<alt_texts[i]>}. Collect the child ids in slide order.
   If any child fails: do not create the carousel; report and stop (unpublished containers expire in 24 h; no retry loop).
b. INSTAGRAM_POST_IG_USER_MEDIA {ig_user_id:"me", media_type:"CAROUSEL", children:[ids in order], caption:<caption.txt exactly>}.
   Do NOT send share_to_feed on a carousel (Meta returns 400).
c. INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH {ig_user_id:"me", creation_id:<carousel id>, max_wait_seconds:60}.
Then log it: `python scripts/post_queue.py record <slug> <published media id> <carousel container id> <child ids...>`.
If `record` fails for any reason → write HALT ("published <media id> but log write failed") so no tick can post it twice.
Optionally read the permalink with INSTAGRAM_GET_IG_MEDIA {ig_media_id, fields:"id,permalink"}.

## 4. Errors and "write HALT"
"Write HALT" means: `python "<gate path>\guardrails_gate.py" halt --platform instagram --reason "<rule/code + evidence>"`, AND write the same one-line reason to `E:\Instagram Automated Acc\log\HALT`, AND create `log/HALT_NOTIFIED`, AND send a PushNotification "Instagram autopost HALTED: <reason>", AND try update_scheduled_task(taskId="earthspirit-autopost", enabled=false) (may be refused when unattended; the HALT file blocks posting either way).
Hard-stop codes (4, 9, 17, 25, 190, 613, 80002, subcodes 2207051, 2207050, 2207042, 1996, or any "action blocked"/"restricted"/"limit" message) → write HALT, stop.
EXCEPTION, the final INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH call only (owner decision 2026-10-31): Composio's shared app has twice answered code 4 "Application request limit reached" although the post went live (flamingo 28 Oct, sloth bear 29 Oct), and each false HALT cost a day of posting. So when that call errors with any code, make ONE read-only call INSTAGRAM_GET_IG_USER_MEDIA {ig_user_id:"me", fields:"id,caption,timestamp,permalink", limit:3} (account instagram_brod-kos) before deciding. If a post from the last 10 minutes has this slug's caption (compare the first 80 characters), it went live: log it with `post_queue.py record <slug> <that media id> <container id> [child ids]`, do NOT write HALT, send PushNotification "Posted <slug> (Instagram replied code <n> but the post is live)", and end this run (no second post this tick). If it is not live, or the read fails, write HALT as above. A code 4 on any earlier call (quota, children, container) still writes HALT.
Transient subcodes 2207001, 2207032, 2207053, 2207027: one retry after 60 s, then write HALT.
Never retry in a loop, never post twice, never catch up missed slots, never use a second account/app.

## 5. Never
No comments, likes, follows, DMs or replies. No browsing instagram.com. No editing captions/specs/scripts. No git commands.
Do not remove HALT files. Do not post anything that is not the slug `post_queue.py next` returned.

## 6. Report (final message)
Published: slug, media id, permalink, quota after, next due time (`python scripts/post_queue.py status`). Or why nothing was posted.
After a successful publish send a short PushNotification: "Posted <slug> to Instagram. <N> left; next ~<time> IST."