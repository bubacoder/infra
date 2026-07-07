---
description: Collect installation details and generate a PRP for container deployment
---

# Prepare deployment of Docker Compose Service

## Variables

$ARGUMENTS contains both of the following; split it as described:
- INSTALL_INSTRUCTIONS_URL: the token that looks like a URL (starts with `http`).
- APPLICATION_NAME: the remaining text. If only a URL was given, derive the name from the URL / the page's title once fetched.

If `$ARGUMENTS` is empty or no URL can be identified, ask the user for the application name and the installation-instructions URL before continuing.

## Instructions

Your task is to collect all necessary know-how for deploying a containerized application using Docker Compose.

**First, check the application is not already deployed:** use the `get-container-categories` MCP tool and/or run `find docker -iname '*<application>*'`. If a matching service already exists, stop and tell the user rather than producing a duplicate PRP.

### Part 1 - Look for installation details

Visit the installation instructions page for APPLICATION_NAME at INSTALL_INSTRUCTIONS_URL and search for Docker Compose deployment examples in this priority order:

1. Docker Compose setup located in the git repository (if the install instructions refer to cloning a repo)
2. Docker Compose setup described on the installation instructions page
3. Plain docker setup (`docker run ...`)

Gather all information relevant to container deployment.
Also research whether the application supports **AMD GPU acceleration** — e.g. VAAPI for video decode/transcode or ROCm for compute/inference. Note the type of acceleration, whether the vendor ships a GPU-specific image tag, and any manual in-app configuration it requires. Record findings only; do not design the compose files here (that is done in the implementation step).
ABORT your work if no container-based installation method is found.

### Part 2 - Gather application metadata

- Starting from the installation page, find the application's main homepage and its GitHub repository page (if available).
- Use the `get-container-categories` MCP tool to list subfolders under the `docker` directory and select an existing category (folder) that fits the application. Do not create a new category; use the "tools" category as a fallback if no good match is found.
- Use the `get-dashboard-groups` MCP tool to list the available dashboard groups. Select the best matching. Do not create a new group; use the "Tools" group as a fallback if no good match is found.  
- Use the `get-app-icon` MCP tool to determine the application's dashboard icon (use the tool output as-is).

### Part 3 - Organize information

Do not save the Docker Compose stack as a separate yaml file yet, only create a Markdown document. If the Compose stack uses additional configuration files, include them.
Fill the following template with the gathered information. THINK HARD to provide the best possible results.
Save the filled template as a file with the filename `docs/PRPs/containers/<application>.md`

```markdown
## Base information for <APPLICATION_NAME> application  

Application name: <APPLICATION_NAME>
Homepage: <Main website, if available>
GitHub page: <GitHub page, if available>
Install instructions URL: <INSTALL_INSTRUCTIONS_URL>
Category: <Subfolder name under the `docker` directory>
Dashboard Icon: <Dashboard icon determined by `get-app-icon`>
Dashboard Group: <Dashboard group, the best matching value returned by `get-dashboard-groups`>
Short description: <Describe the application in one short sentence, suitable to display on the Homepage dashboard>
Long description: <Describe the application in 1–3 sentences. Optimally use the description of the GitHub repo>

## Container deployment

<Put ALL information relevant for container-based deployment: Compose-based example (when found - or at least a docker run command), description of the environment variables, security considerations, AMD GPU acceleration support (type, GPU-specific image tag, manual in-app steps - or state "none"), possible further improvements. Organize information into sub-sections>

```

### Part 4 - Instructions for implementation

As a final step write to the user:

> To deploy the service run "/implement-container-deployment docs/PRPs/containers/<application>.md"
