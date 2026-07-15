"""Materialize view 6: network connections as edges.

Derives HOST nodes and directional CONNECTED_TO edges from the source_ip /
dest_ip fields stored on the view-2 ALERT nodes, and attaches known entities to
the HOST matching their host_ip via :AT edges. External IPs are simply HOST
nodes with no :AT edge.

A CONNECTED_TO edge is one per unique (source, dest) host pair - dest_port is
deliberately NOT in the key, so we do not graph per-port fan-out (a port scan
collapses to a single edge). port_count keeps a scalar breadcrumb of how many
distinct ports the pair covered; count is the total alert events.

Alerts that carry only a source_ip (the cloud-alert shape: cloudtrail rows
have no dest_ip and no host_ip) contribute :SEEN_FROM edges instead: the
alerting entity is linked to the HOST for the source_ip it was observed
operating from. Because HOSTs merge on ip, a cloud user seen from an IP that
is also some endpoint entity's host_ip lands on the same HOST node, making
endpoint <-> cloud-user relationships traversable:

    (endpoint)-[:AT]->(HOST)<-[:SEEN_FROM]-(cloud user)

On top of the host mesh we express connectivity at the entity level:
  - connection_count: set on each ENTITY, the number of distinct PEER HOSTS it
    connects to - CONNECTED_TO peers for endpoints, or SEEN_FROM source IPs for
    cloud users (whose source-only alerts form no CONNECTED_TO edge). The
    headline view-6 metric: a count of connections per entity, where a
    connection is a distinct peer/source IP, not a port.
  - CONNECTS_TO: (e1)-[:CONNECTS_TO {count}]->(e2) for connections BETWEEN two
    known entities. In the current data all alerted traffic is entity <-> the
    internet, so this is usually empty; it is kept for when entity-to-entity
    traffic appears.

Safe to re-run at any time: counts are recomputed from the alerts (SET, not
incremented), so the result always converges to the truth - this view does not
suffer the count-inflation-on-reimport behavior of views 1 and 2. Run it after
every import to keep the counts current.

NOTE: this overlay was formerly built as view 4; it moved to its own view 6 to
de-conflict with unrelated view-4 nodes. view 6 is a fresh namespace, so a plain
build is clean - no teardown needed unless you are clearing a prior view-6 build.

Usage:
    python build_view6.py             build or refresh the view
    python build_view6.py --teardown  delete the view entirely

See docs/FUTURE_WORK.md for the design discussion.
"""

import argparse

from common import get_driver, run

# One edge per unique (source, dest) host pair; ports collapsed (see module doc).
BUILD_CONNECTIONS = """
MATCH (a:ALERT {view: 2})
WHERE a.source_ip <> '' AND a.dest_ip <> ''
WITH a.source_ip AS src_ip, a.dest_ip AS dst_ip,
     count(*) AS events, count(DISTINCT a.dest_port) AS ports,
     collect(DISTINCT a.dst_geo)[0] AS geo
MERGE (src:HOST {ip: src_ip, view: 6})
MERGE (dst:HOST {ip: dst_ip, view: 6})
MERGE (src)-[c:CONNECTED_TO {view: 6}]->(dst)
SET c.count = events, c.port_count = ports, c.dst_geo = geo
"""

BUILD_AT = """
MATCH (a:ALERT {view: 2})
WHERE a.host_ip <> '' AND a.entity <> ''
WITH DISTINCT a.host_ip AS hip, a.entity AS entity, a.entity_type AS etype
MERGE (h:HOST {ip: hip, view: 6})
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
MERGE (h:HOST {ip: sip, view: 6})
WITH h, hip, entity, etype, events
MATCH (e:ENTITY {ip: hip, entity: entity, entity_type: etype, view: 2})
MERGE (e)-[s:SEEN_FROM]->(h)
SET s.count = events
"""

