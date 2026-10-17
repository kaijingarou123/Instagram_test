"""Posting queue for the scheduled autopost task — decides *when* and *what*, never publishes.

    python scripts/post_queue.py status          # queue, next due time, estimated end
    python scripts/post_queue.py next            # exit 0 + prints slug if a post is due now
    python scripts/post_queue.py check           # hashtag rotation along the planned order
    python scripts/post_queue.py record <slug> <media_id> <container_id> [child_id ...]   # log a Composio publish

Timing: after every publish the next slot is drawn at random, MIN_GAP_H..MAX_GAP_H hours later (24..28 h while
the account is in phase 1, days 0-13, because publish.py allows 1 post per rolling 24 h there), and is only
used inside the local posting window (WINDOW_START..WINDOW_END, Asia/Kolkata). A slot that falls outside the
window moves to the next window opening plus a random 0-90 min. Missed slots are never caught up: one post per
due slot. The cadence envelope in publish.py (phase limits, min gap, Reels ban until day 14) still applies on
top of this — run `publish.py plan <slug>` before publishing.

`next` exit codes: 0 due (slug on stdout) · 2 HALT marker present · 3 not due yet · 4 queue finished.
"""
import json
import random
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "log" / "posts.jsonl"
QUEUE = ROOT / "log" / "queue.json"
HALTS = [ROOT / "log" / "HALT", ROOT / "HALT", Path.home() / ".claude" / "platform-guardrails" / "HALT"]

IST = timezone(timedelta(hours=5, minutes=30))
MIN_GAP_H, MAX_GAP_H = 20, 26
PHASE1_GAP_H = (24, 28)          # days 0-13: publish.py allows 1 post per rolling 24 h
WINDOW_START, WINDOW_END = time(8, 0), time(21, 30)


def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(q):
    QUEUE.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def published():
    if not LOG.exists():
        return []
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r.get("status") == "published"]


def gap_range(after):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    start = datetime.fromisoformat(cfg["account_start_date"]).replace(tzinfo=timezone.utc)
    return PHASE1_GAP_H if (after - start).days < 14 else (MIN_GAP_H, MAX_GAP_H)


def into_window(t, rng):
    """Move t forward into the next posting window (local IST), with a random offset if moved."""
    local = t.astimezone(IST)
    start = datetime.combine(local.date(), WINDOW_START, IST)
    end = datetime.combine(local.date(), WINDOW_END, IST)
    if start <= local <= end:
        return t
    opening = start if local < start else start + timedelta(days=1)
    return (opening + timedelta(minutes=rng.randint(0, 90))).astimezone(timezone.utc)


def next_due(q, posts):
    """The due time for the next post; drawn once per published post and stored in queue.json."""
    if not posts:
        return datetime.now(timezone.utc)
    last = max(posts, key=lambda p: p["published_at"])
    if q.get("due_after_media_id") != last["media_id"]:
        rng = random.Random()
        at = datetime.fromisoformat(last["published_at"])
        t = at + timedelta(hours=rng.uniform(*gap_range(at)))
        q["due_after_media_id"] = last["media_id"]
        q["next_due"] = into_window(t, rng).isoformat()
        save_queue(q)
    return datetime.fromisoformat(q["next_due"])


def remaining(q, posts):
    done = {p["slug"] for p in posts}
    return [s for s in q["order"] if s not in done]


def cmd_status():
    q, posts = load_queue(), published()
    rest = remaining(q, posts)
    due = next_due(q, posts)
    print(f"queue: {len(q['order'])} planned, {len(q['order']) - len(rest)} published, {len(rest)} left")
    print(f"gap: random {PHASE1_GAP_H[0]}-{PHASE1_GAP_H[1]} h until day 14, then {MIN_GAP_H}-{MAX_GAP_H} h; window {WINDOW_START:%H:%M}-{WINDOW_END:%H:%M} IST")
    if rest:
        print(f"next: {rest[0]}  due {due.astimezone(IST):%a %d %b %H:%M} IST")
        avg = (MIN_GAP_H + MAX_GAP_H + sum(PHASE1_GAP_H)) / 4
        end = max(due, datetime.now(timezone.utc)) + timedelta(hours=avg * (len(rest) - 1))
        print(f"estimated last post: ~{end.astimezone(IST):%a %d %b} IST")
    for i, s in enumerate(rest, 1):
        print(f"  {i:2}. {s}")


def cmd_next():
    for h in HALTS:
        if h.exists():
            print(f"HALT: {h}: {h.read_text(encoding='utf-8', errors='replace').strip()}")
            return 2
    q, posts = load_queue(), published()
    rest = remaining(q, posts)
    if not rest:
        print("QUEUE FINISHED — every planned post is published.")
        return 4
    due = next_due(q, posts)
    now = datetime.now(timezone.utc)
    if now < due:
        print(f"not due: next is {rest[0]} at {due.astimezone(IST):%a %d %b %H:%M} IST")
        return 3
    local = now.astimezone(IST).time()
    if not (WINDOW_START <= local <= WINDOW_END):
        print(f"not due: outside posting window ({local:%H:%M} IST)")
        return 3
    print(rest[0])
    return 0


def meta_for(slug):
    return json.loads((ROOT / "output" / "carousels" / slug / "meta.json").read_text(encoding="utf-8"))


def cmd_check():
    q = load_queue()
    prev = [h.lower() for h in (published()[-1]["hashtags"] if published() else [])]
    ok = True
    for s in remaining(q, published()):
        cur = [h.lower() for h in meta_for(s)["hashtags"]]
        shared = set(cur) & set(prev)
        flag = "FAIL" if len(shared) > 2 or set(cur) == set(prev) else "ok"
        ok &= flag == "ok"
        print(f"[{flag}] {s}: {len(cur)} tags, shared with previous: {sorted(shared) or '-'}")
        prev = cur
    return 0 if ok else 1


def cmd_record(slug, media_id, container_id, children):
    if any(p["slug"] == slug for p in published()):
        sys.exit(f"{slug} is already logged as published")
    entry = {"published_at": datetime.now(timezone.utc).isoformat(), "slug": slug, "kind": "carousel",
             "status": "published", "media_id": media_id, "container_id": container_id, "children": children,
             "hashtags": meta_for(slug)["hashtags"], "route": "composio", "via": "scheduled autopost"}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"logged {slug} ({media_id})")
    cmd_status()
    return 0


def main():
    a = sys.argv[1:]
    if not a or a[0] == "status":
        return cmd_status()
    if a[0] == "next":
        return cmd_next()
    if a[0] == "check":
        return cmd_check()
    if a[0] == "record" and len(a) >= 4:
        return cmd_record(a[1], a[2], a[3], a[4:])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main() or 0)
