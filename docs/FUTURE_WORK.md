# Future Work: Data-Model Gaps and Candidate Views

[GRAPH_MODEL.md](GRAPH_MODEL.md) documents the schema as it exists; this file collects what it *doesn't* do yet. These are findings from surveying the sample data (July 2026), with recommendations for the planned Python port. None block a port, but they shape what the ported importer should fix versus preserve.

## Timestamps are unsortable free text

`ALERT.timestamp` stores the source's raw string, and the sample data alone contains three formats: zero-padded `2016-06-26 21:03:44`, unpadded-hour `2022-04-27 7:45:03`, and Kibana-style `Nov 14, 2024 @ 12:57:50.349`. Roughly 1,240 of ~1,290 events are not in the lexicographically sortable form, so `ORDER BY a.timestamp` (or any time-range filter or per-entity timeline) is quietly wrong on real data.

**Implemented:** [`scripts/normalize_timestamps.py`](../scripts/normalize_timestamps.py) parses the three known formats (plus a `dateutil` fallback for new ones) and adds `ts_iso` (sortable ISO 8601 string) and `ts_epoch` (integer millis, interpreted as UTC) to every view-2 `ALERT`, leaving the raw `timestamp` untouched. Run it after every import; unparseable values are reported, never guessed. The eventual Python port should fold this into the importer itself. For the graph-native timeline built on top of these properties, see view 12 below.

## No process identity, sparse process data

Alerts carry `process`, `executable`, and `proctitle` names, but no `pid`/`ppid` exists anywhere in the pipeline — the recognizer's output schema doesn't include one. Correlation by process *name* per entity is already queryable:

```cypher
MATCH (a:ALERT {entity: $entity, view: 2})
WHERE a.process <> ''
RETURN a.process, count(*) AS alerts, collect(DISTINCT a.name) AS detections
```

but process-instance tracking and parent/child lineage are impossible until the upstream schema adds pid/ppid. Coverage is also thin: only 22 of ~1,290 sample events have a `process` field at all (7 of those empty).

**Recommendation:** get pid/ppid and better process coverage into the recognizer's output schema first; a full process view is trivial to add afterward and pointless before.

In the meantime, process-name hubs can be materialized on demand with the same derived-data pattern as view 4 (safe to re-run; teardown with `MATCH (p:PROCESS {view: 11}) DETACH DELETE p`):

```cypher
MATCH (a:ALERT {view: 2})
WHERE a.process <> ''          // load-bearing: without it, all process-less alerts pile onto PROCESS {name: ""}
MERGE (p:PROCESS {name: a.process, view: 11})
MERGE (a)-[:RAN]->(p)
```

`MATCH (p:PROCESS {view: 11})<-[r:RAN]-(a:ALERT) RETURN p, r, a` then plots each process name as a hub with its alerts around it; hubs are global (keyed on name, not entity), so the same process on two hosts converges on one node. On the sample data expect three small stars: `rundll32.exe` (8), `spppsvc.exe` (5), `curl` (2).

## Candidate view 4: network connections as edges

`source_ip`, `dest_ip`, `dest_port`, and `dst_geo` live as strings on `ALERT` nodes, so "what did this host talk to" is not traversable today — a connection exists only as columns inside one node.

The data supports an edge-based view well: **1,235 of 1,290 sample events (96%) carry both a source and destination IP** (44 source-only, 11 neither). Resolution against known entities is clean — each of the 8 entity `host_ip`s maps to exactly one entity — but note that **no sample connection runs entity-to-entity**: every one has exactly one known end (1,136 external→entity, 99 entity→external, dominated by external `198.18.10.251` → the entity at `172.16.4.4`). So the useful shape is entity-to-external-IP, with entity-to-entity paths emerging automatically wherever both ends happen to be entity hosts.

### No importer change needed: build it in Cypher

Unlike views 1 and 2 (which must be built during import — nothing else stores the events), view 4 is *derived* from data already on the view-2 `ALERT` nodes. It can be materialized, and re-materialized at any time, with two idempotent statements run after import — automated by [`scripts/build_view4.py`](../scripts/build_view4.py) (`--teardown` to remove):

```cypher
// 1. Connection edges, aggregated per (source, dest, port).
//    SET (not ON CREATE/ON MATCH) recomputes counts from the alerts,
//    so re-running always converges to the truth — no count inflation.
MATCH (a:ALERT {view: 2})
WHERE a.source_ip <> '' AND a.dest_ip <> ''
WITH a.source_ip AS src_ip, a.dest_ip AS dst_ip, a.dest_port AS port,
     count(*) AS events, collect(DISTINCT a.dst_geo)[0] AS geo
MERGE (src:HOST {ip: src_ip, view: 4})
MERGE (dst:HOST {ip: dst_ip, view: 4})
MERGE (src)-[c:CONNECTED_TO {dest_port: port, view: 4}]->(dst)
SET c.count = events, c.dst_geo = geo
```

```cypher
// 2. Attach known entities to the HOST matching their host_ip.
//    External IPs are simply HOST nodes with no :AT edge.
MATCH (a:ALERT {view: 2})
WHERE a.host_ip <> '' AND a.entity <> ''
WITH DISTINCT a.host_ip AS hip, a.entity AS entity, a.entity_type AS etype
MERGE (h:HOST {ip: hip, view: 4})
WITH h, hip, entity, etype
MATCH (e:ENTITY {ip: hip, entity: entity, entity_type: etype, view: 2})
MERGE (e)-[:AT]->(h)
```

