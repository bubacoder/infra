package labctl

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type servicesConfig struct {
	Services []map[string][]serviceConfig `yaml:"services"`
}

type serviceConfig struct {
	Name  string `yaml:"name"`
	State string `yaml:"state"`
}

func loadServicesConfig(filename string) (servicesConfig, error) {
	content, err := os.ReadFile(filename)
	if err != nil {
		return servicesConfig{}, fmt.Errorf("load services configuration %s: %w", filename, err)
	}
	var config servicesConfig
	if err := yaml.Unmarshal(content, &config); err != nil {
		return servicesConfig{}, fmt.Errorf("parse services configuration %s: %w", filename, err)
	}
	if config.Services == nil {
		return servicesConfig{}, fmt.Errorf("invalid configuration: services key not found")
	}
	return config, nil
}
