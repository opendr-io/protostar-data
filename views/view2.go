package views

import (
	"context"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"

	"github.com/opendr-io/protostar-data/utils"
)

func View2(ctx context.Context, session neo4j.SessionWithContext, params map[string]interface{}) {
	// fmt.Println("Creating unique set of entities 2")
	query := `
	MERGE (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})
	ON CREATE SET e.count = 1
	ON MATCH SET e.count = e.count + 1`
	res, err := session.Run(ctx, query, params)
	utils.HandleResult(res, err)

	query = `
	// Match the ENTITY node with the given parameters
	MATCH (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})

	// Merge the SEVERITY_CLUSTER node and update its count
	MERGE (scs:SEVERITY_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, severity: $severity})
	ON CREATE SET scs.count = 1
	ON MATCH SET scs.count = scs.count + 1

	// Create the relationship between ENTITY and SEVERITY_CLUSTER
	MERGE (e)-[:HAS_SEVERITY]->(scs)

	// Merge the NAME_CLUSTER node and update its count
	MERGE (ncs:NAME_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, severity: $severity, name: $name})
	ON CREATE SET ncs.count = 1
	ON MATCH SET ncs.count = ncs.count + 1

	// Create the relationship between SEVERITY_CLUSTER and NAME_CLUSTER
	MERGE (scs)-[:NAME_CLUSTER]->(ncs)

	// Merge the ALERT node on (guid, name), the unique key for an event: guids may repeat
	// across detections, but a guid fires at most once per detection name. This keeps
	// re-imports of the same data from duplicating alerts.
	MERGE (aa:ALERT {guid: $guid, name: $name, view: 2})
	ON CREATE SET aa.timestamp = $timestamp, aa.detection_type = $detection_type, aa.category = $category, aa.mitre_tactic = $mitre_tactic, aa.entity = $entity, aa.entity_type = $entity_type, aa.host_ip = $host_ip, aa.source_ip = $source_ip, aa.dest_ip = $dest_ip, aa.dest_port = $dest_port, aa.dst_geo = $dst_geo, aa.username = $username, aa.syscall_name = $syscall_name, aa.executable = $executable, aa.process = $process, aa.message = $message, aa.proctitle = $proctitle, aa.severity = $severity

	// Create the relationship between NAME_CLUSTER and ALERT
	MERGE (ncs)-[:INCLUDES]->(aa)
	`

	res, err = session.Run(ctx, query, params)
	utils.HandleResult(res, err)
}
