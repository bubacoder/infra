package labctl

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

type recordedDocker struct {
	invocations  []Invocation
	inspectError bool
	runError     error
}

func (d *recordedDocker) Run(_ context.Context, invocation Invocation) error {
	d.invocations = append(d.invocations, invocation)
	if d.inspectError && len(invocation.Args) >= 2 &&
		invocation.Args[0] == "network" && invocation.Args[1] == "inspect" {
		return os.ErrNotExist
	}
	if d.runError != nil {
		return d.runError
	}
	return nil
}

func TestServiceUpUsesEnvironmentFilesAndGPUOverride(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "docker", "ai", "ollama", "ollama.yaml"), `
services:
  ollama:
    image: example.invalid/ollama
`)
	writeFile(t, filepath.Join(root, "docker", "ai", "ollama", "ollama-amdgpu.yaml"), `
services:
  ollama:
    devices: ["/dev/dri"]
`)
	hostConfig := filepath.Join(root, "config", "docker", "host")
	writeFile(t, filepath.Join(root, "config", "docker", ".env"), "COMMON=1\n")
	writeFile(t, filepath.Join(hostConfig, ".env"), "GPU_COMPOSE_SUFFIX=amdgpu\n")
	writeFile(t, filepath.Join(root, "config", "docker", ".env.ollama"), "SERVICE=1\n")
	writeFile(t, filepath.Join(hostConfig, ".env.ollama"), "HOST_SERVICE=1\n")

	docker := &recordedDocker{}
	controller := New(root, "host", docker, io.Discard, io.Discard)
	if err := controller.Service(context.Background(), "up", "ai/ollama", DockerOptions{}); err != nil {
		t.Fatal(err)
	}

	want := []string{
		"compose",
		"-f", filepath.Join(root, "docker", "ai", "ollama", "ollama.yaml"),
		"-f", filepath.Join(root, "docker", "ai", "ollama", "ollama-amdgpu.yaml"),
		"--env-file", filepath.Join(root, "config", "docker", ".env"),
		"--env-file", filepath.Join(hostConfig, ".env"),
		"--env-file", filepath.Join(root, "config", "docker", ".env.ollama"),
		"--env-file", filepath.Join(hostConfig, ".env.ollama"),
		"up", "--detach",
	}
	if len(docker.invocations) != 1 {
		t.Fatalf("invocations = %d, want 1", len(docker.invocations))
	}
	if !reflect.DeepEqual(docker.invocations[0].Args, want) {
		t.Errorf("arguments = %#v, want %#v", docker.invocations[0].Args, want)
	}
}

func TestServiceCreatesMissingExternalNetworksBeforeStart(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "docker", "core", "app", "app.yaml"), `
services:
  app:
    image: example.invalid/app
networks:
  named:
    external:
      name: shared-network
  fallback:
    external: true
`)
	docker := &recordedDocker{inspectError: true}
	controller := New(root, "host", docker, io.Discard, io.Discard)
	if err := controller.Service(context.Background(), "up", "core/app", DockerOptions{}); err != nil {
		t.Fatal(err)
	}

	var got [][]string
	for _, invocation := range docker.invocations {
		got = append(got, invocation.Args)
	}
	want := [][]string{
		{"network", "inspect", "fallback"},
		{"network", "create", "--driver", "bridge", "fallback"},
		{"network", "inspect", "shared-network"},
		{"network", "create", "--driver", "bridge", "shared-network"},
		{
			"compose", "-f", filepath.Join(root, "docker", "core", "app", "app.yaml"),
			"up", "--detach",
		},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("invocations = %#v, want %#v", got, want)
	}
}

func TestApplyConfigDefaultsStateAndRespectsOrder(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	hostConfig := filepath.Join(root, "config", "docker", "host")
	writeFile(t, filepath.Join(root, "docker", "first", "one", "one.yaml"), "services: {}\n")
	writeFile(t, filepath.Join(root, "docker", "second", "two", "two.yaml"), "services: {}\n")
	writeFile(t, filepath.Join(hostConfig, "services.yaml"), `
services:
  - first:
      - name: one
  - second:
      - name: two
        state: restart
`)
	docker := &recordedDocker{}
	controller := New(root, "host", docker, io.Discard, io.Discard)
	if err := controller.ApplyConfig(context.Background(), "", "", DockerOptions{}); err != nil {
		t.Fatal(err)
	}

	var got []string
	for _, invocation := range docker.invocations {
		got = append(got, strings.Join(invocation.Args, " "))
	}
	want := []string{
		"compose -f " + filepath.Join(root, "docker", "first", "one", "one.yaml") +
			" up --detach",
		"compose -f " + filepath.Join(root, "docker", "second", "two", "two.yaml") +
			" restart",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("operations = %#v, want %#v", got, want)
	}
}

func TestServiceRejectsPathTraversal(t *testing.T) {
	t.Parallel()
	controller := New(t.TempDir(), "host", &recordedDocker{}, io.Discard, io.Discard)
	err := controller.Service(context.Background(), "up", "core/../app", DockerOptions{})
	if err == nil || !strings.Contains(err.Error(), "invalid path component") {
		t.Fatalf("error = %v, want path validation error", err)
	}
}

