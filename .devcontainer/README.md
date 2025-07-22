# Dev Containers

> The Visual Studio Code Dev Containers extension lets you use a container as a full-featured development environment. It allows you to open any folder inside (or mounted into) a container and take advantage of Visual Studio Code's full feature set. A devcontainer.json file in your project tells VS Code how to access (or create) a development container with a well-defined tool and runtime stack. This container can be used to run an application or to separate tools, libraries, or runtimes needed for working with a codebase.

Source: [Developing inside a Container](https://code.visualstudio.com/docs/devcontainers/containers)

## Tips and Tricks

[Dev Containers Tips and Tricks](https://code.visualstudio.com/docs/devcontainers/tips-and-tricks)

## Troubleshooting

### "You don't have enough free space in /var/cache/apt/archives/"

Check the Docker Build Cache:
```sh
docker system df
```

If the cache is full, clean it:
```sh
docker builder prune --all
```
