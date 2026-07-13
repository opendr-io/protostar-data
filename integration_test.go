package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/opendr-io/protostar-data/auth"
	"github.com/opendr-io/protostar-data/utils"
)

// TestImportIsIdempotent imports the sample data twice into a real Neo4j
// instance and verifies the second pass adds no nodes and no relationships,
// i.e. re-running the importer without -reset cannot duplicate anything.
//
// The test only runs when NEO4J_TEST_URI is set and the target database is
// empty, so it never destroys existing data; it deletes what it imported
// before finishing, leaving the database empty again.
//
// Run with -v to see an explanation of each phase.
func TestImportIsIdempotent(t *testing.T) {
	explain(t, "importing all sample data twice into a real Neo4j must change nothing the second time")
	uri := os.Getenv("NEO4J_TEST_URI")
	if uri == "" {
		t.Skip("NEO4J_TEST_URI is not set, so the integration test did not run.\n" +
			"What it does: imports the sample data twice into a real Neo4j database and\n" +
			"verifies the second pass duplicates nothing. It requires an EMPTY database\n" +
			"and leaves it empty afterwards.\n" +
			"To enable it: add NEO4J_TEST_URI=bolt://localhost:7687 to your .env file (or\n" +
			"environment). Credentials are read from NEO4J_USERNAME / NEO4J_PASSWORD as usual.")
	}

	driver, session := auth.GetSession(uri, envOr("NEO4J_USERNAME", "neo4j"), envOr("NEO4J_PASSWORD", "password"), false)
	defer driver.Close()
	defer session.Close()
	t.Logf("connected to %s", uri)

	count := func(query string) int64 {
		res, err := session.Run(query, nil)
		if err != nil {
			t.Fatalf("count query %q failed: %v", query, err)
		}
		if !res.Next() {
			t.Fatalf("count query %q returned no rows", query)
		}
		return res.Record().GetByIndex(0).(int64)
	}

	// Refuse to run against a database that already contains data.
	if existing := count(`MATCH (n) RETURN count(n)`); existing != 0 {
		t.Skipf("The database at %s already contains %d nodes, so the integration test did not run.\n"+
			"This test refuses to delete data it did not create. To run it, empty the database\n"+
			"first (e.g. MATCH (n) DETACH DELETE n in the Neo4j browser) and rerun with -count=1.", uri, existing)
	}
	t.Log("database is empty, safe to proceed (the test cleans up after itself)")
	defer func() {
		t.Log("cleaning up: deleting everything the test imported, leaving the database empty")
		utils.DeleteAll(session)
	}()

	importAll := func() {
		files, err := os.ReadDir("data")
		if err != nil {
			t.Fatalf("reading data directory: %v", err)
		}
		for _, file := range files {
			if filepath.Ext(file.Name()) == ".json" {
				insert(session, filepath.Join("data", file.Name()))
			}
		}
	}

	t.Log("PASS 1: importing every JSON file in data/ into the empty database")
	importAll()
	alerts, nodes, rels := count(`MATCH (a:ALERT) RETURN count(a)`),
		count(`MATCH (n) RETURN count(n)`),
		count(`MATCH ()-[r]->() RETURN count(r)`)
	if alerts == 0 {
		t.Fatal("first import created no ALERT nodes; the data directory may be empty or unreadable")
	}
	t.Logf("PASS 1 result: %d alerts, %d nodes, %d relationships", alerts, nodes, rels)

	t.Log("PASS 2: importing the exact same files again; an idempotent importer must change nothing")
	importAll()
	if got := count(`MATCH (a:ALERT) RETURN count(a)`); got != alerts {
		t.Errorf("ALERT count changed from %d to %d: re-importing duplicated alerts, the (guid, name) MERGE in views/view2.go is not deduplicating", alerts, got)
	} else {
		t.Logf("PASS 2 result: ALERT count still %d — no duplicate alerts", alerts)
	}
	if got := count(`MATCH (n) RETURN count(n)`); got != nodes {
		t.Errorf("total node count changed from %d to %d: some node type is being re-created instead of merged", nodes, got)
	} else {
		t.Logf("PASS 2 result: node count still %d — no duplicate nodes of any kind", nodes)
	}
	if got := count(`MATCH ()-[r]->() RETURN count(r)`); got != rels {
		t.Errorf("relationship count changed from %d to %d: duplicate edges are being created", rels, got)
	} else {
		t.Logf("PASS 2 result: relationship count still %d — no duplicate edges", rels)
	}
}
