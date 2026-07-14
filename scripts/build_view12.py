"""Materialize view 12: a time-ordered alert timeline per entity.

For each entity, builds a chain alongside the existing graph:

    (TIMELINE {entity, view: 12})
        -[:STARTS]-> (TICK {seq: 0}) -[:NEXT]-> (TICK {seq: 1}) -[:NEXT]-> ...

with each TICK pointing at its real alert via -[:OF]-> (ALERT). TICKs carry
ts_epoch/ts_iso, name, severity, and guid so a timeline can render without
touching the alerts.

Deliberately does NOT chain the ALERT nodes themselves: the web front end runs
unbounded (entity)-[*]->(:ALERT) traversals over view 2, and NEXT edges between
real alerts would extend those into hundreds of thousands of extra paths
(see docs/FUTURE_WORK.md). Nothing in view 1 or 2 links INTO this subgraph, and
:OF points into ALERT (which has no outgoing edges), so existing queries cannot
reach it and their results are unchanged.

Ordering comes from ts_epoch, so run normalize_timestamps.py first. Alerts
without ts_epoch (unparseable timestamps) are skipped with a warning. The view
is dropped and rebuilt from scratch on every run, so it self-heals after new
imports; ties on ts_epoch are broken by (guid, name) for a deterministic order.

Usage:
    python build_view12.py             rebuild the timelines
    python build_view12.py --teardown  delete the view entirely
"""

import argparse
from collections import defaultdict

from common import get_driver, run

FETCH = """
MATCH (a:ALERT {view: 2})
WHERE a.entity <> '' AND a.ts_epoch IS NOT NULL
RETURN a.entity AS entity, a.guid AS guid, a.name AS name,
       a.severity AS severity, a.ts_epoch AS epoch, a.ts_iso AS iso
"""

COUNT_MISSING = """
MATCH (a:ALERT {view: 2})
WHERE a.entity <> '' AND a.ts_epoch IS NULL
RETURN count(a) AS missing
"""

TEARDOWN = """
MATCH (n {view: 12})
WHERE n:TICK OR n:TIMELINE
DETACH DELETE n
"""

CREATE_TICKS = """
UNWIND $rows AS row
CREATE (k:TICK {view: 12, entity: $entity, seq: row.seq, ts_epoch: row.epoch,
                ts_iso: row.iso, name: row.name, severity: row.severity, guid: row.guid})
WITH k, row
MATCH (a:ALERT {guid: row.guid, name: row.name, view: 2})
CREATE (k)-[:OF]->(a)
"""

CHAIN_TICKS = """
MATCH (k:TICK {view: 12, entity: $entity})
WITH k ORDER BY k.seq
WITH collect(k) AS ticks
UNWIND range(0, size(ticks) - 2) AS i
WITH ticks[i] AS a, ticks[i + 1] AS b
CREATE (a)-[:NEXT {view: 12}]->(b)
"""

CREATE_ANCHOR = """
MATCH (k:TICK {view: 12, entity: $entity, seq: 0})
CREATE (t:TIMELINE {entity: $entity, view: 12, alerts: $alerts})
CREATE (t)-[:STARTS {view: 12}]->(k)
"""


def main():
    parser = argparse.ArgumentParser(description="Build or tear down view 12 (per-entity alert timelines)")
    parser.add_argument("--teardown", action="store_true", help="delete the view instead of building it")
    args = parser.parse_args()

    with get_driver() as driver:
        _, counters = run(driver, TEARDOWN)
        if args.teardown:
            print(f"View 12 removed: {counters.nodes_deleted} nodes, "
                  f"{counters.relationships_deleted} relationships deleted.")
            return

        records, _ = run(driver, COUNT_MISSING)
        missing = records[0]["missing"]
        if missing:
            print(f"Warning: skipping {missing} alerts without ts_epoch - "
                  f"run normalize_timestamps.py to include them.")

        records, _ = run(driver, FETCH)
        if not records:
            print("No normalized alerts found; nothing to build.")
            return

        by_entity = defaultdict(list)
        for r in records:
            by_entity[r["entity"]].append(r)

        for entity, alerts in sorted(by_entity.items()):
            alerts.sort(key=lambda r: (r["epoch"], r["guid"], r["name"]))
            rows = [{"seq": i, "guid": r["guid"], "name": r["name"], "severity": r["severity"],
                     "epoch": r["epoch"], "iso": r["iso"]} for i, r in enumerate(alerts)]
            run(driver, CREATE_TICKS, entity=entity, rows=rows)
            run(driver, CHAIN_TICKS, entity=entity)
            run(driver, CREATE_ANCHOR, entity=entity, alerts=len(rows))
            print(f"  {entity}: {len(rows)} alerts, "
                  f"{alerts[0]['iso']} .. {alerts[-1]['iso']}")

        print(f"View 12 built: {len(by_entity)} timelines over {len(records)} alerts.")
        print('Plot one with: MATCH p=(t:TIMELINE {view: 12, entity: "COBALT"})'
              "-[:STARTS|NEXT*]->(:TICK) RETURN p")


if __name__ == "__main__":
    main()
