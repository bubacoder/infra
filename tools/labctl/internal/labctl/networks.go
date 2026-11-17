package labctl

import (
	"bytes"
	"context"
	"fmt"
	"slices"
	"strings"
)

func (c *Controller) createServiceNetworks(ctx context.Context, composeFile string, baseArgs []string) error {
	networks, err := externalNetworks(composeFile)
	if err != nil {
		fmt.Fprintf(c.Err, "Warning: extract networks from %s: %v\n", composeFile, err)
		return nil
	}
	for _, network := range networks {
		if strings.Contains(network, "$") {
			var output bytes.Buffer
			args := append(append([]string{}, baseArgs...), "config", "--format", "json", "--no-env-resolution")
			if err := c.Docker.Run(ctx, Invocation{Args: args, Stdout: &output, Stderr: c.Err}); err != nil {
				return fmt.Errorf("resolve external networks: %w", err)
			}
			document, err := parseComposeDocument(output.Bytes())
			if err != nil {
				return fmt.Errorf("parse resolved Compose configuration: %w", err)
			}
			networks = networkNames(document)
			break
		}
	}
	for _, network := range networks {
		err := c.docker(ctx, []string{"network", "inspect", network}, nil, true)
		if err == nil {
			continue
		}
		fmt.Fprintf(c.Out, "Creating network: %s\n", network)
		if err := c.docker(ctx, []string{"network", "create", "--driver", "bridge", network},
			nil, false); err != nil {
			return err
		}
	}
	return nil
}

func externalNetworks(filename string) ([]string, error) {
	document, err := composeDocument(filename)
	if err != nil {
		return nil, err
	}
	return networkNames(document), nil
}

func networkNames(document map[string]any) []string {
	networks, ok := document["networks"].(map[string]any)
	if !ok {
		return nil
	}
	var names []string
	for key, value := range networks {
		network, ok := value.(map[string]any)
		if !ok {
			continue
		}
		name, _ := network["name"].(string)
		switch external := network["external"].(type) {
		case bool:
			if external {
				if name == "" {
					name = key
				}
				names = append(names, name)
			}
		case map[string]any:
			if externalName, _ := external["name"].(string); externalName != "" {
				name = externalName
			}
			if name == "" {
				name = key
			}
			names = append(names, name)
		}
	}
	slices.Sort(names)
	return slices.Compact(names)
}
