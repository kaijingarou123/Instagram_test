"""Posting queue for the scheduled autopost task — decides *when* and *what*, never publishes.

    python scripts/post_queue.py status          # queue, next due time, estimated end
    python scripts/post_queue.py next            # exit 0 + prints slug if a post is due now
    python scripts/post_queue.py check           # hashtag rotation along the planned order
    python scripts/post_queue.py record <slug> <media_id> <container_id> [child_id ...]   # log a Composio publish

Timing (owner decisions 2026-10-28): three fixed daily slots in IST, morning, afternoon and evening (SLOTS).
After each publish the next post is due at a random time in the next slot that starts at least MIN_GAP_H after
it. A due post is only released inside a slot window (with SLACK_MIN of grace at the end), so a slot missed while
the PC was off is never caught up at night: it waits for the next slot.

What: 2 carousels and 1 Reel a day; see pick(). A Reel may go only when the owner has approved it (its slug is in
`approved_reels` in log/queue.json), when no Reel went out in the last 24 h, and within the weekly Reels allowance
in publish.py's PHASES; then it takes the next slot, otherwise carousels fill the slots in queue order. Any post
that would break hashtag rotation against the last post is skipped for now. The cadence envelope in publish.py
still applies on top of this: run `publish.py plan <slug>` before publishing.

`next` exit codes: 0 due (slug on stdout) · 2 HALT marker present · 3 not due yet · 4 queue empty or nothing
eligible.
"""
import json
import random
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import PHASES  # noqa: E402  (one source of truth for the Reels allowance)

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "log" / "posts.jsonl"
QUEUE = ROOT / "log" / "queue.json"
HALTS = [ROOT / "log" / "HALT", ROOT / "HALT", Path.home() / ".claude" / "platform-guardrails" / "HALT"]

IST = timezone(timedelta(hours=5, minutes=30))
SLOTS = [(time(8, 0), time(9, 30)), (time(14, 0), time(15, 30)), (time(20, 0), time(21, 30))]  # IST
SLACK_MIN = 60                     # a due post may still go up to this long after its slot closes
MIN_GAP_H = 6                      # publish.py phase limit: >= 6 h between posts


def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(q):
    QUEUE.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def published():
    if not LOG.exists():
        return []
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r.get("status") == "published"]


def account_day(t):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    start = datetime.fromisoformat(cfg["account_start_date"]).replace(tzinfo=timezone.utc)
    return (t - start).days


def reels_allowed_per_week(t):
    day = account_day(t)
    for lo, hi, _per_day, _gap, reels in PHASES:
        if lo <= day <= hi:
            return reels
    return PHASES[-1][4]


def slot_windows(from_day, days=4):
    """(start, end) UTC datetimes of every slot from `from_day` (an IST date) on."""
    out = []
    for d in range(days):
        day = from_day + timedelta(days=d)
        for a, b in SLOTS:
            out.append((datetime.combine(day, a, IST).astimezone(timezone.utc),
                        datetime.combine(day, b, IST).astimezone(timezone.utc)))
    return out


def next_slot_time(after, rng):
    """A random time in the first slot that still has room at least MIN_GAP_H after `after`."""
    earliest = after + timedelta(hours=MIN_GAP_H)
    for start, end in slot_windows(after.astimezone(IST).date()):
        lo = max(start, earliest)
        if lo <= end:
            return lo + timedelta(seconds=rng.uniform(0, (end - lo).total_seconds()))
    raise RuntimeError("no slot found")


def in_slot(t):
    for start, end in slot_windows(t.astimezone(IST).date() - timedelta(days=1), days=2):
        if start <= t <= end + timedelta(minutes=SLACK_MIN):
            return True
    return False


def next_due(q, posts):
    """The due time for the next post; drawn once per published post and stored in queue.json."""
    if not posts:
        return datetime.now(timezone.utc)
    last = max(posts, key=lambda p: p["published_at"])
    if q.get("due_after_media_id") != last["media_id"] or q.get("schedule") != "slots3":
        q["due_after_media_id"] = last["media_id"]
        q["schedule"] = "slots3"
        q["next_due"] = next_slot_time(datetime.fromisoformat(last["published_at"]), random.Random()).isoformat()
        save_queue(q)
    return datetime.fromisoformat(q["next_due"])


def kind_of(slug):
    if (ROOT / "output" / "carousels" / slug / "meta.json").exists():
        return "carousel"
    if (ROOT / "output" / "reels" / f"{slug}-meta.json").exists():
        return "reel"
    return None


def meta_for(slug):
    if kind_of(slug) == "reel":
        return json.loads((ROOT / "output" / "reels" / f"{slug}-meta.json").read_text(encoding="utf-8"))
    return json.loads((ROOT / "output" / "carousels" / slug / "meta.json").read_text(encoding="utf-8"))


def remaining(q, posts):
    done = {p["slug"] for p in posts}
    return [s for s in q["order"] if s not in done]


def reels_last_7d(posts, now):
    return sum(1 for p in posts if p.get("kind") == "reel"
               and datetime.fromisoformat(p["published_at"]) > now - timedelta(days=7))


