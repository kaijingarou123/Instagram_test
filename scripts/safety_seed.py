"""Build the seed documents for the Field Desk Safety tab.

    python scripts/safety_seed.py

Writes two JSON files that the lead pushes to the dashboard database (nothing here talks to claude.ai or Instagram):
    log/dashboard/seed/rules.json   the `rules` collection: one doc per rule, stable ids
    log/dashboard/seed/flags.json   the `flags` collection: the real HALT and flag history to date

Rules are hand-encoded from the platform-guardrails RULES.md (v0.1.1, Instagram sections only; YouTube is parked)
plus the owner's decisions for @earthspirit_nature (log/agent/decisions.json, scripts/publish.py, the autopost
task prompt). Each doc: {id, group, text, value, kind: "platform"|"ours", applies: "both"|"earthspirit"|
"muddy_lessons", changed_at?, source, order}.

Flags come from log/watchdog.json, log/agent/activity.jsonl, log/agent/insights.json, log/agent/plans.json and
log/agent/decisions.json. Each doc: {id, at, account, kind, rule_or_code, task, evidence, state, cleared_at?}.
All historical flags are "cleared".
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "log" / "dashboard" / "seed"

G = "platform-guardrails RULES.md v0.1.1"
PUB = "scripts/publish.py"
AUTO = "research/task-prompts-2026-11-09/earthspirit-autopost.md"

# (id, group, text, value, kind, applies, changed_at, source)
RULES = [
    # ---------------------------------------------------------------- cadence by account age
    ("cad-api-quota", "cadence", "API publish quota", "Read live before every publish. Meta allows 50 to 100 a day; we halt at a quota use of 20.", "platform", "both", None, G),
    ("cad-quota-halt", "cadence", "Halt at quota 20", "If quota_usage is 20 or more, write HALT and stop.", "ours", "both", None, G),
    ("cad-call-rate", "cadence", "Platform call rate", "200 calls per user per hour, shared by publishing, comments and reads.", "platform", "both", None, G),
    ("cad-ceiling", "cadence", "Daily ceiling", "Never more than 10 API publishes in a day, whatever the phase.", "ours", "both", None, G + "; " + PUB),
    ("cad-wk1-2", "cadence", "Weeks 1 to 2", "1 post a day, at least 20 h apart.", "ours", "both", None, G),
    ("cad-wk3-4", "cadence", "Weeks 3 to 4", "2 posts a day, at least 8 h apart.", "ours", "both", None, G),
    ("cad-wk5", "cadence", "Week 5 onwards", "3 posts a day, at least 6 h apart.", "ours", "both", None, G),
    ("cad-ml-plan", "cadence", "Muddy Lessons weekly plan", "2 Reels and 1 to 2 carousels a week, well inside the ladder.", "ours", "muddy_lessons", None, "research/muddy_lessons/claude-build-prompt.md"),
    ("cad-es-2026-10-18", "cadence", "Two posts a day from day 0", "2 a day, at least 8 h apart, on days 0 to 12. Owner accepted the higher new-account risk.", "ours", "earthspirit", "2026-10-18T18:05:10+00:00", "log/agent/decisions.json (two-a-day)"),
    ("cad-es-2026-10-28-catchup", "cadence", "Catch-up days, 28 Oct to 1 Nov", "Up to 7 a day, at least 2 h apart, to clear the carousel backlog. 31 Oct and 1 Nov were added after the false code 4 HALT.", "ours", "earthspirit", "2026-10-28T09:00:38+00:00", "log/agent/decisions.json (catch-up-and-reels-approved, false-code4-catchup)"),
    ("cad-es-2026-10-30", "cadence", "From 30 Oct", "Up to 4 a day, at least 3 h apart. Up to 2 Reels a day and 14 a week. Never two Reels in a row.", "ours", "earthspirit", "2026-10-28T09:00:38+00:00", "log/agent/decisions.json; " + PUB),
    ("cad-es-2026-11-09-trial", "cadence", "Reel-leaning trial", "2 Reels and 1 carousel a day, inside the 4 a day, 3 h envelope.", "ours", "earthspirit", "2026-11-09T12:51:18+00:00", "commit d6d1cde; scripts/post_queue.py"),
    ("cad-reels-approval", "cadence", "Reels only after owner approval", "A Reel posts only once the owner has approved it. Approved Reels are never overwritten.", "ours", "earthspirit", "2026-10-27T20:34:46+00:00", "log/agent/decisions.json (three-slots-reels-approval)"),

    # ---------------------------------------------------------------- captions and hashtags
    ("cap-hashtag-cap", "captions", "Hashtags per post", "3 to 5. Hashtags in the first comment count toward the 5.", "ours", "both", None, G),
    ("cap-hashtag-rotate", "captions", "Hashtag rotation", "Never the same set twice. At most 2 shared with the previous post.", "ours", "both", None, G),
    ("cap-hashtag-bad", "captions", "No risky tags", "No generic mega-tags and no animal plus selfie, pet or for-sale tags.", "ours", "both", None, G),
    ("cap-length", "captions", "Caption length", "At most 2,200 characters. We aim for 1,500 or less.", "platform", "both", None, G),
    ("cap-unique", "captions", "Unique caption", "Word overlap (Jaccard) under 0.5 against each of the last 30 captions.", "ours", "both", None, G + "; scripts/preflight.py"),
    ("cap-source", "captions", "Source and credit lines", "Every caption has a Source line and a credit line.", "ours", "both", None, G),
    ("cap-no-links", "captions", "No external links", "No links in captions.", "ours", "both", None, G),
    ("cap-alt", "captions", "Alt text", "alt_text is set on every image.", "ours", "both", None, G),
    ("cap-house-style", "captions", "No em dashes or emojis", "House style for captions and slides. Preflight fails the post otherwise.", "ours", "both", "2026-10-17T14:17:00+00:00", "log/agent/decisions.json (house-style)"),

    # ---------------------------------------------------------------- media, licensing and audio
    ("med-originality", "media", "Original, edited media only", "Every post is a materially edited asset. A raw CC photo, a third-party clip, a crop, a border or a caption alone counts as unoriginal.", "platform", "both", None, G + " (Instagram rule of 30 Apr 2026)"),
    ("med-licences", "media", "Allowed licences", "Public domain, CC0, CC BY and CC BY-SA, or Pexels, Unsplash and Pixabay when edited.", "ours", "earthspirit", None, G),
    ("med-no-nc-nd", "media", "No NC or ND licences", "Non-commercial and no-derivatives material is never used.", "ours", "earthspirit", None, G),
    ("med-attribution", "media", "Attribution in the caption", "Author, licence and version, and a source link.", "ours", "earthspirit", None, G),
    ("med-image-spec", "media", "Image files", "JPEG, sRGB, at most 8 MB, aspect 4:5 to 1.91:1.", "platform", "both", None, G),
    ("med-reel-spec", "media", "Reel files", "MP4, H.264 and AAC, at most 300 MB, 9:16, faststart.", "platform", "both", None, G),
    ("med-url", "media", "Media URL", "Public direct URL that answers 200 with no redirect.", "platform", "both", None, G),
    ("aud-allowed", "media", "Allowed audio", "None, our own, CC0 or public domain, or the Meta Sound Collection.", "ours", "both", None, G),
    ("aud-clip-sound", "media", "Natural sound of the clip", "The wildlife clip's own sound, credited with the clip. No music or human speech in it, and listened to before approval.", "ours", "earthspirit", "2026-10-28T09:00:38+00:00", G + " (owner decision 2026-10-28)"),
    ("aud-owner-tracks", "media", "Tracks the owner downloads", "A Pixabay track that is not registered with Content ID, or AI music made on a plan that grants commercial rights. Page or terms URL recorded.", "ours", "earthspirit", "2026-10-28T09:00:38+00:00", G + " (owner decision 2026-10-28)"),
    ("aud-never", "media", "Never commercial music", "No Content ID tracks, no NC or ND audio, no trending or chart songs.", "platform", "both", None, G),
    ("aud-no-voice", "media", "Calm music, no narration", "Reels use calm nature-style music and on-screen text. Never TTS or an AI voice.", "ours", "earthspirit", None, "owner rule (memory: reels-soothing-music-no-narration)"),

    # ---------------------------------------------------------------- NEVER (Instagram items only)
    ("nev-0-above-all", "never", "Nothing publishes unless the checks passed", "The pre-action checklist passed in the same run, no HALT exists, and the post is inside the cadence.", "platform", "both", None, G + " section 0"),
    ("nev-1-bursts", "never", "Posting bursts", "Publishes closer than the minimum gap, more than the daily ceiling, or catching up missed slots without an owner decision.", "platform", "both", None, G + " NEVER 1"),
    ("nev-2-duplicates", "never", "Duplicate captions or hashtags", "Identical or near-identical captions, or the same hashtag block twice in a row.", "platform", "both", None, G + " NEVER 2"),
    ("nev-3-stuffing", "never", "Hashtag stuffing", "More than 5 hashtags, generic mega-tags, or animal-selfie and pet-trade tags.", "platform", "both", None, G + " NEVER 3"),
    ("nev-4-repost", "never", "Reposting raw third-party media", "An unedited CC photo, a stock clip, a screenshot, another creator's video, or anything with a third-party watermark.", "platform", "both", None, G + " NEVER 4"),
    ("nev-5-music", "never", "Commercial or unlicensed audio", "Any audio without a verifiable licence in the ledger.", "platform", "both", None, G + " NEVER 5"),
    ("nev-6-engagement", "never", "Automated engagement", "Follow or unfollow churn, mass follows, auto-likes, auto-comments, auto-replies, auto-DMs, engagement bait or incentives.", "platform", "both", None, G + " NEVER 6"),
    ("nev-7-bypass", "never", "Bypassing limits", "Retry loops, second apps or accounts, proxies, undocumented endpoints, password-login tools or scraping.", "platform", "both", None, G + " NEVER 7"),
    ("nev-8-codes", "never", "Ignoring error codes", "Treating a hard-stop code as transient, retrying after one, or continuing while a HALT exists.", "platform", "both", None, G + " NEVER 8"),
    ("nev-10-evidence", "never", "Deleting or hiding evidence", "Removing a HALT marker, log lines or the licence ledger to make a check pass. Only a human clears a HALT.", "platform", "both", None, G + " NEVER 10"),
    ("nev-11-misleading", "never", "Misleading content", "Clickbait, invented facts, unverified species claims, or realistic AI media without disclosure.", "platform", "both", None, G + " NEVER 11"),
    ("nev-12-workaround", "never", "Working around a restriction", "Re-posting or switching accounts to get around a restricted account.", "platform", "both", None, G + " NEVER 12"),
    ("nev-13-scraping", "never", "Logged-in scraping", "Fetching instagram.com with the account's session, token or cookies, or doing research through the publishing connection.", "platform", "both", None, G + " NEVER 13"),

    # ---------------------------------------------------------------- hard-stop codes
    ("code-hard", "codes", "Codes 4, 9, 17, 25, 190, 613, 80002", "HALT: write the HALT file, stop every task, tell the owner. No retry.", "platform", "both", None, G + "; " + PUB),
    ("code-subcodes", "codes", "Subcodes 2207051, 2207050, 2207042, 1996", "HALT, the same as the hard-stop codes.", "platform", "both", None, PUB),
    ("code-transient", "codes", "Transient subcodes 2207001, 2207032, 2207053, 2207027", "One retry after 60 s. If it fails again, HALT.", "platform", "both", None, G + " section 3; " + PUB),
    ("code-connector", "codes", "Connector paused mid-publish", "A half-finished container is a hard stop, not a retry.", "platform", "both", None, G + " (Composio)"),
    ("code-4-exception", "codes", "Code 4 on the final publish call", "Check once whether the post went live. If it did, log it and do not HALT. If not, or the check fails, HALT. A code 4 on any earlier call still HALTs.", "ours", "earthspirit", "2026-10-31T05:59:58+00:00", AUTO),
    ("code-clear", "codes", "Clearing a HALT", "Only the owner clears a HALT, by deleting the HALT file. Every task checks for it first and exits while it exists.", "platform", "both", None, G + " section 3"),
]

FLAGS = [
    {"id": "2026-10-24-github-pages-404", "at": "2026-10-24T10:21:00+00:00", "account": "earthspirit", "kind": "flag",
     "rule_or_code": "Media host down: GitHub Pages 404, posting stalled", "task": "earthspirit-watchdog",
     "evidence": "Media URLs on GitHub Pages answered 404, so every publish check failed and the weaver ant slot was missed. Insight runs reported GitHub Pages failing until it came back at 23:45 UTC 24 Oct.",
     "state": "cleared", "cleared_at": "2026-10-24T23:45:00+00:00"},
    {"id": "2026-10-28-autopost-missed-slots", "at": "2026-10-28T07:25:00+00:00", "account": "earthspirit", "kind": "flag",
     "rule_or_code": "Autopost missed slots: no post since 26 Oct", "task": "earthspirit-watchdog",
     "evidence": "PC asleep 01:18 to 11:37 IST 27 Oct, then a network error on the 11:37 IST autopost run; sea turtle missed its slot. Offline again 02:18 to 10:57 IST 28 Oct. Posting resumed with sea turtle at 08:49 UTC 28 Oct.",
     "state": "cleared", "cleared_at": "2026-10-28T08:49:00+00:00"},
    {"id": "2026-10-28-code4-flamingo", "at": "2026-10-28T09:04:00+00:00", "account": "earthspirit", "kind": "halt",
     "rule_or_code": "Code 4: Application request limit reached", "task": "manual publish (flamingo-pink-diet)",
     "evidence": "media_publish for flamingo-pink-diet answered code 4 at 09:04 UTC, 15 min after sea turtle (08:49 UTC). Quota was 1/100, so a call-rate reply. HALT written to log/HALT and the guardrails HALT. False alarm: the post went live.",
     "state": "cleared", "cleared_at": "2026-10-29T08:44:00+00:00"},
    {"id": "2026-10-29-code4-sloth-bear", "at": "2026-10-29T12:02:00+00:00", "account": "earthspirit", "kind": "halt",
     "rule_or_code": "Code 4: Application request limit reached", "task": "earthspirit-autopost (sloth-bear-termite-vacuum)",
     "evidence": "HTTP 403 code 4 on media_publish for sloth-bear-termite-vacuum, container 18149096341556793, quota 1/100 before the call, 3.3 h after the orca Reel. False positive: the post went live. Owner cleared the HALT on 31 Oct (commit 47dc4a9); 29 Oct evening and 30 Oct were lost.",
     "state": "cleared", "cleared_at": "2026-10-31T05:59:58+00:00"},
    {"id": "2026-11-02-tasks-disabled", "at": "2026-11-02T03:01:00+00:00", "account": "earthspirit", "kind": "flag",
     "rule_or_code": "All scheduled tasks off", "task": "all tasks",
     "evidence": "No task ran from 03:01 UTC 2 Nov to about 20:48 UTC 5 Nov: the owner had paused them. No posts for 4 days and account reach fell to 0. All tasks running again from 20:48 UTC 5 Nov.",
     "state": "cleared", "cleared_at": "2026-11-05T20:48:00+00:00"},
]

KEYS = ("group", "text", "value", "kind", "applies", "changed_at", "source")


def rule_docs():
    docs, seen = [], set()
    for i, (rid, *vals) in enumerate(RULES):
        if rid in seen:
            raise SystemExit(f"duplicate rule id {rid}")
        seen.add(rid)
        d = {"id": rid, **dict(zip(KEYS, vals)), "order": (i + 1) * 10}
        if d["changed_at"] is None:
            del d["changed_at"]
        docs.append(d)
    return docs


def check_style(docs):
    bad = [d["id"] for d in docs if any(ch in json.dumps(d, ensure_ascii=False) for ch in ("—", "–"))]
    if bad:
        raise SystemExit(f"em or en dash in: {', '.join(bad)}")


def main():
    rules, flags = rule_docs(), FLAGS
    check_style(rules + flags)
    SEED.mkdir(parents=True, exist_ok=True)
    (SEED / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (SEED / "flags.json").write_text(json.dumps(flags, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    by_group = {}
    for r in rules:
        by_group[r["group"]] = by_group.get(r["group"], 0) + 1
    print(json.dumps({"rules": len(rules), "rules_by_group": by_group, "flags": len(flags),
                      "files": [str(SEED / "rules.json"), str(SEED / "flags.json")]}, indent=1))


if __name__ == "__main__":
    main()
