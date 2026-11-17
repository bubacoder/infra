package labctl

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func (c *Controller) hostConfigDir() string {
	return filepath.Join(c.DockerConfig, c.Hostname)
}

func (c *Controller) createLocalhostLink(configDir string) {
	hostnameDir := filepath.Join(configDir, c.Hostname)
	info, err := os.Stat(hostnameDir)
	if err != nil || !info.IsDir() {
		return
	}
	link := filepath.Join(configDir, "localhost")
	info, err = os.Lstat(link)
	if err == nil && info.Mode()&os.ModeSymlink == 0 {
		fmt.Fprintf(c.Err, "Error: %s exists but is not a symlink. Cannot create link.\n", link)
		return
	}
	if err == nil {
		if err := os.Remove(link); err != nil {
			fmt.Fprintf(c.Err, "Error removing %s: %v\n", link, err)
			return
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		fmt.Fprintf(c.Err, "Error inspecting %s: %v\n", link, err)
		return
	}
	if err := os.Symlink(c.Hostname+"/", link); err != nil {
		fmt.Fprintf(c.Err, "Error creating localhost symlink: %v\n", err)
	}
}

func splitStack(stack string) (string, string, error) {
	parts := strings.Split(filepath.ToSlash(stack), "/")
	if len(parts) < 2 || parts[len(parts)-1] == "" {
		return "", "", fmt.Errorf(
			"service name must be category/name or category/subcategory/name",
		)
	}
	for _, part := range parts {
		if part == "" || part == "." || part == ".." {
			return "", "", fmt.Errorf("service name contains an invalid path component")
		}
	}
	return filepath.Join(parts[:len(parts)-1]...), parts[len(parts)-1], nil
}

func envFileArgs(hostConfigDir, service string) []string {
	paths := []string{
		filepath.Join(filepath.Dir(hostConfigDir), ".env"),
		filepath.Join(hostConfigDir, ".env"),
		filepath.Join(filepath.Dir(hostConfigDir), ".env."+service),
		filepath.Join(hostConfigDir, ".env."+service),
	}
	var args []string
	for _, path := range paths {
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			args = append(args, "--env-file", path)
		}
	}
	return args
}

func gpuSuffix(hostConfigDir string) string {
	content, err := os.ReadFile(filepath.Join(hostConfigDir, ".env"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(content), "\n") {
		line = strings.TrimSpace(line)
		key, value, ok := strings.Cut(line, "=")
		if ok && strings.TrimSpace(key) == "GPU_COMPOSE_SUFFIX" {
			value = strings.TrimSpace(value)
			if len(value) > 0 && (value[0] == '\'' || value[0] == '"') {
				if end := strings.IndexByte(value[1:], value[0]); end >= 0 {
					return value[1 : end+1]
				}
			}
			if index := strings.Index(value, " #"); index >= 0 {
				value = value[:index]
			}
			return strings.TrimSpace(value)
		}
	}
	return ""
}
