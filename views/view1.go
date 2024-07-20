package views

import (
	"fmt"

	"github.com/neo4j/neo4j-go-driver/neo4j"

	"github.com/cyberdyne-ventures/salvation/utils"
)

func View1(session neo4j.Session, params map[string]interface{}) {
	// fmt.Println("Creating unique set of entities 1")
	query := fmt.Sprintf(`
	MERGE (e:ENTITY {ip: $host_ip, entity: $entity, view: 1})
	ON CREATE SET e.count = 1
	ON MATCH SET e.count = e.count + 1
	MERGE (summary:%s_TYPE_SUMMARY {ip: $host_ip, entity: $entity, detection_type: $detection_type, view: 1})
	ON CREATE SET summary.count = 1
	ON MATCH SET summary.count = summary.count + 1
	MERGE (e)-[:%s{view: 1}]->(summary)
	MERGE (nsummary:%s_NAME_SUMMARY {ip: $host_ip, entity: $entity, name: $name, detection_type: $detection_type, view: 1})
	ON CREATE SET nsummary.count = 1
	ON MATCH SET nsummary.count = nsummary.count + 1
	MERGE (summary)-[:%s{view: 1}]->(nsummary)`, params["detection_type"], params["detection_type"], params["name"], params["name"])
	res, err := session.Run(query, params)
	utils.HandleResult(res, err)
}
