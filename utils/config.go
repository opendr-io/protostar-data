package utils

import "os"

// EnvOr returns the value of the environment variable key, or def if it is
// unset or empty.
func EnvOr(key, def string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return def
}
