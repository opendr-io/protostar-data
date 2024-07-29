package utils

// // Integrated the changes directly in insert function
// func FilterJSONData(jsonString string) string {
// 	// Change name
// 	modifiedJSON := jsonString
// 	gjson.Parse(jsonString).ForEach(func(key, value gjson.Result) bool {
// 		reg := regexp.MustCompile(`[^a-zA-Z0-9]+`)
// 		cleanName := strings.ToUpper(reg.ReplaceAllString(value.Get("name").String(), "_"))

// 		var err error
// 		modifiedJSON, err = sjson.Set(modifiedJSON, fmt.Sprintf("%s.name", key.String()), cleanName)
// 		if err != nil {
// 			log.Fatal(err)
// 		}

// 		// replace all special chars with _ and make it uppercase
// 		cleanAlertTypeName := strings.ToUpper(reg.ReplaceAllString(value.Get("type").String(), "_"))
// 		// fmt.Println(cleanAlertTypeName, alert_type)
// 		// os.Exit(1)
// 		modifiedJSON, err = sjson.Set(modifiedJSON, fmt.Sprintf("%s.type", key.String()), cleanAlertTypeName)
// 		if err != nil {
// 			log.Fatal(err)
// 		}

// 		return true
// 	})

// 	return modifiedJSON

// }
