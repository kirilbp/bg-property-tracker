"""
Resolves a `git pull --rebase` content conflict on a `data/history*.json`
file by actually merging both sides instead of blindly discarding one -
see docs/decisions.md's 2026-09-22 entry ("alo.bg grid crawl was never
actually dead") for the full investigation this came out of.

The bug this replaces: every scrape/backfill workflow's git-commit step
falls back to

    git diff --name-only --diff-filter=U | xargs -r git checkout --ours --

on a rebase conflict, with a comment claiming this "keeps main's version
of the conflicted files". During an active `git rebase` (which is what
`git pull --rebase` runs), git's own meaning of "ours"/"theirs" is
swapped from a normal merge: "ours" (stage 2) is the commit being rebased
ONTO - i.e. upstream/origin/main - and "theirs" (stage 3) is the commit
being replayed - i.e. THIS run's own freshly-scraped data. So
`checkout --ours` does exactly what its comment says (keeps main's
version) - but for a workflow whose only job is to land freshly-scraped
data, "keep main's version and discard what this run just produced" is
backwards the moment main's version is the STALE one, which is exactly
what happens whenever this workflow's run genuinely has newer data than
whatever an interleaved concurrent workflow (an hourly backfill sharing
the same data/ files) most recently pushed.

Live-confirmed as the actual root cause of alo.bg's grid crawl "silently
dying" (docs/backlog.md item 3): scraper_alo.py's fetch_listings() found
77,625-89,324 real listings on every single run from 2026-09-16 through
at least 2026-09-19 (confirmed from GitHub Actions job logs - the crawl
was never broken), but data/history_alo.json hit a real content conflict
against backfill-detail-alo.yml's concurrent hourly commits on every one
of those runs, and `checkout --ours` discarded the freshly-merged file
every time - freezing the committed data/history_alo.json at whatever
backfill-detail-alo.yml had last pushed, which is why every listing's
last real snapshot capped at 2026-09-16T07:57:07Z regardless of how many
subsequent runs "succeeded".

data/history*.json's shape (see scraper_alo.py's update_history()/
save_history(), and the equivalent in every other scraper - same schema
everywhere) is a dict keyed by listing id:
    {"<id>": {"first_seen": "<iso>", "snapshots": [{"seen_at": "<iso>",
     "price_eur": <int>, ...}, ...], "latest": {<scraped fields>}}, ...}
That shape is safe to merge without guessing: each listing's id is an
independent record, so the merge is a per-id union, not a line-based text
merge. For an id present on both sides: "first_seen" takes the earlier of
the two (whichever side saw it first is correct regardless of which
commit happened to survive), "snapshots" takes the union of both sides'
entries (deduped on exact (seen_at, price_eur) - see below), and "latest"
is a shallow dict merge preferring whichever side's own snapshot history
is more recent (the side that actually re-scraped this listing most
recently) but keeping any keys unique to the OTHER side (this is a
deliberate, minimal mitigation for a separate, already-flagged issue -
scraper_alo.py's update_history() replaces "latest" wholesale each run
rather than merging into it, so a plain grid-crawl commit's "latest" has
none of backfill_detail_alo.py's enrichment fields like site_updated_at/
lat/lng/description/photos/_detail_fetched - see docs/decisions.md for
why that's being flagged as a separate follow-up rather than fixed here).

Not applied to data/leads*.json (the OTHER conflicted files in every run
that hit this) - deliberately left on the existing checkout --ours
fallback (now made loud, not silent - see the workflow files). leads*.json
is a fully-derived array that every scraper's own compute_leads()
recomputes from scratch off history*.json on its very next run, so as
long as history*.json - the actual source of truth - stops losing data,
leads*.json self-heals within one cycle with no separate merge logic
needed; writing a safe generic merger for an array keyed by nothing would
be real, unnecessary extra risk for zero lasting benefit.

Usage (from the workflow's conflict-fallback step, after `git pull
--rebase origin main` reports a conflict):
    python merge_history_conflict.py $(git diff --name-only --diff-filter=U)
Exits 0 and `git add`s each file it actually resolved. Any conflicted
path that doesn't match data/history*.json is left untouched (still
conflicted) for the caller's own existing fallback to handle - this
script only ever touches the specific files it knows how to merge safely.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HISTORY_NAME_RE = None  # set below, avoids importing re at module import time for a one-liner


def is_history_file(path):
    name = Path(path).name
    return name == "history.json" or (name.startswith("history_") and name.endswith(".json"))


def git_show(rev, path):
    """Returns the conflicted file's content at the given git stage
    ('main' -> :2:, 'local' -> :3:), or None if that stage doesn't exist
    (e.g. the file was added fresh on only one side)."""
    stage = {"main": ":2:", "local": ":3:"}[rev]
    result = subprocess.run(
        ["git", "show", f"{stage}{path}"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout


def snapshot_key(s):
    # Two snapshots are "the same real observation" if they share a
    # timestamp and price - anything else (a genuinely different scrape
    # at a different moment, or the same moment with a different price,
    # which shouldn't happen but isn't this script's job to police) is
    # kept as a separate entry.
    return (s.get("seen_at"), s.get("price_eur"))


def freshest_seen_at(rec):
    snaps = rec.get("snapshots") or []
    if not snaps:
        return None
    return snaps[-1].get("seen_at")


def merge_record(main_rec, local_rec):
    if main_rec is None:
        return local_rec
    if local_rec is None:
        return main_rec

    first_seen = main_rec.get("first_seen") or local_rec.get("first_seen")
    if main_rec.get("first_seen") and local_rec.get("first_seen"):
        first_seen = min(main_rec["first_seen"], local_rec["first_seen"])

    seen = set()
    merged_snapshots = []
    for s in (main_rec.get("snapshots") or []) + (local_rec.get("snapshots") or []):
        k = snapshot_key(s)
        if k in seen:
            continue
        seen.add(k)
        merged_snapshots.append(s)
    # seen_at is an ISO timestamp string - safe to sort lexicographically
    # (same format/timezone convention every scraper uses via
    # datetime.now(timezone.utc).isoformat()).
    merged_snapshots.sort(key=lambda s: s.get("seen_at") or "")

    main_fresh = freshest_seen_at(main_rec)
    local_fresh = freshest_seen_at(local_rec)
    if local_fresh and (not main_fresh or local_fresh > main_fresh):
        newer_latest, older_latest = local_rec.get("latest", {}), main_rec.get("latest", {})
    else:
        newer_latest, older_latest = main_rec.get("latest", {}), local_rec.get("latest", {})
    # Shallow union: the newer side's own fields win on overlap, but a
    # field only the older side has (typically backfill-only enrichment
    # fields the newer side's plain grid-crawl "latest" never carried -
    # see module docstring) survives instead of being silently dropped.
    merged_latest = {**older_latest, **newer_latest}

    merged = dict(main_rec if main_fresh and (not local_fresh or main_fresh >= local_fresh) else local_rec)
    merged["first_seen"] = first_seen
    merged["snapshots"] = merged_snapshots
    merged["latest"] = merged_latest
    return merged


def merge_history(main_json, local_json):
    main_data = json.loads(main_json) if main_json is not None else {}
    local_data = json.loads(local_json) if local_json is not None else {}
    merged = {}
    for lid in set(main_data) | set(local_data):
        merged[lid] = merge_record(main_data.get(lid), local_data.get(lid))
    return merged


def resolve(path):
    main_json = git_show("main", path)
    local_json = git_show("local", path)
    if main_json is None and local_json is None:
        print(f"WARNING: merge_history_conflict.py: {path} has neither :2: nor :3: stage - leaving unresolved")
        return False
    try:
        merged = merge_history(main_json, local_json)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"::warning::merge_history_conflict.py: {path} failed to parse for a real merge ({e}) - leaving unresolved for the caller's existing fallback")
        return False
    Path(path).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    n_main = len(json.loads(main_json)) if main_json else 0
    n_local = len(json.loads(local_json)) if local_json else 0
    print(
        f"OK: merge_history_conflict.py: merged {path} - "
        f"main had {n_main} listings, this run had {n_local}, merged has {len(merged)} "
        f"(no listing or snapshot from either side was discarded)"
    )
    subprocess.run(["git", "add", path], check=True)
    return True


def main():
    paths = sys.argv[1:]
    if not paths:
        print("Usage: merge_history_conflict.py <conflicted-path> [<conflicted-path> ...]")
        sys.exit(0)
    unresolved = []
    for path in paths:
        if not is_history_file(path):
            unresolved.append(path)
            continue
        if not resolve(path):
            unresolved.append(path)
    if unresolved:
        # Not an error - the caller (the workflow's own bash fallback)
        # still needs to resolve these itself. Printed so it's visible in
        # the run's log which files got a real merge vs. the old
        # last-resort behavior.
        print("merge_history_conflict.py: left unresolved (caller's fallback applies): " + ", ".join(unresolved))
    # Always exit 0 - this script's job is best-effort resolution, not
    # deciding whether the overall push attempt succeeds.
    sys.exit(0)


if __name__ == "__main__":
    main()
