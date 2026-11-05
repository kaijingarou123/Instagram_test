# Instagram control page v2 (spec)

Owner: Suryansh. Written 2026-11-04 from the owner's review of the v1 dashboard.
This file is the single brief for building v2. Each build session reads this file, not the old chats.

## Goal

One private page that runs the Instagram pipeline with you:

1. One content calendar is the source of truth for what gets posted and when.
2. The agent learns from results on its own. It reviews insights, runs experiments, updates its plan and makes new content.
3. You can see what every task is doing, stop it, and feed in your own ideas (links, videos, screen recordings, notes). The agent turns those into proposed posts.
4. **You can always show it example Reels and posts and it changes what it makes.** This is the most important goal. Any Reel or idea you see can be dropped in at any time, and the agent must update its formats, plan and next posts from it, not keep posting the same kind of thing.
5. **Prove it here, then copy it to Muddy Lessons safely.** This is a test account. Once it grows, the same pipeline moves to the Muddy Lessons account, which is important and must not be put at risk (see Rollout below).

## Brand kit (shared plugin)

Everything that defines how a post looks lives in one brand kit, stored on both laptops (this one and the teammate's) as a plugin, never hard-coded in scripts:
fonts, video format (length, aspect, pacing, text timing), colour scheme, border, framing, background, logos and logo placement.
One kit per account (`earthspirit`, `muddy-lessons`). The renderer reads the kit, so changing the kit changes every new post. Experiments can override one kit value at a time (for example a new colour scheme) and the winner is written back to the kit.

## Rollout to Muddy Lessons

1. Grow the test account until the loops work without hand-holding (target to agree, for example 4 weeks of steady reach growth).
2. Build the Muddy Lessons brand kit from the real assets. Owner pastes or sends them via Slack.
3. Agree a storyline for the account before any automation: who it speaks to, three or four content pillars, and the series formats. It should not just copy the nature account.
4. Shadow mode: the pipeline drafts and schedules into the calendar, but a person approves every post for the first weeks. Insights read-only from day one.
5. Only then autopost, under the same guardrails, at a lower cadence than the test account.

Scope: Instagram only (@earthspirit_nature test account). Facebook and others come later, each on its own page.
Hosting: a claude.ai Artifact. These are private by default; nobody sees it unless you share the link. Same page later for the main account by swapping config.

## Pages: 13 tabs down to 6

| v2 page | Replaces | What's on it |
|---|---|---|
| **1. Summary** | Executive summary | Keep v1 as is. Add a red alert bar at the top (task off, run failed, nothing posted in 24 h) and a short **Needs you** list (Reels to approve, proposals to accept). |
| **2. Plan** | Agent plan, Activity | **Tasks strip** at the top: one row per scheduled task with on/off, doing now, last run, next run, Stop/Resume. **Kanban** below with columns Now, This week, Next week, Later. Cards are tagged Agent or Human. Done and Dropped fold away by week. **Changes feed** on the side: agent and human plan changes, last 7 days by default, with a filter and an older-weeks timeline. |
| **3. Calendar** | Pipeline (unreadable chart), Queue | Week and month grid. Each day shows its slots with a chip per item: Reel or Carousel, and Published, Queued, Draft, Needs approval or Experiment. Click a chip to open the post page. |
| **4. Posts** | Posts, Content library | All Reels and carousels in one list, filtered by Published, Queued, Draft or Experiment. Each post has its own page with likes, reach, saves, shares, watch time and sources. |
| **5. Learn** | AI insights, Experiments, Scan a post | **Insights** as short points grouped by topic (format, time, hook, topic, hashtags), filtered by metric (reach, likes, saves, shares). **Experiments**: running and concluded, each linking to its posts. **Your inputs** (see below). |
| **6. Audience** | Audience and hashtags, Competitors | Audience, **top 20 hashtags** (all hashtags behind a "show all" toggle that scrolls inside its card), competitors. |
| More (collapsed) | Health, Guardrails and docs | Connector health. Guardrails as a 10-line checklist of the rules that matter, with a link to the full skill instead of dumping it. |

"Plan status" and "Who does the work" cards are removed.

## The loops

### Agent learning loop (the review skill)
- A skill, `review-and-plan`, later packaged as a plugin. It runs automatically 24 h after each post and on each full insight run. The **Run review now** button on Learn starts it early.
- It reads the latest posts' metrics and writes or updates insights, concludes or extends experiments, and proposes the next ones (format, length, hook, font, colour scheme, time slot, topic).
- Each proposal becomes a Kanban card and, once approved where needed, a Calendar slot. Plan cards it replaces get marked Dropped with a one-line reason, which shows in the changes feed.

### Human input loop (Your inputs on Learn)
You add a link, a video file or a screen recording, plus one line on why you liked it. Each input then moves through:

1. **Received**: shows on Learn straight away.
2. **Analysed**: on its next run the agent writes a learning card covering what works in it, what we'd borrow, what we won't copy (originality rules) and what it needs from you.
3. **Proposed**: the agent creates an experiment and a draft post. The draft appears in Calendar and Posts tagged Experiment and is linked from the learning card. This answers "where does the new post go".
4. **Your call**: Approve, Change or Reject. Nothing new-format goes out without approval.
5. **Scheduled, then Measured**: results flow back into the experiment.

Your side: approve or reject, and add the one-line why. The agent's side: respond by the next run, never post an unapproved new format, and say when it drops an old plan.

### Visibility and control
- **Heartbeat**: every task writes started, doing (a one-line step) and finished or failed to the page's database. The tasks strip shows these, and a task with no heartbeat past its expected time turns red.
- **Stop/Resume**: the button writes a control document. Every task checks it first and exits if it's paused. Takes effect from the next run; it can't kill a run already in progress.
- **Notifications** to your phone: post published, run failed, task paused or stale, input analysed or proposal ready.

## Weekly rhythm (owner review, 4 Nov)

The page leads with **Top 5 this week**, not with insights. Insights and experiments are the agent's internal notes.
- Monday: the review writes `weekly/<ISO week>` with 5 items (title, why, change, evidence, owner, status).
- The owner accepts, skips or marks each item on the page. Accepted items become the week's work.
- Any time: the owner drops inspirations on Learn. Files over 20 MB go in `inputs/` in the repo (git-ignored) with a one-line note on the page.
- Sunday: results feed next Monday's Top 5. Anything skipped is not proposed again.

## Status (2026-11-04)

Phase 2 page restructure is live at the same link: 7 tabs (Summary, Plan, Calendar, Posts, Learn, Audience, More).
The Calendar tab has a Sheet view built from `Muddy_Lessons_Content_Calendar.xlsx`: all 41 columns, the workbook's dropdown lists, and the same calculated columns.
New page writes the tasks don't read yet: `control/tasks` (pause flags), `control/review`, `inputs`, `sheet` (cell edits and new rows), `plans` with `source: "page"`. Phase 1 and 4 wire the tasks to them, and the tasks must also write `tasks/<task-id>` heartbeats.

New Reel format (4 Nov): `scripts/make_mood_reel.py`, spec `format: "mood"`. It uses 1 to 4 cuts of 1080p CC footage, one line of Georgia Italic, music from assets/music, and puts the fact and credits in the caption. The first three test Reels wait for owner approval and are not in the queue. 480p clips look soft when cropped to 9:16, so new Reels use only 1080p sources.

## Build phases (one short session each)

1. **Foundations**: heartbeat, control document with Stop/Resume, alert bar, notifications. Edit the task SKILL.md files and `scripts/dashboard_sync.py`. Done when stopping a task from the page skips its next run and a stale task shows red.
2. **Page restructure**: 6 pages, tasks strip and Kanban, calendar grid, top-20 hashtags, guardrails checklist. Done when every v1 number still appears somewhere and nothing scrolls the whole page sideways or for ever.
3. **Learning loop**: `review-and-plan` skill plus the Run review button, and the experiment lifecycle linked to posts.
4. **Human inputs**: upload and link intake, learning cards, proposal to draft to approval flow.
5. **Turn back on**: re-enable tasks, watch one full day, then decide on the plugin packaging and the main-account copy.

House rules: no em dashes or emojis in page copy, never overwrite an approved Reel (new slug with `variant_of`), Reels use calm music and no narration, and everything goes through platform-guardrails.
