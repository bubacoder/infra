package labctl

import (
	"bytes"
	"context"
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

func hasBuildDirective(filename string) bool {
	document, err := composeDocument(filename)
	if err != nil {
		return false
	}
	return documentHasBuild(document)
}

func documentHasBuild(document map[string]any) bool {
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

func (c *Controller) resolvedCompose(ctx context.Context, baseArgs []string) (map[string]any, error) {
	var output bytes.Buffer
	args := append(append([]string{}, baseArgs...), "config", "--format", "json", "--no-env-resolution")
	if err := c.Docker.Run(ctx, Invocation{Args: args, Stdout: &output, Stderr: c.Err}); err != nil {
		return nil, fmt.Errorf("resolve Compose configuration: %w", err)
	}
	document, err := parseComposeDocument(output.Bytes())
	if err != nil {
		return nil, fmt.Errorf("parse resolved Compose configuration: %w", err)
	}
	return document, nil
}

func composeDocument(filename string) (map[string]any, error) {
	content, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	return parseComposeDocument(content)
}

func parseComposeDocument(content []byte) (map[string]any, error) {
	var document map[string]any
	if err := yaml.Unmarshal(content, &document); err != nil {
		return nil, err
	}
	return document, nil
}
