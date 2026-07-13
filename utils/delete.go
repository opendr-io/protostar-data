package utils

import (
	"context"
	"fmt"
	"log"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

func DeleteAll(ctx context.Context, session neo4j.SessionWithContext) {
	for {
		// Get the total number of nodes before deletion
		res, err := session.Run(ctx, `MATCH (n) RETURN count(n) AS totalCountBefore`, nil)
		if err != nil {
			log.Fatalf("Failed to run get counter query: %v", err)
		}

		var totalCountBefore int64
		if res.Next(ctx) {
			totalCountBefore = res.Record().Values[0].(int64)
		}

		fmt.Printf("Total nodes before deletion: %d\n", totalCountBefore)

		if totalCountBefore == 0 {
			fmt.Println("No more nodes to delete.")
			break
		}

		// Run the deletion query
		_, err = session.Run(ctx, `CALL { MATCH (n) WITH n LIMIT 10000 RETURN n } DETACH DELETE n`, nil)
		if err != nil {
			log.Fatalf("Failed to run deletion query: %v", err)
			return
		}

		// Get the total number of nodes after deletion
		res, err = session.Run(ctx, `MATCH (n) RETURN count(n) AS totalCountAfter`, nil)
		if err != nil {
			log.Fatalf("Failed to run get counter query: %v", err)
		}

		var totalCountAfter int64
		if res.Next(ctx) {
			totalCountAfter = res.Record().Values[0].(int64)
		}

		fmt.Printf("Total nodes after deletion: %d\n", totalCountAfter)

		// Exit loop if no nodes are deleted
		if totalCountAfter == 0 {
			fmt.Println("No more nodes deleted in this iteration. Exiting.")
			break
		}
	}
}
