package labctl

import (
	"os"

	"gopkg.in/yaml.v3"
)

func hasBuildDirective(filename string) bool {
	document, err := composeDocument(filename)
	if err != nil {
		return false
	}
	services, ok := document["services"].(map[string]any)
	if !ok {
		return false
	}
	for _, value := range services {
		service, ok := value.(map[string]any)
		if !ok {
			continue
		}
		if _, exists := service["build"]; exists {
			return true
		}
	}
	return false
}

func composeDocument(filename string) (map[string]any, error) {
	content, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	var document map[string]any
	if err := yaml.Unmarshal(content, &document); err != nil {
		return nil, err
	}
	return document, nil
}
