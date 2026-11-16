package labctl

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
)

func (c *Controller) Service(
	ctx context.Context,
	operation, stack string,
	options DockerOptions,
) error {
	if !ValidOperation(operation) {
		return fmt.Errorf("unknown operation %q", operation)
	}
	category, service, err := splitStack(stack)
	if err != nil {
		return err
	}
	return c.service(ctx, c.hostConfigDir(), category, service, operation, options)
}

func (c *Controller) ApplyConfig(
	ctx context.Context,
	configFile, stateOverride string,
	options DockerOptions,
) error {
	hostConfigDir := c.hostConfigDir()
	if configFile == "" {
		configFile = filepath.Join(hostConfigDir, "services.yaml")
	} else {
		hostConfigDir = filepath.Dir(configFile)
	}
	config, err := loadServicesConfig(configFile)
	if err != nil {
		return err
	}
	if stateOverride != "" && !ValidOperation(stateOverride) {
		return fmt.Errorf("unknown operation %q", stateOverride)
	}
	fmt.Fprintln(c.Out, "Init...")
	c.createLocalhostLink(filepath.Dir(hostConfigDir))
	for _, category := range config.Services {
		if len(category) != 1 {
			fmt.Fprintf(c.Err, "Warning: skipping invalid category entry: %v\n", category)
			continue
		}
		for categoryName, services := range category {
			for _, service := range services {
				if service.Name == "" {
					fmt.Fprintf(c.Err,
						"Warning: skipping invalid service entry in category %s: missing name\n",
						categoryName,
					)
					continue
				}
				categoryPath, serviceName, err := splitStack(
					filepath.ToSlash(categoryName) + "/" + service.Name,
				)
				if err != nil {
					fmt.Fprintf(c.Err, "Warning: skipping invalid service entry %s/%s: %v\n",
						categoryName, service.Name, err)
					continue
				}
				operation := service.State
				if stateOverride != "" {
					operation = stateOverride
				}
				if operation == "" {
					operation = "up"
				}
				operation = strings.ToLower(operation)
				if !ValidOperation(operation) {
					fmt.Fprintf(c.Err, "Warning: unknown state %q for service %s/%s\n",
						operation, categoryName, service.Name)
					continue
				}
				if err := c.service(ctx, hostConfigDir, categoryPath, serviceName,
					operation, options); err != nil {
					return err
				}
			}
		}
	}
	return nil
}
