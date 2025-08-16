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
- Look at the subfolders under the `docker` directory (use the `tree -d -L 1 docker/` command) and select an existing category that fits the application. Do not create a new category; use the "tools" category as a fallback if no match is found.
- Use the `uv run --directory scripts/task-mcp tools/find_app_icon.py "<APPLICATION_NAME>" "<APPLICATION_HOMEPAGE>"` command to determine the application's dashboard icon (use the command's output as-is).
- For each container image used in the deployment, get the most specific tag (e.g. tag "1.2.0" is more specific than "1.2") by running `scripts/get-container-tags.py --quiet get-most-specific-tag <IMAGE> --tag <TAG>`. Use the tag returned by this script.

### Part 2 - Organize information

Fill the following template with the gathered information.
THINK HARD to provide the best possible results.
Save the filled template as a file with the filename `docker/<category>/<application>.md`

```markdown
## Base information for <APPLICATION_NAME> application  

Application name: <APPLICATION_NAME>
Homepage: <Main website, if available>
GitHub page: <GitHub page, if available>
Install instructions URL: <INSTALL_INSTRUCTIONS_URL>
Container image(s): <Container image of the service (or multiple images if the application consists of multiple services)>
Category: <Subfolder name under the `docker` directory>
Dashboard Icon: <Dashboard icon determined by find_app_icon.py>
Short description: <Describe the application in one short sentence, suitable to display on the Homepage dashboard>
Long description: <Describe the application in 1–3 sentences. Optimally use the description of the GitHub repo>

## Container deployment

<Put ALL information relevant for container-based deployment: Compose-based example (when found - or at least a docker run command), description of the environment variables, security considerations, possible further improvements. Organize information into sub-sections>

```

### Part 3 - Instructions for implementation

As a final step write to the user:

> To deploy the service run "/implement-container-deployment docker/<category>/<application>.md"
