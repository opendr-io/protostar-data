package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"testing"

	"github.com/tidwall/gjson"
)

func TestEnvOr(t *testing.T) {
	explain(t, "envOr prefers a set environment variable and falls back to the default otherwise")
	t.Setenv("PROTOSTAR_TEST_KEY", "from-env")
	if got := envOr("PROTOSTAR_TEST_KEY", "fallback"); got != "from-env" {
		t.Errorf("envOr should prefer a set environment variable: got %q, want %q", got, "from-env")
	}
	t.Setenv("PROTOSTAR_TEST_KEY", "")
	if got := envOr("PROTOSTAR_TEST_KEY", "fallback"); got != "fallback" {
		t.Errorf("envOr should fall back when the variable is empty: got %q, want %q", got, "fallback")
	}
}

// TestAlertKeyUniqueness guards the ALERT merge key used in views/view2.go.
// Alerts are deduplicated on (guid, name): guids may repeat across detections,
// but a guid fires at most once per detection name. If two different events
// shared the pair, the second would be silently dropped on import, so defective
// data must fail here instead. Byte-identical repeats are tolerated because
// merging them is lossless.
//
// Run with -v to see what was checked. Run this first when adding data files.
func TestAlertKeyUniqueness(t *testing.T) {
	explain(t, "no two different events in data/ may share a (guid, name) pair, the importer's dedup key")
	reg := regexp.MustCompile(`[^a-zA-Z0-9]+`)
	files, err := os.ReadDir("data")
	if err != nil {
		t.Fatalf("reading data directory: %v", err)
	}

	type event struct {
		where  string
		parsed map[string]interface{}
	}
	seen := map[[2]string]event{}
	checked := 0
	identicalRepeats := 0
	sharedGuids := map[string]bool{}

	for _, file := range files {
		if filepath.Ext(file.Name()) != ".json" {
			continue
		}
		path := filepath.Join("data", file.Name())
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("reading %s: %v", path, err)
		}
		fileEvents := 0
		gjson.ParseBytes(raw).ForEach(func(idx, value gjson.Result) bool {
			where := fmt.Sprintf("%s[%d]", path, idx.Int())
			checked++
			fileEvents++

			guid := value.Get("guid").String()
			name := strings.ToUpper(reg.ReplaceAllString(value.Get("name").String(), "_"))
			if guid == "" {
				t.Errorf("%s: event has no guid; the importer could not deduplicate it", where)
				return true
			}
			if name == "" {
				t.Errorf("%s: event has no name; the importer could not deduplicate it", where)
				return true
			}

			var parsed map[string]interface{}
			if err := json.Unmarshal([]byte(value.Raw), &parsed); err != nil {
				t.Errorf("%s: event is not a JSON object: %v", where, err)
				return true
			}

			key := [2]string{guid, name}
			if prev, dup := seen[key]; dup {
				if reflect.DeepEqual(prev.parsed, parsed) {
					// Harmless: importing an exact copy merges into one node.
					identicalRepeats++
				} else {
					t.Errorf("DEFECTIVE DATA: %s and %s are different events but share guid %q and name %q; the importer would keep only the first and silently drop the second", prev.where, where, guid, name)
				}
				return true
			}
			if _, guidSeen := sharedGuids[guid]; guidSeen {
				// Expected: one guid, several detection names.
				sharedGuids[guid] = true
			} else {
				sharedGuids[guid] = false
			}
			seen[key] = event{where: where, parsed: parsed}
			return true
		})
		t.Logf("%s: %d events", path, fileEvents)
	}

	if checked == 0 {
		t.Fatal("no events found in data directory; nothing was validated")
	}

	reused := 0
	for _, multi := range sharedGuids {
		if multi {
			reused++
		}
	}
	t.Logf("checked %d events: %d unique (guid, name) keys, %d guids legitimately reused by multiple detections, %d byte-identical repeats (tolerated)", checked, len(seen), reused, identicalRepeats)
	t.Log("invariant held: no two different events share a (guid, name) pair, so the importer cannot silently drop any of them")
}
