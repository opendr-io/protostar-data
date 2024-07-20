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

	// fmt.Println("Creating unique set of entities 3")
	query = `
	MATCH (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})
	MERGE (ad:AS_DEST {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, dest_ip: $dest_ip})
	ON CREATE SET ad.count = 1
	ON MATCH SET ad.count = ad.count + 1
	WITH e, ad
	MATCH (e_dest:ENTITY {ip: $dest_ip, view: 2})
	MERGE (e_dest)-[:AS_DEST]->(ad)
	
	MERGE (sc:SEVERITY_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, dest_ip: $dest_ip, severity: $severity})
	ON CREATE SET sc.count = 1
	ON MATCH SET sc.count = sc.count + 1
	MERGE (ad)-[:HAS_SEVERITY]->(sc)
	
	MERGE (nc:NAME_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, dest_ip: $dest_ip, severity: $severity, name: $name})
	ON CREATE SET nc.count = 1
	ON MATCH SET nc.count = nc.count + 1
	MERGE (sc)-[:NAME_CLUSTER]->(nc)
	
	CREATE (a:ALERT {guid: $guid, timestamp: $timestamp, detection_type: $detection_type, name: $name, category: $category, mitre_tactic: $mitre_tactic, entity: $entity, entity_type: $entity_type, host_ip: $host_ip, source_ip: $source_ip, dest_ip: $dest_ip, dest_port: $dest_port, dst_geo: $dst_geo, username: $username, syscall_name: $syscall_name, executable: $executable, process: $process, message: $message, proctitle: $proctitle, severity: $severity, view: 2})
	MERGE (nc)-[:INCLUDES]->(a)
	`
	res, err = session.Run(query, params)
	utils.HandleResult(res, err)

	// fmt.Println("Creating unique set of entities 4")
	query = `
	MATCH (e:ENTITY {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2})
	MERGE (as:AS_SOURCE {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, source_ip: $source_ip})
	ON CREATE SET as.count = 1
	ON MATCH SET as.count = as.count + 1
	WITH e, as
	MATCH (e_source:ENTITY {ip: $source_ip, view: 2})
	MERGE (e_source)-[:AS_SOURCE]->(as)
	
	
	MERGE (scs:SEVERITY_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, source_ip: $source_ip, severity: $severity})
	ON CREATE SET scs.count = 1
	ON MATCH SET scs.count = scs.count + 1
	MERGE (as)-[:HAS_SEVERITY]->(scs)
	
	MERGE (ncs:NAME_CLUSTER {ip: $host_ip, entity: $entity, entity_type: $entity_type, view: 2, source_ip: $source_ip, severity: $severity, name: $name})
	ON CREATE SET ncs.count = 1
	ON MATCH SET ncs.count = ncs.count + 1
	MERGE (scs)-[:NAME_CLUSTER]->(ncs)
	
	CREATE (aa:ALERT {guid: $guid, timestamp: $timestamp, detection_type: $detection_type, name: $name, category: $category, mitre_tactic: $mitre_tactic, entity: $entity, entity_type: $entity_type, host_ip: $host_ip, source_ip: $source_ip, dest_ip: $dest_ip, dest_port: $dest_port, dst_geo: $dst_geo, username: $username, syscall_name: $syscall_name, executable: $executable, process: $process, message: $message, proctitle: $proctitle, severity: $severity, view: 2})
	MERGE (ncs)-[:INCLUDES]->(aa)
	`
	res, err = session.Run(query, params)
	utils.HandleResult(res, err)
}
