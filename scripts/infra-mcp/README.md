# Infra MCP Server

This is an MCP server implementation using the FastMCP library that dynamically creates tools from your taskfile tasks.

## Features

- Dynamically generates FastMCP tools from the output of `task --list-all`
- Each task becomes a callable tool in the MCP server
- Uses UV for dependency management

## FastMCP overview

[FastMCP - Get Started](https://gofastmcp.com/getting-started/welcome)

> The Model Context Protocol (MCP) is a new, standardized way to provide context and tools to your LLMs, and FastMCP makes building MCP servers and clients simple and intuitive. Create tools, expose resources, define prompts, and more with clean, Pythonic code

## Installation

1. Make sure [UV](https://docs.astral.sh/uv/) is installed (Install: `pipx install uv`, Setup environment: `uv init`)
2. Setup a virtual environment and install dependencies:

```bash
cd scripts/infra-mcp
uv venv
uv sync # or: uv pip install -r requirements.txt
```

Note additional packages can be installed with:
```bash
uv add <package>
```

## Usage

Run the MCP server with the following commands.
The server will start and dynamically create tools from all available tasks in your taskfile.

```bash
source .venv/bin/activate
python server.py
```

or

```bash
uv run server.py
```

or (recommended)

```bash
fastmcp run server.py
fastmcp run server.py --transport http --host 127.0.0.1 --port 8000
```

Test with [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector):

```bash
npx @modelcontextprotocol/inspector
```

## How it works

1. The server runs `task --list-all` to get all available tasks
2. It parses the output to extract task names and descriptions
3. For each task, it creates a FastMCP tool that executes `task <task_name>`
4. All tools are added to the MCP server
5. When a tool is called, it executes the corresponding task and returns the output

## Development

To add new dependencies:

```bash
uv pip add <package-name>
uv pip freeze > requirements.txt
```
