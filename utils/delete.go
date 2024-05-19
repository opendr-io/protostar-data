package utils

import (
	"github.com/neo4j/neo4j-go-driver/neo4j"
)

func DeleteAll(session neo4j.Session) {
	res, err := session.Run(`MATCH (n) DETACH DELETE n`, nil)
	HandleResult(res, err)
}
