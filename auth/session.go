package auth

import (
	"log"

	"github.com/neo4j/neo4j-go-driver/neo4j"
)

func GetSession(url, username, password string, encryption bool) (neo4j.Driver, neo4j.Session) {
	driver, err := neo4j.NewDriver(url, neo4j.BasicAuth(username, password, ""), func(c *neo4j.Config) {
		c.Encrypted = encryption
		// c.TrustStrategy = neo4j.TrustAny(true)
	})
	if err != nil {
		panic(err)
	}
	// defer driver.Close()

	session, err := driver.NewSession(neo4j.SessionConfig{})
	if err != nil {
		log.Fatal("bye")
	}
	// defer session.Close()
	return driver, session
}
