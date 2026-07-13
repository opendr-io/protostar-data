package auth

import (
	"context"
	"log"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

func GetSession(url, username, password string, encryption bool) (neo4j.DriverWithContext, neo4j.SessionWithContext) {
	// In driver v5, encryption is selected by the URI scheme instead of a config flag
	if encryption {
		url = "bolt+s" + url[len("bolt"):]
	}
	driver, err := neo4j.NewDriverWithContext(url, neo4j.BasicAuth(username, password, ""))
	if err != nil {
		panic(err)
	}

	ctx := context.Background()
	if err := driver.VerifyConnectivity(ctx); err != nil {
		log.Fatal("bye")
	}
	session := driver.NewSession(ctx, neo4j.SessionConfig{})
	return driver, session
}
