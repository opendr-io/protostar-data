package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/joho/godotenv"
	"github.com/neo4j/neo4j-go-driver/neo4j"
	"github.com/opendr-io/protostar-data/auth"
	"github.com/opendr-io/protostar-data/utils"
	"github.com/opendr-io/protostar-data/views"
	"github.com/schollz/progressbar/v3"
	"github.com/tidwall/gjson"
)

func insert(session neo4j.Session, filename string) {

	// modifiedJSON := read.ReadFile(filename)
	fmt.Printf("Reading data from %s\n", filename)
	file, err := os.ReadFile(filename)
	if err != nil {
		log.Fatalf("Unable to read file - %s", filename)
	}
	modifiedJSON := string(file)

	totalItems := int(gjson.Parse(modifiedJSON).Get("#").Int())
	bar := progressbar.NewOptions(totalItems,
		progressbar.OptionSetDescription(fmt.Sprintf("Processing JSON data from %s", filename)),
		progressbar.OptionSetWidth(50),
		progressbar.OptionShowCount(),
		progressbar.OptionSetPredictTime(false),
		progressbar.OptionSetTheme(progressbar.Theme{
			Saucer:        "#",
			SaucerHead:    ">",
			SaucerPadding: "-",
			BarStart:      "[",
			BarEnd:        "]",
		}),
	)
	var reg = regexp.MustCompile(`[^a-zA-Z0-9]+`)

	gjson.Parse(modifiedJSON).ForEach(func(key, value gjson.Result) bool {
		params := map[string]interface{}{
			"source":         value.Get("source").String(),
			"guid":           value.Get("guid").String(),
			"timestamp":      value.Get("timestamp").String(),
			"detection_type": strings.ToUpper(reg.ReplaceAllString(value.Get("detection_type").String(), "_")),
			"name":           strings.ToUpper(reg.ReplaceAllString(value.Get("name").String(), "_")),
			"severity":       value.Get("severity").String(),
			"category":       value.Get("category").String(),
			"mitre_tactic":   value.Get("mitre_tactic").String(),
			"entity":         value.Get("entity").String(),
			"entity_type":    value.Get("entity_type").String(),
			"host_ip":        value.Get("host_ip").String(),
			"source_ip":      value.Get("source_ip").String(),
			"dest_ip":        value.Get("dest_ip").String(),
			"dest_port":      value.Get("dest_port").String(),
			"dst_geo":        value.Get("dst_geo").String(),
			"username":       value.Get("username").String(),
			"syscall_name":   value.Get("syscall_name").String(),
			"executable":     value.Get("executable").String(),
			"process":        value.Get("process").String(),
			"message":        value.Get("message").String(),
			"proctitle":      value.Get("proctitle").String(),
		}
		views.View1(session, params)
		views.View2(session, params)
		bar.Add(1)
		return true
	})
	fmt.Println()
}

// envOr returns the value of the environment variable key, or def if it is unset or empty.
func envOr(key, def string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return def
}

func main() {
	// Load optional .env file into the environment; real environment variables win over
	// .env values, so precedence is: flags > environment > .env > local defaults.
	if err := godotenv.Load(); err != nil && !os.IsNotExist(err) {
		log.Fatalf("Unable to load .env file: %v", err)
	}

	// Connection options: flags override environment variables, which override the local defaults.
	// The password default is Neo4j's out-of-the-box value. DO NOT USE IN PRODUCTION
	uri := flag.String("uri", envOr("NEO4J_URI", "bolt://localhost:7687"), "Neo4j connection URI")
	username := flag.String("username", envOr("NEO4J_USERNAME", "neo4j"), "Neo4j username")
	password := flag.String("password", envOr("NEO4J_PASSWORD", "password"), "Neo4j password")
	encrypted := flag.Bool("encrypted", os.Getenv("NEO4J_ENCRYPTED") == "true", "use an encrypted (TLS) connection")
	dataDir := flag.String("data", "data", "directory containing the JSON files to import")
	reset := flag.Bool("reset", false, "delete the entire existing graph before importing")
	flag.Parse()

	driver, session := auth.GetSession(*uri, *username, *password, *encrypted)

	fmt.Println("Driver = ", driver)
	fmt.Println("Session = ", session)
	defer driver.Close()
	defer session.Close()

	// Delete everything to reset the graph before insertion (only when -reset is passed)
	if *reset {
		utils.DeleteAll(session)
	}
	files, err := os.ReadDir(*dataDir)
	if err != nil {
		panic(err)
	}
	for _, file := range files {
		if filepath.Ext(file.Name()) == ".json" {
			path := filepath.Join(*dataDir, file.Name())
			insert(session, path)
		}
	}

	fmt.Println("Data imported successfully.")
}
