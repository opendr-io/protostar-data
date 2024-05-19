package read

import (
	"fmt"
	"io/ioutil"
	"log"
	"regexp"
	"strings"

	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"
)

func readFile(filePath string) (string, error) {
	file, err := ioutil.ReadFile(filePath)
	if err != nil {
		return "", err
	}
	return string(file), nil
}

func JSONFile(filename string) string {
	jsonString, err := readFile(filename)
	if err != nil {
		log.Fatal("Error reading JSON file:", err)
	}
	// modifiedJSON := filterJSONData(jsonString)
	modifiedJSON := jsonString
	// Change name
	gjson.Parse(jsonString).ForEach(func(key, value gjson.Result) bool {
		reg := regexp.MustCompile(`[^a-zA-Z0-9]+`)
		name := value.Get("name").String()
		cleanName := reg.ReplaceAllString(name, "_")
		cleanName = strings.ToUpper(cleanName)

		var err error
		modifiedJSON, err = sjson.Set(modifiedJSON, fmt.Sprintf("%s.name", key.String()), cleanName)
		if err != nil {
			log.Fatal(err)
		}

		alert_type := value.Get("type").String()
		cleanAlertTypeName := reg.ReplaceAllString(alert_type, "_")
		cleanAlertTypeName = strings.ToUpper(cleanAlertTypeName)
		// fmt.Println(cleanAlertTypeName, alert_type)
		// os.Exit(1)
		modifiedJSON, err = sjson.Set(modifiedJSON, fmt.Sprintf("%s.type", key.String()), cleanAlertTypeName)
		if err != nil {
			log.Fatal(err)
		}

		return true
	})

	return modifiedJSON

}
