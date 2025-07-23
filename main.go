package main

import (
	"fmt"
	"log"
	"os"
	"regexp"
	"strings"

	"github.com/cyberdyne-ventures/salvation/auth"
	"github.com/cyberdyne-ventures/salvation/utils"
	"github.com/cyberdyne-ventures/salvation/views"
	"github.com/neo4j/neo4j-go-driver/neo4j"
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

func main() {
	// local data
	// This is default password. DO NOT USE IN PRODUCTION
	driver, session := auth.GetSession("bolt://localhost:7687", "neo4j", "password", false)

	fmt.Println("Driver = ", driver)
	fmt.Println("Session = ", session)
	defer driver.Close()
	defer session.Close()

	// Delete everything to reset the graph before insertion
	utils.DeleteAll(session)
	files, err := os.ReadDir("data")
	if err != nil {
		panic(err)
	}
	for _, file := range files {
		insert(session, ("data\\" + file.Name()))
	}

	fmt.Println("Data imported successfully.")
}