def pick(rest, posts, now):
    """The next post that may go now.

    Owner decisions 2026-10-28: 2 carousels and 1 Reel a day, and no Reel goes out until the owner has seen and
    approved it. So a Reel may go only if approved, within the weekly allowance, and when no Reel went out in the
    last 24 h; when one may, it goes first, otherwise the first eligible carousel goes.
    """
    approved = set(load_queue().get("approved_reels", []))
    reel_ok = (reels_allowed_per_week(now) - reels_last_7d(posts, now) > 0
               and not any(p.get("kind") == "reel" and datetime.fromisoformat(p["published_at"]) > now - timedelta(hours=24)
                           for p in posts))
    last = max(posts, key=lambda p: p["published_at"]) if posts else None
    prev_tags = {h.lower() for h in (last or {}).get("hashtags", [])}

    def rotates(s):   # publish.py refuses > 2 hashtags shared with the previous post, or the same set
        cur = {h.lower() for h in meta_for(s)["hashtags"]}
        return cur != prev_tags and len(cur & prev_tags) <= 2

    eligible = [s for s in rest
                if (kind_of(s) == "carousel" or (kind_of(s) == "reel" and reel_ok and s in approved)) and rotates(s)]
    if not eligible:
        return None
    return next((s for s in eligible if kind_of(s) == "reel"), eligible[0])


def cmd_status():
    q, posts = load_queue(), published()
    rest = remaining(q, posts)
    now = datetime.now(timezone.utc)
    due = next_due(q, posts)
    reels_left = sum(1 for s in rest if kind_of(s) == "reel")
    print(f"queue: {len(q['order'])} planned, {len(q['order']) - len(rest)} published, {len(rest)} left "
          f"({len(rest) - reels_left} carousels, {reels_left} Reels)")
    print("slots: " + ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in SLOTS) + f" IST, >= {MIN_GAP_H} h apart; "
          f"Reels this week {reels_last_7d(posts, now)}/{reels_allowed_per_week(now)} (day {account_day(now)})")
    if rest:
        print(f"next: {pick(rest, posts, max(now, due)) or rest[0]}  due {due.astimezone(IST):%a %d %b %H:%M} IST")
        # rough simulation of what can go without new approvals; bounded so it always ends
        sim, t, rng = list(posts), max(due, now), random.Random(0)
        todo, last_t, idle = list(rest), None, 0
        while todo and idle < 9:
            s = pick(todo, sim, t)
            if s is None:
                idle += 1
            else:
                idle = 0
                sim.append({"slug": s, "kind": kind_of(s), "published_at": t.isoformat(),
                            "hashtags": meta_for(s)["hashtags"]})
                todo.remove(s)
                last_t = t
            t = next_slot_time(t, rng)
        if last_t:
            print(f"estimated last post: ~{last_t.astimezone(IST):%a %d %b} IST"
                  + (f" ({len(todo)} not schedulable yet: unapproved Reels or hashtag clashes)" if todo else ""))
    approved = set(q.get("approved_reels", []))
    for i, s in enumerate(rest, 1):
        tag = ""
        if kind_of(s) == "reel":
            tag = "  [Reel, approved]" if s in approved else "  [Reel, waiting for approval]"
        print(f"  {i:2}. {s}{tag}")


def cmd_next():
    for h in HALTS:
        if h.exists():
            print(f"HALT: {h}: {h.read_text(encoding='utf-8', errors='replace').strip()}")
            return 2
    q, posts = load_queue(), published()
    rest = remaining(q, posts)
    if not rest:
        print("QUEUE FINISHED: every planned post is published.")
        return 4
    due = next_due(q, posts)
    now = datetime.now(timezone.utc)
    if now < due:
        print(f"not due: next post at {due.astimezone(IST):%a %d %b %H:%M} IST")
        return 3
    if not in_slot(now):
        print(f"not due: outside the posting slots ({now.astimezone(IST):%H:%M} IST)")
        return 3
    s = pick(rest, posts, now)
    if s is None:
        print("nothing eligible: only Reels are left and none is approved and allowed right now.")
        return 4
    print(s)
    return 0


def cmd_check():
    q = load_queue()
    prev = [h.lower() for h in (published()[-1]["hashtags"] if published() else [])]
    ok = True
    for s in remaining(q, published()):
        if kind_of(s) is None:
            print(f"[FAIL] {s}: not rendered under output/")
            ok = False
            continue
        cur = [h.lower() for h in meta_for(s)["hashtags"]]
        shared = set(cur) & set(prev)
        flag = "FAIL" if len(shared) > 2 or set(cur) == set(prev) else "ok"
        ok &= flag == "ok"
        print(f"[{flag}] {s}{' (Reel)' if kind_of(s) == 'reel' else ''}: {len(cur)} tags, shared with previous: {sorted(shared) or '-'}")
        prev = cur
    return 0 if ok else 1


def cmd_record(slug, media_id, container_id, children):
    if any(p["slug"] == slug for p in published()):
        sys.exit(f"{slug} is already logged as published")
    kind = kind_of(slug)
    if kind is None:
        sys.exit(f"{slug} is not rendered under output/")
    entry = {"published_at": datetime.now(timezone.utc).isoformat(), "slug": slug, "kind": kind,
             "status": "published", "media_id": media_id, "container_id": container_id, "children": children,
             "hashtags": meta_for(slug)["hashtags"], "route": "composio", "via": "scheduled autopost"}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"logged {slug} ({kind}, {media_id})")
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
