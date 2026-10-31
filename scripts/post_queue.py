"""Posting queue for the scheduled autopost task — decides *when* and *what*, never publishes.

    python scripts/post_queue.py status          # queue, next due time, estimated end
    python scripts/post_queue.py next            # exit 0 + prints slug if a post is due now
    python scripts/post_queue.py check           # hashtag rotation along the planned order
    python scripts/post_queue.py record <slug> <media_id> <container_id> [child_id ...]   # log a Composio publish

Timing (owner decisions 2026-10-28): fixed daily slots in IST. On the catch-up days (CATCHUP_DAYS, 28-29 Oct) seven
slots at least 2 h apart to clear the carousel backlog; after that four slots at least 3 h apart. After each publish
the next post is due at a random time in the next slot that starts at least the day's gap after it. A due post is
only released inside a slot window (with SLACK_MIN of grace at the end), so a slot missed while the PC was off is
never caught up at night: it waits for the next slot.

What: see pick(). A Reel may go only when the owner has approved it (its slug is in `approved_reels` in
log/queue.json), never right after another Reel, at most REELS_PER_DAY a day and within the weekly Reels allowance in
publish.py's PHASES. Carousels fill the other slots (at most CAROUSELS_PER_DAY a day after the catch-up days). Any post
that would break hashtag rotation against the last post is skipped for now. The cadence envelope in publish.py
still applies on top of this: run `publish.py plan <slug>` before publishing.

`next` exit codes: 0 due (slug on stdout) · 2 HALT marker present · 3 not due yet · 4 queue empty or nothing
eligible.
"""
import json
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
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
# Owner decisions 2026-10-28: clear the carousel backlog on 28-29 Oct (catch-up days, up to 7 posts a day, >= 2 h
# apart), then 2 carousels and 1 to 2 Reels a day (up to 4 posts, >= 3 h apart). Times are IST.
CATCHUP_DAYS = {date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30),    # 30 Oct added: 28 Oct lost to a HALT
                date(2026, 10, 31), date(2026, 11, 1)}    # added: 29 Oct evening and 30 Oct lost to a false code-4 HALT
CATCHUP_SLOTS = [(time(8, 0), time(8, 45)), (time(10, 15), time(11, 0)), (time(12, 30), time(13, 15)),
                 (time(14, 45), time(15, 30)), (time(17, 0), time(17, 45)), (time(19, 15), time(20, 0)),
                 (time(21, 30), time(22, 15))]
NORMAL_SLOTS = [(time(8, 0), time(9, 30)), (time(12, 30), time(13, 30)), (time(17, 0), time(18, 0)),
                (time(20, 30), time(21, 30))]
SLOTS = NORMAL_SLOTS               # shown by `status`
SLACK_MIN = 45                     # a due post may still go up to this long after its slot closes
CATCHUP_GAP_H, NORMAL_GAP_H = 2, 3  # publish.py phase limits for those days
CAROUSELS_PER_DAY = 2              # outside catch-up days
REELS_PER_DAY = 2


def slots_for(day):
    return CATCHUP_SLOTS if day in CATCHUP_DAYS else NORMAL_SLOTS


def gap_for(t):
    return CATCHUP_GAP_H if t.astimezone(IST).date() in CATCHUP_DAYS else NORMAL_GAP_H


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
        for a, b in slots_for(day):
            out.append((datetime.combine(day, a, IST).astimezone(timezone.utc),
                        datetime.combine(day, b, IST).astimezone(timezone.utc)))
    return out


def next_slot_time(after, rng):
    """A random time in the first slot that still has room at least the day's minimum gap after `after`."""
    for start, end in slot_windows(after.astimezone(IST).date()):
        lo = max(start, after + timedelta(hours=gap_for(start)))
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
    if q.get("due_after_media_id") != last["media_id"] or q.get("schedule") != "slots4":
        q["due_after_media_id"] = last["media_id"]
        q["schedule"] = "slots4"
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

    Owner decisions 2026-10-28: no Reel goes out until the owner has approved it; up to REELS_PER_DAY Reels a day,
    never two Reels in a row; carousels unlimited on catch-up days, otherwise CAROUSELS_PER_DAY. When a Reel may go
    it goes first, otherwise the first eligible carousel goes.
    """
    approved = set(load_queue().get("approved_reels", []))
    last = max(posts, key=lambda p: p["published_at"]) if posts else None
    day_ago = now - timedelta(hours=24)
    recent = [p for p in posts if datetime.fromisoformat(p["published_at"]) > day_ago]
    reel_ok = (reels_allowed_per_week(now) - reels_last_7d(posts, now) > 0
               and sum(p.get("kind") == "reel" for p in recent) < REELS_PER_DAY
               and not (last and last.get("kind") == "reel"))
    carousel_ok = (now.astimezone(IST).date() in CATCHUP_DAYS
                   or sum(p.get("kind") == "carousel" for p in recent) < CAROUSELS_PER_DAY)
    prev_tags = {h.lower() for h in (last or {}).get("hashtags", [])}

    def rotates(s):   # publish.py refuses > 2 hashtags shared with the previous post, or the same set
        cur = {h.lower() for h in meta_for(s)["hashtags"]}
        return cur != prev_tags and len(cur & prev_tags) <= 2

    # A Reel variant ("variant_of" in its meta) and its original are the same footage: posting both is near-duplicate
    # content, so once either one is published the other never goes.
    posted = {p["slug"] for p in posts}

    def family(s):
        base = meta_for(s).get("variant_of") or s
        return {base} | {r for r in approved if kind_of(r) == "reel" and (meta_for(r).get("variant_of") or r) == base}

    eligible = [s for s in rest
                if ((kind_of(s) == "carousel" and carousel_ok)
                    or (kind_of(s) == "reel" and reel_ok and s in approved and not (family(s) & posted)))
                and rotates(s)]
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
    print("slots: " + ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in slots_for(now.astimezone(IST).date()))
          + f" IST today, >= {gap_for(now)} h apart; "
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
