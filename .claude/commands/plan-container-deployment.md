# Prepare deployment of Docker Compose Service

## Variables

APPLICATION_NAME: $ARGUMENTS
INSTALL_INSTRUCTIONS_URL: $ARGUMENTS

## Instructions

Your task is to collect all necessary know-how for deploying a containerized application using Docker Compose.

### Part 1 - Gather information

- Visit the installation instructions page for APPLICATION_NAME at INSTALL_INSTRUCTIONS_URL and search for Docker Compose deployment examples. If none are found, fall back to plain Docker examples. Gather all information relevant to container deployment.
- ABORT your work if no container-based installation method is found.
- Starting from the installation page, find the application's main homepage and its GitHub repository page (if available).
- For each container image used in the deployment, get the most specific tag (e.g. tag "1.2.0" is more specific than "1.2") by using the `get-most-specific-container-tag` MCP tool. Use the tag returned by the tool.
- Use the `get-container-categories` MCP tool to list subfolders under the `docker` directory and select an existing category (folder) that fits the application. Do not create a new category; use the "tools" category as a fallback if no good match is found.
- Use the `get-dashboard-groups` MCP tool to list the available dashboard groups. Select the best matching. Do not create a new group; use the "Tools" group as a fallback if no good match is found.  
- Use the `get-app-icon` MCP tool to determine the application's dashboard icon (use the tool output as-is).

### Part 2 - Organize information

Do not save the Docker Compose stack as a separate yaml file yet, only create a markdown document.
Fill the following template with the gathered information. THINK HARD to provide the best possible results.
Save the filled template as a file with the filename `docs/PRPs/containers/<application>.md`

```markdown
## Base information for <APPLICATION_NAME> application  

Application name: <APPLICATION_NAME>
Homepage: <Main website, if available>
GitHub page: <GitHub page, if available>
Install instructions URL: <INSTALL_INSTRUCTIONS_URL>
Container image(s): <Container image of the service (or multiple images if the application consists of multiple services)>
Category: <Subfolder name under the `docker` directory>
Dashboard Icon: <Dashboard icon determined by `get-app-icon`>
Dashboard Group: <Dashboard group, the best matching value returned by `get-dashboard-groups`>
Short description: <Describe the application in one short sentence, suitable to display on the Homepage dashboard>
Long description: <Describe the application in 1–3 sentences. Optimally use the description of the GitHub repo>

## Container deployment

<Put ALL information relevant for container-based deployment: Compose-based example (when found - or at least a docker run command), description of the environment variables, security considerations, possible further improvements. Organize information into sub-sections>

```

### Part 3 - Instructions for implementation

As a final step write to the user:

> To deploy the service run "/implement-container-deployment docs/PRPs/containers/<application>.md"
