package labctl

import (
	"context"
	"fmt"
	"slices"
)

func (c *Controller) createServiceNetworks(ctx context.Context, composeFile string) error {
	networks, err := externalNetworks(composeFile)
	if err != nil {
		fmt.Fprintf(c.Err, "Warning: extract networks from %s: %v\n", composeFile, err)
		return nil
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
	networks, ok := document["networks"].(map[string]any)
	if !ok {
		return nil, nil
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
	return slices.Compact(names), nil
}
