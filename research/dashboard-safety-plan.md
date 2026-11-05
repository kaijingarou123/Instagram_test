# Field Desk additions: Rules, Security, What's new (plan, not built)

Requested 6 Nov 2026 from the "skills and plugins review" chat. Waiting for the owner's OK before building.

**Placement:** a new **Safety** tab (Rules, then Security) replaces the short checklist under More. The weekly **What's new** panel goes on Summary under the Top 5. That makes 8 tabs in total.

## 1. Rules
- Source: platform-guardrails `RULES.md` (v0.1.1) and `research/posting-limits.md`. `scripts/dashboard_sync.py` parses them into a `rules` collection, so the page never holds hand-typed copies.
- Each row has: rule, value, kind (**Platform limit, fixed** or **Our choice, adjustable**), applies to (both accounts, earthspirit only, or muddy_lessons only) and source.
- Groups:
  - Cadence by account age: wk 1-2 1/day 20 h apart, wk 3-4 2/day 8 h, wk 5+ 3/day 6 h, never more than 10/day, halt at quota 20. Owner overrides are shown as "our choice, changed on date".
  - Captions and hashtags: 3 to 5 hashtags, at most 2 shared with the last post; caption at most 2,200 characters and unique (Jaccard < 0.5); no links; alt text; no em dashes or emojis.
  - Media, licensing and audio. Stock and CC licensing rows are tagged earthspirit only, because Muddy Lessons uses its own photos.
  - The NEVER list, verbatim.
  - Hard-stop codes and what each one triggers.
- YouTube appears as one collapsed "Parked" line.

## 2. Security
- A `flags` collection, one row per HALT, flag-and-stop, error code or guardrail hit: time, account, rule or code, task, evidence, and state (open or cleared by the owner).
- Backfill: the code-4 HALTs on 28 and 29 Oct, the false code-4 catch-up, the watchdog flags on 24 and 28 Oct, and the tasks found off on 2 Nov.
- Sync: publish.py and the watchdog add a row whenever they write HALT, and the insight agent mirrors `log/HALT` and the gate status on every run.
- Alert: a red shield badge with the count of unacknowledged flags on every tab, plus a line in the Summary alert bar. Acknowledging a flag records who saw it, but never clears a HALT. Only the owner deletes HALT.

## 3. What's new (weekly)
- `whatsnew/<ISO week>` holds three lists: new content, rule or guardrail changes (week-over-week diff of `rules`), and research suggestions (Instagram updates and packaging ideas, each with a source link).
- It runs once a week inside the Monday review that already writes the Top 5, so no new task is needed. It uses web tools only, never the Instagram connection.

## 4. Future scope
- Custom thumbnails for YouTube Shorts, said to be allowed from 3 Nov 2026: noted on the Rules tab as "to verify", because YouTube is parked.

## Decisions for the owner
1. Safety as its own tab: yes or no.
2. What's new inside the Monday review, or as a separate weekly task.
