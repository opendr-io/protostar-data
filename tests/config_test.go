package tests

import (
	"testing"

	"github.com/opendr-io/protostar-data/utils"
)

func TestEnvOr(t *testing.T) {
	explain(t, "utils.EnvOr prefers a set environment variable and falls back to the default otherwise")
	t.Setenv("PROTOSTAR_TEST_KEY", "from-env")
	if got := utils.EnvOr("PROTOSTAR_TEST_KEY", "fallback"); got != "from-env" {
		t.Errorf("EnvOr should prefer a set environment variable: got %q, want %q", got, "from-env")
	}
	t.Setenv("PROTOSTAR_TEST_KEY", "")
	if got := utils.EnvOr("PROTOSTAR_TEST_KEY", "fallback"); got != "fallback" {
		t.Errorf("EnvOr should fall back when the variable is empty: got %q, want %q", got, "fallback")
	}
}
