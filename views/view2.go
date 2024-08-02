package views

import (
	"fmt"

	"github.com/cyberdyne-ventures/salvation/utils"
	"github.com/neo4j/neo4j-go-driver/neo4j"
)

func View2(session neo4j.Session, params map[string]interface{}) {
	// fmt.Println("Creating unique set of entities 2")
	query := fmt.Sprintf(`
	MERGE (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})
	ON CREATE SET e.count = 1
	ON MATCH SET e.count = e.count + 1`)
	res, err := session.Run(query, params)
	utils.HandleResult(res, err)

	query = `
	// Match the ENTITY node with the given parameters
	MATCH (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})

	// Merge the SEVERITY_CLUSTER node and update its count
	MERGE (scs:SEVERITY_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, source_ip: $source_ip, dest_ip: $dest_ip, severity: $severity})
	ON CREATE SET scs.count = 1
	ON MATCH SET scs.count = scs.count + 1

	// Create the relationship between ENTITY and SEVERITY_CLUSTER
	MERGE (e)-[:HAS_SEVERITY]->(scs)

	// Merge the NAME_CLUSTER node and update its count
	MERGE (ncs:NAME_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, source_ip: $source_ip, dest_ip: $dest_ip, severity: $severity, name: $name})
	ON CREATE SET ncs.count = 1
	ON MATCH SET ncs.count = ncs.count + 1

	// Create the relationship between SEVERITY_CLUSTER and NAME_CLUSTER
	MERGE (scs)-[:NAME_CLUSTER]->(ncs)

	// Create the ALERT node with the given parameters
	CREATE (aa:ALERT {guid: $guid, timestamp: $timestamp, detection_type: $detection_type, name: $name, category: $category, mitre_tactic: $mitre_tactic, entity: $entity, entity_type: $entity_type, host_ip: $host_ip, source_ip: $source_ip, dest_ip: $dest_ip, dest_port: $dest_port, dst_geo: $dst_geo, username: $username, syscall_name: $syscall_name, executable: $executable, process: $process, message: $message, proctitle: $proctitle, severity: $severity, view: 2})

	// Create the relationship between NAME_CLUSTER and ALERT
	MERGE (ncs)-[:INCLUDES]->(aa)
	`

	res, err = session.Run(query, params)
	utils.HandleResult(res, err)
}
