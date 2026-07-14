"""Materialize view 4: network connections as edges.

Derives HOST nodes and directional CONNECTED_TO edges from the source_ip /
dest_ip / dest_port fields already stored on the view-2 ALERT nodes, and
attaches known entities to the HOST matching their host_ip via :AT edges.
External IPs are simply HOST nodes with no :AT edge.

Alerts that carry only a source_ip (the cloud-alert shape: cloudtrail rows
have no dest_ip and no host_ip) contribute :SEEN_FROM edges instead: the
alerting entity is linked to the HOST for the source_ip it was observed
operating from. Because HOSTs merge on ip, a cloud user seen from an IP that
is also some endpoint entity's host_ip lands on the same HOST node, making
endpoint <-> cloud-user relationships traversable:

    (endpoint)-[:AT]->(HOST)<-[:SEEN_FROM]-(cloud user)

Safe to re-run at any time: edge counts are recomputed from the alerts
(SET, not incremented), so the result always converges to the truth - this
view does not suffer the count-inflation-on-reimport behavior of views 1
and 2. Run it after every import to keep the counts current.

Usage:
    python build_view4.py             build or refresh the view
    python build_view4.py --teardown  delete the view entirely

See docs/FUTURE_WORK.md for the design discussion.
"""

import argparse

from common import get_driver, run

BUILD_CONNECTIONS = """
MATCH (a:ALERT {view: 2})
WHERE a.source_ip <> '' AND a.dest_ip <> ''
WITH a.source_ip AS src_ip, a.dest_ip AS dst_ip, a.dest_port AS port,
     count(*) AS events, collect(DISTINCT a.dst_geo)[0] AS geo
MERGE (src:HOST {ip: src_ip, view: 4})
MERGE (dst:HOST {ip: dst_ip, view: 4})
MERGE (src)-[c:CONNECTED_TO {dest_port: port, view: 4}]->(dst)
SET c.count = events, c.dst_geo = geo
"""

BUILD_AT = """
MATCH (a:ALERT {view: 2})
WHERE a.host_ip <> '' AND a.entity <> ''
WITH DISTINCT a.host_ip AS hip, a.entity AS entity, a.entity_type AS etype
MERGE (h:HOST {ip: hip, view: 4})
WITH h, hip, entity, etype
MATCH (e:ENTITY {ip: hip, entity: entity, entity_type: etype, view: 2})
MERGE (e)-[:AT]->(h)
"""

# Source-only alerts (no dest_ip) cannot form a CONNECTED_TO edge; instead
# link the alerting entity to the source_ip HOST it was seen from. Skipped
# when source_ip = host_ip - :AT already expresses presence at the own host.
BUILD_SEEN_FROM = """
MATCH (a:ALERT {view: 2})
WHERE a.source_ip <> '' AND a.dest_ip = '' AND a.entity <> ''
      AND a.source_ip <> a.host_ip
WITH a.source_ip AS sip, a.host_ip AS hip, a.entity AS entity,
     a.entity_type AS etype, count(*) AS events
MERGE (h:HOST {ip: sip, view: 4})
WITH h, hip, entity, etype, events
MATCH (e:ENTITY {ip: hip, entity: entity, entity_type: etype, view: 2})
MERGE (e)-[s:SEEN_FROM]->(h)
SET s.count = events
"""

TEARDOWN = "MATCH (n:HOST {view: 4}) DETACH DELETE n"

SUMMARY = """
MATCH (h:HOST {view: 4})
OPTIONAL MATCH (h)<-[:AT]-(e:ENTITY)
OPTIONAL MATCH (h)<-[:SEEN_FROM]-(se:ENTITY)
WITH count(DISTINCT h) AS hosts, count(DISTINCT e) AS entities,
     count(DISTINCT se) AS seen_entities,
     count(DISTINCT CASE WHEN e IS NULL AND se IS NULL THEN h END) AS unknown_hosts
OPTIONAL MATCH ()-[c:CONNECTED_TO {view: 4}]->()
WITH hosts, entities, seen_entities, unknown_hosts,
     count(c) AS edges, sum(c.count) AS events
OPTIONAL MATCH ()-[s:SEEN_FROM]->(:HOST {view: 4})
RETURN hosts, entities, seen_entities, unknown_hosts, edges, events,
       count(s) AS seen_edges
"""


def main():
    parser = argparse.ArgumentParser(description="Build or tear down view 4 (network connections)")
    parser.add_argument("--teardown", action="store_true", help="delete the view instead of building it")
    args = parser.parse_args()

    with get_driver() as driver:
        if args.teardown:
            _, counters = run(driver, TEARDOWN)
            print(f"View 4 removed: {counters.nodes_deleted} hosts, "
                  f"{counters.relationships_deleted} relationships deleted.")
            return

        _, c1 = run(driver, BUILD_CONNECTIONS)
        _, c2 = run(driver, BUILD_AT)
        _, c3 = run(driver, BUILD_SEEN_FROM)
        print(f"Created {c1.nodes_created + c2.nodes_created + c3.nodes_created} hosts, "
              f"{c1.relationships_created} connection edges, "
              f"{c2.relationships_created} entity links, "
              f"{c3.relationships_created} seen-from links "
              f"(0s everywhere just means the view was already current).")

        records, _ = run(driver, SUMMARY)
        s = records[0]
        print(f"View 4 now: {s['hosts']} hosts ({s['unknown_hosts']} unknown/external), "
              f"{s['entities']} entities at hosts, "
              f"{s['seen_entities']} entities seen from hosts, "
              f"{s['edges']} directed connection edges covering {s['events']} alert events, "
              f"{s['seen_edges']} seen-from edges.")


if __name__ == "__main__":
    main()
