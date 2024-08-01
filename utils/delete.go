package utils

import (
	"fmt"
	"log"

	"github.com/neo4j/neo4j-go-driver/neo4j"
)

// func DeleteAll(session neo4j.Session) {
// 	res, err := session.Run(`MATCH (n) DETACH DELETE n`, nil)
// 	HandleResult(res, err)
// }

func DeleteAll(session neo4j.Session) {
	for {
		// Get the total number of nodes before deletion
		res, err := session.Run(`MATCH (n) RETURN count(n) AS totalCountBefore`, nil)
		if err != nil {
			log.Fatalf("Failed to run get counter query: %v", err)
		}

		var totalCountBefore int64
		if res.Next() {
			totalCountBefore = res.Record().GetByIndex(0).(int64)
		}

		fmt.Printf("Total nodes before deletion: %d\n", totalCountBefore)

		if totalCountBefore == 0 {
			fmt.Println("No more nodes to delete.")
			break
		}

		// Run the deletion query
		_, err = session.Run(`CALL { MATCH (n) WITH n LIMIT 10000 RETURN n } DETACH DELETE n`, nil)
		if err != nil {
			log.Fatalf("Failed to run deletion query: %v", err)
			return
		}

		// Get the total number of nodes after deletion
		res, err = session.Run(`MATCH (n) RETURN count(n) AS totalCountAfter`, nil)
		if err != nil {
			log.Fatalf("Failed to run get counter query: %v", err)
		}

		var totalCountAfter int64
		if res.Next() {
			totalCountAfter = res.Record().GetByIndex(0).(int64)
		}

		fmt.Printf("Total nodes after deletion: %d\n", totalCountAfter)

		// Exit loop if no nodes are deleted
		if totalCountAfter == 0 {
			fmt.Println("No more nodes deleted in this iteration. Exiting.")
			break
		}
	}
}