# Headline metric: distinct peer hosts each entity connects to. For endpoints
# that is CONNECTED_TO peers (in + out) reached via their :AT host; for cloud
# users (source-only alerts, no dest_ip, so no CONNECTED_TO) it is the distinct
# source IPs they were SEEN_FROM. count(DISTINCT ...) so a port scan (one peer)
# counts once and the two OPTIONAL MATCHes' cross product does not inflate.
# OPTIONAL so entities with no connectivity get 0 rather than being skipped.
SET_ENTITY_CONNECTION_COUNT = """
MATCH (e:ENTITY {view: 2})
OPTIONAL MATCH (e)-[:AT]->(:HOST)-[:CONNECTED_TO {view: 6}]-(peer:HOST)
OPTIONAL MATCH (e)-[:SEEN_FROM]->(src:HOST)
WITH e, count(DISTINCT peer) + count(DISTINCT src) AS conns
SET e.connection_count = conns
"""

# Connections BETWEEN two known entities. Two ways entities connect:
#  (1) network - their :AT hosts talk to each other via CONNECTED_TO (usually
#      empty in the current data, where traffic is entity <-> internet); and
#  (2) shared host - a cloud user's source_ip equals an endpoint's host_ip, so
#      both land on the same HOST: (endpoint)-[:AT]->(HOST)<-[:SEEN_FROM]-(user).
# count = number of such connection instances between the pair. Directional a->b
# (network: source->dest; shared host: endpoint->cloud user).
BUILD_ENTITY_CONNECTIONS = """
CALL {
  MATCH (a:ENTITY {view: 2})-[:AT]->(:HOST {view: 6})-[:CONNECTED_TO {view: 6}]->(:HOST {view: 6})<-[:AT]-(b:ENTITY {view: 2})
  WHERE a <> b
  RETURN a, b
  UNION
  MATCH (a:ENTITY {view: 2})-[:AT]->(:HOST {view: 6})<-[:SEEN_FROM]-(b:ENTITY {view: 2})
  WHERE a <> b
  RETURN a, b
}
WITH a, b, count(*) AS conns
MERGE (a)-[r:CONNECTS_TO {view: 6}]->(b)
SET r.count = conns
"""

# Flag entities that connect to ANOTHER entity (a CONNECTS_TO edge, in or out) so
# the graph can highlight them. entity_links = 0 for entities that only talk to
# hosts/the internet; > 0 for entity-to-entity links like LP-42 <-> lp-sre-42.
SET_ENTITY_LINK_COUNT = """
MATCH (e:ENTITY {view: 2})
OPTIONAL MATCH (e)-[r:CONNECTS_TO {view: 6}]-(:ENTITY {view: 2})
WITH e, count(r) AS links
SET e.entity_links = links
"""

# Directed entity <-> peer edges for the graph view: collapse the entity's own
# host so the ENTITY is the node, and orient the arrow along the real connection
# direction (source -> dest).
#  - endpoint OUTBOUND: their :AT host is the CONNECTED_TO source  => entity -> peer
#  - endpoint INBOUND:  their :AT host is the CONNECTED_TO dest    => peer -> entity
#  - cloud user: has only a source_ip and never a dest_ip, so it is NEVER a
#    connection source; the source-IP host it was SEEN_FROM points TO it
#    => source_ip host -> cloud user.
BUILD_ENTITY_PEER_OUT = """
MATCH (e:ENTITY {view: 2})-[:AT]->(:HOST {view: 6})-[:CONNECTED_TO {view: 6}]->(peer:HOST {view: 6})
MERGE (e)-[:CONNECTS_HOST {view: 6}]->(peer)
"""

BUILD_ENTITY_PEER_IN = """
MATCH (e:ENTITY {view: 2})-[:AT]->(:HOST {view: 6})<-[:CONNECTED_TO {view: 6}]-(peer:HOST {view: 6})
MERGE (peer)-[:CONNECTS_HOST {view: 6}]->(e)
"""

BUILD_ENTITY_PEER_SEEN = """
MATCH (e:ENTITY {view: 2})-[:SEEN_FROM]->(src:HOST {view: 6})
MERGE (src)-[:CONNECTS_HOST {view: 6}]->(e)
"""

# CONNECTS_TO joins ENTITY nodes and connection_count lives on ENTITY nodes, so
# the HOST teardown below would leave both behind - clear them explicitly.
TEARDOWN_ENTITY_CONNECTIONS = "MATCH (:ENTITY)-[r:CONNECTS_TO {view: 6}]->(:ENTITY) DELETE r"
TEARDOWN_ENTITY_PROPS = "MATCH (e:ENTITY {view: 2}) REMOVE e.connection_count, e.entity_links"

