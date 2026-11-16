// labctl manages locally configured Compose stacks.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"

	"github.com/bubacoder/infra/tools/labctl/internal/labctl"
)

func main() {
	os.Exit(run(context.Background(), os.Args[1:], os.Stdout, os.Stderr))
}

func run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	root, err := os.Getwd()
	if err != nil {
		fmt.Fprintln(stderr, "Error:", err)
		return 1
	}
	hostname, err := os.Hostname()
	if err != nil {
		fmt.Fprintln(stderr, "Error:", err)
		return 1
	}
	controller := labctl.New(root, hostname, dockerRunner{}, stdout, stderr)
	if len(args) == 0 {
		usage(stderr)
		return 2
	}

	switch args[0] {
	case "config":
		return runConfig(ctx, controller, args[1:], stderr)
	case "service":
		return runService(ctx, controller, args[1:], stderr)
	case "-h", "--help", "help":
		usage(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "Error: unknown command %q\n", args[0])
		usage(stderr)
		return 2
	}
}

func runConfig(
	ctx context.Context,
	controller *labctl.Controller,
	args []string,
	stderr io.Writer,
) int {
	if len(args) == 0 || args[0] != "apply" {
		fmt.Fprintln(stderr, "Error: expected config apply")
		return 2
	}
	flags := flag.NewFlagSet("labctl config apply", flag.ContinueOnError)
	flags.SetOutput(stderr)
	var config, mode string
	var options labctl.DockerOptions
	flags.StringVar(&config, "config", "", "path to services configuration")
	flags.StringVar(&config, "c", "", "alias for --config")
	flags.StringVar(&mode, "mode", "", "override operation for every service")
	flags.StringVar(&mode, "m", "", "alias for --mode")
	flags.BoolVar(&options.PullBeforeStart, "pull-before-start", false,
		"pull images before starting services")
	flags.BoolVar(&options.Quiet, "quiet", false, "use quiet mode for image pulls")
	if err := flags.Parse(args[1:]); err != nil || flags.NArg() != 0 {
		return 2
	}
	if err := controller.ApplyConfig(ctx, config, mode, options); err != nil {
		fmt.Fprintln(stderr, "Error:", err)
		return 1
	}
	return 0
}

func runService(
	ctx context.Context,
	controller *labctl.Controller,
	args []string,
	stderr io.Writer,
) int {
	if len(args) < 2 {
		fmt.Fprintln(stderr, "Error: service requires an operation and category/name")
		return 2
	}
	operation, name := args[0], args[1]
	if !labctl.ValidOperation(operation) {
		fmt.Fprintf(stderr, "Error: unknown operation %q\n", operation)
		return 2
	}
	flags := flag.NewFlagSet("labctl service", flag.ContinueOnError)
	flags.SetOutput(stderr)
	var options labctl.DockerOptions
	flags.BoolVar(&options.PullBeforeStart, "pull-before-start", false,
		"pull images before starting the service")
	flags.BoolVar(&options.Quiet, "quiet", false, "use quiet mode for image pulls")
	flags.BoolVar(&options.Follow, "follow", false, "follow logs")
	flags.BoolVar(&options.Follow, "f", false, "alias for --follow")
	flags.StringVar(&options.Tail, "tail", "all", "number of log lines from the end")
	flags.StringVar(&options.Tail, "n", "all", "alias for --tail")
	flags.StringVar(&options.Since, "since", "", "show logs since a timestamp")
	flags.StringVar(&options.Since, "s", "", "alias for --since")
	flags.BoolVar(&options.Timestamps, "timestamps", false, "show log timestamps")
	flags.BoolVar(&options.Timestamps, "t", false, "alias for --timestamps")
	if err := flags.Parse(args[2:]); err != nil || flags.NArg() != 0 {
		return 2
	}
	if err := controller.Service(ctx, operation, name, options); err != nil {
		fmt.Fprintln(stderr, "Error:", err)
		return 1
	}
	return 0
}

func usage(writer io.Writer) {
	fmt.Fprintln(writer, `Usage:
  labctl config apply [--config FILE] [--mode OPERATION] [--pull-before-start]
  labctl service OPERATION CATEGORY/NAME [options]

Operations: pull, up, down, restart, recreate, config, logs`)
}

type dockerRunner struct{}

func (dockerRunner) Run(ctx context.Context, invocation labctl.Invocation) error {
	docker, err := exec.LookPath("docker")
	if err != nil {
		return errors.New("Docker executable not found on PATH")
	}
	command := exec.CommandContext(ctx, docker, invocation.Args...)
	command.Stdout = invocation.Stdout
	command.Stderr = invocation.Stderr
	if len(invocation.Env) != 0 {
		command.Env = os.Environ()
		for key, value := range invocation.Env {
			command.Env = append(command.Env, key+"="+value)
		}
	}
	if err := command.Run(); err != nil {
		return fmt.Errorf("docker %s: %w", strings.Join(invocation.Args, " "), err)
	}
	return nil
}
