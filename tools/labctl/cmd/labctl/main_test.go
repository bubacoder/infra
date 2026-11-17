package main

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLauncherRootOverridesWorkingDirectory(t *testing.T) {
	root := t.TempDir()
	t.Setenv("LABCTL_ROOT", root)
	var stdout, stderr bytes.Buffer
	code := run(context.Background(), []string{"service", "config", "core/missing"}, &stdout, &stderr)
	if code != 1 || !strings.Contains(stderr.String(), filepath.Join(root, "docker", "core", "missing")) {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}
}

func TestDirectBinaryFallsBackToWorkingDirectory(t *testing.T) {
	t.Setenv("LABCTL_ROOT", "")
	root, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := run(context.Background(), []string{"service", "config", "core/missing"}, &stdout, &stderr)
	if code != 1 || !strings.Contains(stderr.String(), filepath.Join(root, "docker", "core", "missing")) {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}
}