TEARDOWN = "MATCH (n:HOST {view: 6}) DETACH DELETE n"

SUMMARY = """
MATCH (h:HOST {view: 6})
OPTIONAL MATCH (h)<-[:AT]-(e:ENTITY)
OPTIONAL MATCH (h)<-[:SEEN_FROM]-(se:ENTITY)
WITH count(DISTINCT h) AS hosts, count(DISTINCT e) AS entities,
     count(DISTINCT se) AS seen_entities,
     count(DISTINCT CASE WHEN e IS NULL AND se IS NULL THEN h END) AS unknown_hosts
OPTIONAL MATCH ()-[c:CONNECTED_TO {view: 6}]->()
WITH hosts, entities, seen_entities, unknown_hosts,
     count(c) AS edges, sum(c.count) AS events
OPTIONAL MATCH ()-[s:SEEN_FROM]->(:HOST {view: 6})
WITH hosts, entities, seen_entities, unknown_hosts, edges, events,
     count(s) AS seen_edges
OPTIONAL MATCH (:ENTITY)-[ec:CONNECTS_TO {view: 6}]->(:ENTITY)
WITH hosts, entities, seen_entities, unknown_hosts, edges, events, seen_edges,
     count(ec) AS entity_edges
OPTIONAL MATCH (ce:ENTITY {view: 2}) WHERE coalesce(ce.connection_count, 0) > 0
RETURN hosts, entities, seen_entities, unknown_hosts, edges, events, seen_edges,
       entity_edges, count(ce) AS connected_entities,
       max(ce.connection_count) AS max_connections
"""


def main():
    parser = argparse.ArgumentParser(description="Build or tear down view 6 (network connections)")
    parser.add_argument("--teardown", action="store_true", help="delete the view instead of building it")
    args = parser.parse_args()

    with get_driver() as driver:
        if args.teardown:
            _, ce = run(driver, TEARDOWN_ENTITY_CONNECTIONS)
            run(driver, TEARDOWN_ENTITY_PROPS)
            _, counters = run(driver, TEARDOWN)
            print(f"View 6 removed: {counters.nodes_deleted} hosts, "
                  f"{counters.relationships_deleted + ce.relationships_deleted} relationships deleted.")
            return

        _, c1 = run(driver, BUILD_CONNECTIONS)
        _, c2 = run(driver, BUILD_AT)
        _, c3 = run(driver, BUILD_SEEN_FROM)
        run(driver, SET_ENTITY_CONNECTION_COUNT)
        _, c5 = run(driver, BUILD_ENTITY_CONNECTIONS)
        run(driver, SET_ENTITY_LINK_COUNT)
        _, c6 = run(driver, BUILD_ENTITY_PEER_OUT)
        _, c6b = run(driver, BUILD_ENTITY_PEER_IN)
        _, c7 = run(driver, BUILD_ENTITY_PEER_SEEN)
        print(f"Created {c1.nodes_created + c2.nodes_created + c3.nodes_created} hosts, "
              f"{c1.relationships_created} connection edges, "
              f"{c2.relationships_created} entity links, "
              f"{c3.relationships_created} seen-from links, "
              f"{c5.relationships_created} entity-to-entity connections, "
              f"{c6.relationships_created + c6b.relationships_created + c7.relationships_created} entity-peer edges "
              f"(0s everywhere just means the view was already current).")

        records, _ = run(driver, SUMMARY)
        s = records[0]
        print(f"View 6 now: {s['hosts']} hosts ({s['unknown_hosts']} unknown/external), "
              f"{s['entities']} entities at hosts, "
              f"{s['seen_entities']} entities seen from hosts, "
              f"{s['edges']} directed connection edges covering {s['events']} alert events, "
              f"{s['seen_edges']} seen-from edges. "
              f"{s['connected_entities']} entities have connections "
              f"(max {s['max_connections']} distinct peers), "
              f"{s['entity_edges']} entity-to-entity edges.")


if __name__ == "__main__":
    main()