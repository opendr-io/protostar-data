package auth

import (
	"context"
	"log"

	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

// GetSession connects to Neo4j and returns an open driver and session.
// In driver v5 encryption is selected by the URI scheme (bolt+s://, or
// neo4j+s:// for Aura), so there is no separate encryption switch.
func GetSession(ctx context.Context, url, username, password string) (neo4j.DriverWithContext, neo4j.SessionWithContext) {
	driver, err := neo4j.NewDriverWithContext(url, neo4j.BasicAuth(username, password, ""))
	if err != nil {
		log.Fatalf("Invalid Neo4j connection URI %s: %v", url, err)
	}

	if err := driver.VerifyConnectivity(ctx); err != nil {
		log.Fatalf("Unable to connect to Neo4j at %s: %v", url, err)
	}
	session := driver.NewSession(ctx, neo4j.SessionConfig{})
	return driver, session
}
