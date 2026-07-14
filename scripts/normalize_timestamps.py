"""Normalize ALERT timestamps into sortable properties.

The importer stores each alert's timestamp as the raw string from the source,
and the sources disagree on format (the sample data alone has three: zero-padded
"2016-06-26 21:03:44", unpadded-hour "2022-04-27 7:45:03", and Kibana-style
"Nov 14, 2024 @ 12:57:50.349"). Raw strings do not sort chronologically, so
this script parses each view-2 ALERT's timestamp and adds two properties:

    ts_iso    ISO 8601 string, e.g. "2016-06-26T21:03:44" (sortable)
    ts_epoch  integer milliseconds since the Unix epoch (what view 12 sorts on)

Source timestamps carry no timezone; they are interpreted as UTC. The raw
timestamp property is left untouched. Alerts already normalized are skipped
unless --force is given; unparseable timestamps are reported and skipped, never
guessed. Safe to re-run after every import.

Usage:
    python normalize_timestamps.py             normalize alerts missing ts_epoch
    python normalize_timestamps.py --force     re-normalize every alert
    python normalize_timestamps.py --dry-run   parse and report, write nothing
"""

import argparse
from datetime import datetime, timezone

from dateutil import parser as dateparser

from common import get_driver, run

# Explicit formats seen in the data so far; dateutil is the fallback for
# anything new. strptime accepts unpadded day/hour digits, so the unpadded
# variants need no extra entries.
KNOWN_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%b %d, %Y @ %H:%M:%S.%f",
]

FETCH = """
MATCH (a:ALERT {view: 2})
WHERE $force OR a.ts_epoch IS NULL
RETURN a.guid AS guid, a.name AS name, a.timestamp AS timestamp
"""

# Alerts are matched on their documented merge key (guid, name, view).
UPDATE = """
UNWIND $rows AS row
MATCH (a:ALERT {guid: row.guid, name: row.name, view: 2})
SET a.ts_iso = row.iso, a.ts_epoch = row.epoch
"""

BATCH_SIZE = 500


def parse_timestamp(raw):
    """Parse one raw timestamp string; returns a naive datetime or None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in KNOWN_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        dt = dateparser.parse(raw)
    except (ValueError, OverflowError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def to_row(record):
    dt = parse_timestamp(record["timestamp"])
    if dt is None:
        return None
    return {
        "guid": record["guid"],
        "name": record["name"],
        "iso": dt.isoformat(),
        "epoch": int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000),
    }


def main():
    parser = argparse.ArgumentParser(description="Add sortable ts_iso/ts_epoch properties to ALERT nodes")
    parser.add_argument("--force", action="store_true", help="re-normalize alerts that already have ts_epoch")
    parser.add_argument("--dry-run", action="store_true", help="parse and report without writing")
    args = parser.parse_args()

    with get_driver() as driver:
        records, _ = run(driver, FETCH, force=args.force)
        if not records:
            print("Nothing to do: every view-2 ALERT already has ts_epoch.")
            return

        rows, failures = [], []
        for record in records:
            row = to_row(record)
            if row is None:
                failures.append(record)
            else:
                rows.append(row)

        print(f"{len(records)} alerts fetched: {len(rows)} parsed, {len(failures)} unparseable.")
        for record in failures:
            print(f"  cannot parse {record['timestamp']!r} (guid {record['guid']}, name {record['name']})")

        if args.dry_run:
            print("Dry run: nothing written.")
            return

        updated = 0
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            _, counters = run(driver, UPDATE, rows=batch)
            updated += counters.properties_set // 2
        print(f"Set ts_iso/ts_epoch on {updated} alerts.")


if __name__ == "__main__":
    main()
