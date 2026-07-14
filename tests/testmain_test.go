package tests

import (
	"fmt"
	"os"
	"sync"
	"testing"

	"github.com/joho/godotenv"
)

type outcome struct {
	name        string
	explanation string
	status      string
}

var (
	outcomesMu sync.Mutex
	outcomes   []outcome
)

// explain prints what a test is about to verify (always visible, unlike t.Log,
// which needs -v) and records the test's final status for the summary that
// TestMain prints when the run finishes.
func explain(t *testing.T, what string) {
	fmt.Printf("=== %s\n    %s\n", t.Name(), what)
	t.Cleanup(func() {
		status := "PASS"
		if t.Failed() {
			status = "FAIL"
		} else if t.Skipped() {
			status = "SKIP"
		}
		fmt.Printf("--- %s: %s\n\n", status, t.Name())
		outcomesMu.Lock()
		outcomes = append(outcomes, outcome{t.Name(), what, status})
		outcomesMu.Unlock()
	})
}

// skipf prints the skip reason (always visible, unlike t.Skipf's message,
// which needs -v) and then skips the test.
func skipf(t *testing.T, format string, args ...interface{}) {
	fmt.Printf("    skipped: "+format+"\n", args...)
	t.Skipf(format, args...)
}

// TestMain loads the repository's optional .env file (same as the importer
// itself) before running tests, and prints a summary of every test afterwards.
func TestMain(m *testing.M) {
	_ = godotenv.Load("../.env")
	code := m.Run()
	if len(outcomes) > 0 {
		fmt.Println("=============================== TEST SUMMARY ===============================")
		counts := map[string]int{}
		for _, o := range outcomes {
			fmt.Printf("%-5s %-24s %s\n", o.status, o.name, o.explanation)
			counts[o.status]++
		}
		fmt.Println("=============================================================================")
		fmt.Printf("%d passed, %d failed, %d skipped (run with -v for detailed narration)\n", counts["PASS"], counts["FAIL"], counts["SKIP"])
	}
	os.Exit(code)
}