func TestServiceOperationsForwardComposeArguments(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name      string
		operation string
		options   DockerOptions
		want      []string
	}{
		{"down", "down", DockerOptions{}, []string{"down"}},
		{"restart", "restart", DockerOptions{}, []string{"restart"}},
		{"recreate", "recreate", DockerOptions{}, []string{"up", "--detach", "--force-recreate"}},
		{"config", "config", DockerOptions{}, []string{"config", "--no-interpolate"}},
		{
			"logs",
			"logs",
			DockerOptions{Follow: true, Tail: "50", Since: "10m", Timestamps: true},
			[]string{"logs", "--follow", "--tail", "50", "--since", "10m", "--timestamps"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()
			root := t.TempDir()
			composeFile := filepath.Join(root, "docker", "core", "app", "app.yaml")
			writeFile(t, composeFile, "services: {}\n")
			docker := &recordedDocker{}
			controller := New(root, "host", docker, io.Discard, io.Discard)

			if err := controller.Service(context.Background(), test.operation, "core/app",
				test.options); err != nil {
				t.Fatal(err)
			}
			if len(docker.invocations) != 1 {
				t.Fatalf("invocations = %d, want 1", len(docker.invocations))
			}
			want := append([]string{"compose", "-f", composeFile}, test.want...)
			if !reflect.DeepEqual(docker.invocations[0].Args, want) {
				t.Errorf("arguments = %#v, want %#v", docker.invocations[0].Args, want)
			}
		})
	}
}

func TestPullBuildUsesBakeAndQuiet(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	composeFile := filepath.Join(root, "docker", "dev", "app", "app.yaml")
	writeFile(t, composeFile, "services:\n  app:\n    build: .\n")
	docker := &recordedDocker{}
	controller := New(root, "host", docker, io.Discard, io.Discard)

	if err := controller.Service(context.Background(), "pull", "dev/app",
		DockerOptions{Quiet: true}); err != nil {
		t.Fatal(err)
	}
	if len(docker.invocations) != 1 {
		t.Fatalf("invocations = %d, want 1", len(docker.invocations))
	}
	invocation := docker.invocations[0]
	want := []string{"compose", "-f", composeFile, "build", "--pull", "--quiet"}
	if !reflect.DeepEqual(invocation.Args, want) {
		t.Errorf("arguments = %#v, want %#v", invocation.Args, want)
	}
	if !reflect.DeepEqual(invocation.Env, map[string]string{"COMPOSE_BAKE": "true"}) {
		t.Errorf("environment = %#v", invocation.Env)
	}
}

func TestApplyConfigSkipsTraversalAndCreatesLocalhostLink(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	hostConfig := filepath.Join(root, "config", "docker", "host")
	writeFile(t, filepath.Join(hostConfig, "services.yaml"), `
services:
  - ../outside:
      - name: app
`)
	var stderr bytes.Buffer
	docker := &recordedDocker{}
	controller := New(root, "host", docker, io.Discard, &stderr)

	if err := controller.ApplyConfig(context.Background(), "", "", DockerOptions{}); err != nil {
		t.Fatal(err)
	}
	if len(docker.invocations) != 0 {
		t.Fatalf("invocations = %#v, want none", docker.invocations)
	}
	if !strings.Contains(stderr.String(), "skipping invalid service entry") {
		t.Errorf("stderr = %q, want validation warning", stderr.String())
	}
	link, err := os.Readlink(filepath.Join(root, "config", "docker", "localhost"))
	if err != nil {
		t.Fatal(err)
	}
	if link != "host/" {
		t.Errorf("localhost link = %q, want host/", link)
	}
}

func TestMalformedNetworkWarningUsesControllerErrorWriter(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	composeFile := filepath.Join(root, "docker", "core", "app", "app.yaml")
	writeFile(t, composeFile, "networks: [\n")
	var stderr bytes.Buffer
	docker := &recordedDocker{}
	controller := New(root, "host", docker, io.Discard, &stderr)

	if err := controller.Service(context.Background(), "up", "core/app", DockerOptions{}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(stderr.String(), "Warning: extract networks") {
		t.Errorf("stderr = %q, want network warning", stderr.String())
	}
	if len(docker.invocations) != 1 {
		t.Fatalf("invocations = %d, want Compose start", len(docker.invocations))
	}
}

func TestDockerFailureStopsOperation(t *testing.T) {
	t.Parallel()
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "docker", "core", "app", "app.yaml"), "services: {}\n")
	controller := New(root, "host", &recordedDocker{runError: errors.New("unavailable")},
		io.Discard, io.Discard)

	if err := controller.Service(context.Background(), "down", "core/app", DockerOptions{}); err == nil {
		t.Fatal("expected Docker error")
	}
}

func writeFile(t *testing.T, filename, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(filename), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filename, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}
