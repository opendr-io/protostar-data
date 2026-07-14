package tests

import (
	"context"
	"os"
	"os/exec"
	"testing"

	"github.com/opendr-io/protostar-data/auth"
	"github.com/opendr-io/protostar-data/utils"
)

// TestImportIsIdempotent runs the real importer binary twice against a real
// Neo4j instance and verifies the second run adds no nodes and no
// relationships, i.e. re-running the importer without -reset cannot duplicate
// anything.
//
// The test only runs when NEO4J_TEST_URI is set and the target database is
// empty, so it never destroys existing data; it deletes what it imported
// before finishing, leaving the database empty again.
func TestImportIsIdempotent(t *testing.T) {
	explain(t, "running the real importer twice against Neo4j must change nothing the second time")

	uri := os.Getenv("NEO4J_TEST_URI")
	if uri == "" {
		skipf(t, "NEO4J_TEST_URI is not set, so the integration test did not run.\n"+
			"What it does: runs the importer twice against a real Neo4j database and verifies\n"+
			"the second run duplicates nothing. It requires an EMPTY database and leaves it\n"+
			"empty afterwards. To enable it: add NEO4J_TEST_URI=bolt://localhost:7687 to your\n"+
			".env file (or environment). Credentials come from NEO4J_USERNAME / NEO4J_PASSWORD.")
	}
	username := utils.EnvOr("NEO4J_USERNAME", "neo4j")
	password := utils.EnvOr("NEO4J_PASSWORD", "password")

	ctx := context.Background()
	driver, session := auth.GetSession(ctx, uri, username, password)
	defer driver.Close(ctx)
	defer session.Close(ctx)
	t.Logf("connected to %s", uri)

	count := func(query string) int64 {
		res, err := session.Run(ctx, query, nil)
		if err != nil {
			t.Fatalf("count query %q failed: %v", query, err)
		}
		if !res.Next(ctx) {
			t.Fatalf("count query %q returned no rows", query)
		}
		return res.Record().Values[0].(int64)
	}

	// Refuse to run against a database that already contains data.
	if existing := count(`MATCH (n) RETURN count(n)`); existing != 0 {
		skipf(t, "The database at %s already contains %d nodes, so the integration test did not run.\n"+
			"This test refuses to delete data it did not create. To run it, empty the database\n"+
			"first (e.g. MATCH (n) DETACH DELETE n in the Neo4j browser) and rerun with -count=1.", uri, existing)
	}
	t.Log("database is empty, safe to proceed (the test cleans up after itself)")
	defer func() {
		t.Log("cleaning up: deleting everything the test imported, leaving the database empty")
		utils.DeleteAll(ctx, session)
	}()

	// runImporter executes the actual CLI from the repository root, pointed at
	// the same database this test is inspecting.
	runImporter := func() {
		cmd := exec.Command("go", "run", ".", "-uri", uri, "-username", username, "-password", password)
		cmd.Dir = ".."
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			t.Fatalf("importer run failed: %v", err)
		}
	}

	t.Log("RUN 1: importing every JSON file in data/ into the empty database")
	runImporter()
	alerts, nodes, rels := count(`MATCH (a:ALERT) RETURN count(a)`),
		count(`MATCH (n) RETURN count(n)`),
		count(`MATCH ()-[r]->() RETURN count(r)`)
	if alerts == 0 {
		t.Fatal("first import created no ALERT nodes; the data directory may be empty or unreadable")
	}
	t.Logf("RUN 1 result: %d alerts, %d nodes, %d relationships", alerts, nodes, rels)

	t.Log("RUN 2: importing the exact same files again; an idempotent importer must change nothing")
	runImporter()
	if got := count(`MATCH (a:ALERT) RETURN count(a)`); got != alerts {
		t.Errorf("ALERT count changed from %d to %d: re-importing duplicated alerts, the (guid, name) MERGE in views/view2.go is not deduplicating", alerts, got)
	} else {
		t.Logf("RUN 2 result: ALERT count still %d — no duplicate alerts", alerts)
	}
	if got := count(`MATCH (n) RETURN count(n)`); got != nodes {
		t.Errorf("total node count changed from %d to %d: some node type is being re-created instead of merged", nodes, got)
	} else {
		t.Logf("RUN 2 result: node count still %d — no duplicate nodes of any kind", nodes)
	}
	if got := count(`MATCH ()-[r]->() RETURN count(r)`); got != rels {
		t.Errorf("relationship count changed from %d to %d: duplicate edges are being created", rels, got)
	} else {
		t.Logf("RUN 2 result: relationship count still %d — no duplicate edges", rels)
	}
}