Once built, entity-to-entity traffic is:

```cypher
MATCH (e1:ENTITY)-[:AT]->(h1:HOST)-[c:CONNECTED_TO]->(h2:HOST)<-[:AT]-(e2:ENTITY)
RETURN e1.entity, h1.ip, c.dest_port, h2.ip, e2.entity
```

(zero rows on the sample data — see above). Entity-to-external traffic, the shape the sample data actually has:

```cypher
MATCH (e:ENTITY)-[:AT]->(h:HOST)-[c:CONNECTED_TO]-(x:HOST)
WHERE NOT (x)<-[:AT]-()
RETURN e, h, c, x
```

and "unknown talkers" alone is `MATCH (h:HOST {view: 4}) WHERE NOT (h)<-[:AT]-() RETURN h`. Teardown/rebuild is `MATCH (n:HOST {view: 4}) DETACH DELETE n` followed by the two build statements.

**Direction** is preserved throughout: every edge points `source_ip` → `dest_ip`, and opposite flows are separate edges (the dominant sample pair is two arrows: external → entity with count 1,130, and entity → external with count 87 — the beacon-shaped half). The undirected `-[c:CONNECTED_TO]-` in the query above only widens the *match* to both directions; Browser still draws the stored arrows. For tabular directional analysis, split it:

```cypher
MATCH (e:ENTITY)-[:AT]->(h:HOST)-[c:CONNECTED_TO]->(x:HOST)
WHERE NOT (x)<-[:AT]-()
RETURN e.entity, 'outbound' AS direction, h.ip AS src, x.ip AS dst, c.dest_port AS port, c.count AS events
UNION
MATCH (e:ENTITY)-[:AT]->(h:HOST)<-[c:CONNECTED_TO]-(x:HOST)
WHERE NOT (x)<-[:AT]-()
RETURN e.entity, 'inbound' AS direction, x.ip AS src, h.ip AS dst, c.dest_port AS port, c.count AS events
```

### Design notes

- Because counts are recomputed (`SET c.count = events`), this view avoids the count-inflation-on-reimport problem the other views have — rebuild after any import and the numbers are exact.
- The `:AT` edge deliberately links a view-2 `ENTITY` to a view-4 `HOST`, bending the views-are-disjoint convention at one explicit, documented point. The alternative — duplicating entity nodes into view 4 — keeps the convention pure at the cost of another parallel entity set.
- `dest_port` in the edge merge key gives one edge per host-pair *per port* (suits beacon-hunting; the dominant sample traffic is beacon-like). Dropping it gives one edge per pair with ports as a collected property.
- The result maps *alerted-on* traffic only, not netflow.
- Data-quality note: two sample entities have names like `" atomic weight: 4 - 172.16.4.4"` (leading space, IP embedded in the name) — worth cleaning upstream before this view makes them prominent.
- At production scale, add an index first: `CREATE INDEX host_ip IF NOT EXISTS FOR (h:HOST) ON (h.ip, h.view)`.
- A pure query-time alternative (no materialization at all) also works for tabular analysis — `MATCH (a:ALERT {view:2}) WHERE ... RETURN a.source_ip, a.dest_ip, count(*)` — but Neo4j Browser can only *visualize* graph elements that exist, so an on-screen connection graph needs either materialized edges (above) or APOC virtual relationships.

## View 12: per-entity alert timeline

Implemented by [`scripts/build_view12.py`](../scripts/build_view12.py) (requires `normalize_timestamps.py` first; `--teardown` to remove). For each entity it builds a time-ordered chain *beside* the existing graph:

```
(TIMELINE {entity, view: 12})-[:STARTS]->(TICK {seq: 0})-[:NEXT]->(TICK {seq: 1})-[:NEXT]->...
```

with each `TICK` pointing at its real alert via `-[:OF]->(ALERT)` and carrying `ts_epoch`/`ts_iso`, `name`, `severity`, and `guid` so a timeline can render without touching the alerts. Plot one in the Browser with:

```cypher
MATCH p = (t:TIMELINE {view: 12, entity: "COBALT"})-[:STARTS|NEXT*]->(:TICK)
RETURN p
```

**Why mirror TICK nodes instead of chaining the ALERTs directly:** the web front end runs *unbounded* `(entity)-[*]->(:ALERT)` traversals over view 2 (View1, View6, View7 pages). `NEXT` edges between real alerts would extend those traversals through the chain, where every hop is another valid `ALERT` endpoint — for the entity with ~1,130 alerts that is hundreds of thousands of extra paths, some over a thousand hops long, enough to hang the dashboard. Nothing in view 1 or 2 links *into* the view-12 subgraph, and `:OF` points into `ALERT` (which has no outgoing edges), so existing queries cannot reach it and their results are byte-identical. The ~1,300 small mirror nodes are the price of that isolation.

The view is dropped and rebuilt on every run (self-heals after imports); ties on `ts_epoch` break deterministically by `(guid, name)`.

## Running the scripts

```
cd scripts
pip install -r requirements.txt
python normalize_timestamps.py   # after every import
python build_view4.py            # network connections
python build_view12.py           # per-entity timelines (needs normalize first)
```

Connection settings come from the same `.env` / environment variables as the Go importer. All three scripts are idempotent; the importer's `-reset` wipes views 4 and 12 along with everything else, so rebuild after any reset.
