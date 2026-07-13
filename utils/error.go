package utils

import (
	"log"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

func HandleResult(res neo4j.ResultWithContext, err error) {
	if err != nil {
		log.Fatal("Failed to run query", err.Error())
	}
	if res.Err() != nil {
		log.Println(">>>", res.Err().Error())
	}
}
