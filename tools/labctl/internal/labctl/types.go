// Package labctl implements Docker Compose stack orchestration for labctl.
package labctl

import (
	"context"
	"io"
	"path/filepath"
	"slices"
	"strings"
)

var Operations = []string{
	"pull", "up", "down", "restart", "recreate", "config", "logs",
}

type DockerOptions struct {
	PullBeforeStart bool
	Quiet           bool
	Follow          bool
	Tail            string
	Since           string
	Timestamps      bool
}

type Invocation struct {
	Args   []string
	Env    map[string]string
	Stdout io.Writer
	Stderr io.Writer
}

// Docker runs one docker command. Docker implements this with "docker" as the
// executable and the invocation arguments following it.
type Docker interface {
	Run(context.Context, Invocation) error
}

type Controller struct {
	Root         string
	Hostname     string
	Docker       Docker
	Out          io.Writer
	Err          io.Writer
	DockerStacks string
	DockerConfig string
}

func New(root, hostname string, docker Docker, out, errOut io.Writer) *Controller {
	return &Controller{
		Root:         root,
		Hostname:     strings.ToLower(hostname),
		Docker:       docker,
		Out:          out,
		Err:          errOut,
		DockerStacks: filepath.Join(root, "docker"),
		DockerConfig: filepath.Join(root, "config", "docker"),
	}
}

func ValidOperation(operation string) bool {
	return slices.Contains(Operations, operation)
}
