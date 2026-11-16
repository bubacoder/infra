package labctl

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

func (c *Controller) service(
	ctx context.Context,
	hostConfigDir, category, service, operation string,
	options DockerOptions,
) error {
	composeFile := filepath.Join(c.DockerStacks, category, service, service+".yaml")
	if _, err := os.Stat(composeFile); errors.Is(err, os.ErrNotExist) {
		fmt.Fprintf(c.Err, "Error: Compose file not found: %s\n", composeFile)
		return nil
	} else if err != nil {
		return err
	}

	if operation == "up" || operation == "recreate" {
		if err := c.createServiceNetworks(ctx, composeFile); err != nil {
			return err
		}
	}

	composeFiles := []string{composeFile}
	if suffix := gpuSuffix(hostConfigDir); suffix != "" {
		override := filepath.Join(filepath.Dir(composeFile), service+"-"+suffix+".yaml")
		if _, err := os.Stat(override); err == nil {
			fmt.Fprintf(c.Out, "  GPU override: %s\n", filepath.Base(override))
			composeFiles = append(composeFiles, override)
		} else if !errors.Is(err, os.ErrNotExist) {
			return err
		}
	}

	envArgs := envFileArgs(hostConfigDir, service)
	fileArgs := composeFileArgs(composeFiles)
	baseArgs := append([]string{"compose"}, fileArgs...)
	baseArgs = append(baseArgs, envArgs...)

	switch operation {
	case "pull":
		return c.pull(ctx, composeFiles, envArgs, options.Quiet)
	case "up":
		if options.PullBeforeStart {
			if err := c.pull(ctx, composeFiles, envArgs, options.Quiet); err != nil {
				return err
			}
		}
		fmt.Fprintf(c.Out, ">>> Starting %s/%s\n", category, service)
		return c.docker(ctx, append(baseArgs, "up", "--detach"), nil, false)
	case "down":
		fmt.Fprintf(c.Out, ">>> Stopping %s/%s\n", category, service)
		return c.docker(ctx, append(baseArgs, "down"), nil, false)
	case "restart":
		fmt.Fprintf(c.Out, ">>> Restarting %s/%s\n", category, service)
		return c.docker(ctx, append(baseArgs, "restart"), nil, false)
	case "recreate":
		if options.PullBeforeStart {
			if err := c.pull(ctx, composeFiles, envArgs, options.Quiet); err != nil {
				return err
			}
		}
		fmt.Fprintf(c.Out, ">>> Recreating %s/%s\n", category, service)
		return c.docker(ctx, append(baseArgs, "up", "--detach", "--force-recreate"),
			nil, false)
	case "config":
		fmt.Fprintf(c.Out, ">>> Checking %s/%s\n", category, service)
		return c.docker(ctx, append(baseArgs, "config", "--no-interpolate"), nil, false)
	case "logs":
		fmt.Fprintf(c.Out, ">>> Showing logs for %s/%s\n", category, service)
		logArgs := append([]string{"logs"}, logFlags(options)...)
		return c.docker(ctx, append(baseArgs, logArgs...), nil, false)
	default:
		return fmt.Errorf("unknown operation %q", operation)
	}
}

func (c *Controller) pull(
	ctx context.Context,
	composeFiles, envArgs []string,
	quiet bool,
) error {
	fileArgs := composeFileArgs(composeFiles)
	if hasBuildDirective(composeFiles[0]) {
		fmt.Fprintf(c.Out, ">>> Pulling %s\n", composeFiles[0])
		args := append([]string{"compose"}, fileArgs...)
		args = append(args, envArgs...)
		args = append(args, "build", "--pull")
		if quiet {
			args = append(args, "--quiet")
		}
		return c.docker(ctx, args, map[string]string{"COMPOSE_BAKE": "true"}, false)
	}
	fmt.Fprintf(c.Out, ">>> Pulling %s\n", composeFiles[0])
	args := append([]string{"compose"}, fileArgs...)
	args = append(args, envArgs...)
	args = append(args, "pull")
	if quiet {
		args = append(args, "--quiet")
	}
	return c.docker(ctx, args, nil, false)
}

func (c *Controller) docker(
	ctx context.Context,
	args []string,
	env map[string]string,
	quiet bool,
) error {
	stdout, stderr := c.Out, c.Err
	if quiet {
		stdout, stderr = io.Discard, io.Discard
	}
	return c.Docker.Run(ctx, Invocation{Args: args, Env: env, Stdout: stdout, Stderr: stderr})
}

func composeFileArgs(files []string) []string {
	args := make([]string, 0, len(files)*2)
	for _, file := range files {
		args = append(args, "-f", file)
	}
	return args
}

func logFlags(options DockerOptions) []string {
	var flags []string
	if options.Follow {
		flags = append(flags, "--follow")
	}
	if options.Tail != "" && options.Tail != "all" {
		flags = append(flags, "--tail", options.Tail)
	}
	if options.Since != "" {
		flags = append(flags, "--since", options.Since)
	}
	if options.Timestamps {
		flags = append(flags, "--timestamps")
	}
	return flags
}
