# Earthspirit as plugins (plan, waiting for the owner's OK)

Requested 9 Nov 2026 from the "skills and plugins review" chat, section A of
`E:\muddy lessons\07 Automation\2026-11-04 skills and plugins review\plugin-plan-v1.md`.
This chat runs it, because it is the one changing the earthspirit project.

## Where earthspirit lives today
| Place | What | Size |
|---|---|---|
| `E:\Instagram Automated Acc` | about 30 scripts, PIPELINE, CHECKLIST, research, queue, logs, media | about 2 GB, served on GitHub Pages |
| 5 scheduled tasks | autopost, weekly content, insight agent, watchdog, reel studio (plus the old `instagram-autopost`, off and marked safe to delete) | 70 to 110 lines each, a lot of it repeated |
| `social-media-knowledge` plugin | 62 format tags, 159 example reels | 305 KB |
| `platform-guardrails` 0.1.x | RULES (Instagram + YouTube), research, gate hook | shared |

The plugin repo `E:\claude\Claude-skills-agents-plugins` has uncommitted edits from the other chat (guardrails 0.1.3). I will not touch them: all work happens in a separate worktree on the branch `earthspirit-plugins`, from `origin/main`, and ends in a PR.

## Target: 2 plugins

### 1. `platform-guardrails` 0.2.0 (shared by every account)
- `RULES.md` becomes **Instagram only**: hard limits, the NEVER list, hard-stop codes, flag-and-stop and HALT, plus the pre-post checklist.
  - New rule: hashtags in the first comment count toward the cap of 5.
- YouTube rules move to `parked/youtube.md`. They are not loaded and are marked parked. The outdated "unverified project = private uploads" rule is removed there (Google reversed it on 2 Nov 2026; I'll confirm with a source before editing).
- `profiles/earthspirit.md` holds the short per-account part:
  - handle and Composio account id;
  - cadence, with the owner overrides and their dates;
  - CC and stock licensing, audio rules, Reels approval;
  - the "never use the default `muddy_lessons` connection" rule.
- `profiles/_template.md` is a blank for Muddy Lessons later (own media, so no stock licensing). I won't write their profile.
- `SKILL.md` loads the common rules plus the profile named in the project's `config.json` (`"guardrails_profile": "earthspirit"`).
- **Hook fix** (`guardrails_gate.py`):
  - MCP tools are checked by **tool name**. For Composio multi-execute, only the `tool_slug` values are checked, not the rest of the text.
  - Bash and PowerShell are checked only when the command **runs** a publisher: `python publish.py publish`, or a curl POST to the Graph API. Words inside grep, cat, git, echo, heredocs and quoted text don't count.
  - Write, Edit and session messages are never scanned.
  - New tests (`hooks/tests/test_gate.py`):
    - true positives that must still block: Composio `INSTAGRAM_POST_IG_USER_MEDIA` and `..._PUBLISH`, `python scripts/publish.py publish x`, a Graph API POST;
    - false positives that must pass: the 3 real ones from this week (a grep for publish.py, a session message, a doc write).
  - The pass and HALT behaviour is unchanged.

### 2. `earthspirit-instagram` 0.1.0 (new)
- One skill, **earthspirit-cycle**, with one section per role:
  0. Start of every run: HALT, the dashboard Stop button, the profile.
  1. Research.
  2. Render: carousels, mood Reels, Studio requests.
  3. Queue.
  4. Post: today's autopost steps, word for word, so posting behaviour does not change.
  5. Watch: the watchdog, plus the dashboard heartbeat.
  6. Insights: metrics, inputs, Top 5, acting on accepted items.
  7. Dashboard contract: which collection each role may write.
  8. Never.
- References in the plugin:
  - `references/reel-formats/`: the 62 tags and 159 examples, moved from social-media-knowledge;
  - `references/mood-reels.md`: the owner's Reel rules and the 6 Nov review, from memory;
  - `references/dashboard.md`: the Field Desk URL and collections;
  - `references/pipeline.md`: a summary of PIPELINE.md.
- **The scripts stay in the project.** They render media that GitHub Pages must serve, so the skill points to `project_root` from config rather than copying code.
- Each of the 5 scheduled-task prompts becomes about 5 lines: "Load earthspirit-instagram:earthspirit-cycle. Role: autopost. Profile: earthspirit. Project: E:\Instagram Automated Acc."
- `social-media-knowledge` is retired: taken out of the marketplace, with its folder replaced by a one-line README that points to the new plugin. Nothing outside the PR is deleted.

## Also on the dashboard (from the earlier request)
- A **Safety** tab:
  - Rules, read from the guardrails plugin;
  - Security and flags: every HALT and error, with a red badge on every tab;
  - built as planned in `research/dashboard-safety-plan.md`.
- **What's new this week** on Summary, written by Monday's review.
- **This week's 3 tests** on Learn: the top 3 running experiments, each with its hypothesis, the Reels in it, and the date the result is due.

## Build (using agents)
Three parallel subagents. Two work in their own git worktrees of the plugin repo; the dashboard agent works on the page in this project. I review and merge each.
1. Guardrails split, hook fix and tests.
2. The earthspirit-cycle skill, its references, and the reel-formats move.
3. The dashboard Safety tab, What's new and the 3 tests.

Then I write the 5 short task prompts and open the PR.

## Test run on @earthspirit_nature
1. Install both plugins from the branch locally (`/plugin` marketplace pointed at the worktree) and check the hook tests pass.
2. Dry run each role by hand, with no publishing:
   - autopost up to `publish.py plan` ("READY");
   - one watchdog heartbeat;
   - one insight run;
   - one idle Studio check;
   - weekly content up to topic selection.
3. Swap the 5 task prompts to the short pointers, a minute after a run so none is mid-run. The tasks stay enabled.
4. Live test: watch the next autopost slot post through the new skill, and check the dashboard, log and notification.
5. If anything fails: put the old prompts back (saved under `research/task-prompts-2026-11-09/`) and report.

## Owner decisions before I build
1. Retire `social-media-knowledge` in this PR? (Probably already yes: decisions.md of 6 Nov says the 159 examples stay with earthspirit and are removed from the shared knowledge.)
2. OK to delete the old, disabled `instagram-autopost` task?
3. Should the PR merge to `main` straight after the test run, or wait for your review?
