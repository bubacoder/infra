---
description: Deploy a container-based service by creating a Docker Compose file from a PRP
---

# Deploy Docker Compose Service

## Variables

INSTALL_INSTRUCTIONS_FILE: $ARGUMENTS

## Instructions

Deploy a container-based service by creating and configuring a Docker Compose file.
Use the application details and deployment instructions from the file: INSTALL_INSTRUCTIONS_FILE
This file is the PRP produced by `/plan-container-deployment`. Follow closely the architectural
patterns described in the `docker/guidelines.md` file.

### Part 1 - Create the Docker Compose file

- Read the `docker/guidelines.md` file for the architectural patterns you must follow. In particular note the **"Template for New Services"** section — use it as the starting skeleton.
- Read the INSTALL_INSTRUCTIONS_FILE and use its content to create the compose file. **Abort if the file is not specified or does not exist.**
- From the PRP, note the metadata you will need later: `Application name`, `Category`, `Homepage`, `GitHub page`, `Dashboard Icon`, `Dashboard Group`, `Short description`, `Long description`. These are consumed by the header comment and the labels below — do not discard them.
- If the installation instructions contain steps to fetch the Compose setup and/or environment variables from a git repository:
  - Shallow clone that repository to `/tmp/infra/container/<application>/` and look at the referenced compose and `.env` files there.
  - Use the compose and `.env` files without any changes.
  - If there are additional configuration files referenced in the compose file, copy them.
  - Keep the cloned repository.
- For each container image used in the deployment, get the most specific tag (e.g. tag "1.2.0" is more specific than "1.2") by using the `get-most-specific-container-tag` MCP tool. Use the tag(s) returned by the tool in the Compose stack.
- Save the Docker Compose file as `docker/<category>/<application>/<application>.yaml`, where `<category>` is the `Category` from the PRP.
- **Header comment.** Start the file with the comment block from the guidelines template: the `Long description`, then a `Links:` list (Homepage, GitHub/Source, Docs, and any Docker/Compose setup example), then a `TODO:` line.
- **Networking.** Connect the service to the shared external `proxy` network by default. For sensitive services (password managers, backup, VPN, anything holding secrets), use an isolated network instead, per the "Isolated Networks" section of the guidelines — and add a `TODO` reminding the user that Traefik must be joined to that new network (in `docker/security/traefik/traefik.yaml`).
- **Traefik labels.** If the service has a web UI, expose it via Traefik labels (`traefik.enable`, the router `Host(...)` rule, the loadbalancer server port, and the access middleware). Choose the access middleware explicitly and state your choice in the summary:
  - `localaccess@file` — local network only (default)
  - `localaccess-sso@file` — local network + Authelia authentication
  - `publicaccess@file` — reachable externally with CrowdSec protection
- **Homepage dashboard labels.** Add the dashboard labels using the PRP metadata: `homepage.group` = `Dashboard Group`, `homepage.name` = `Application name`, `homepage.icon` = `Dashboard Icon`, `homepage.href` = the service URL, `homepage.description` = `Short description`.
- If the installation guide suggests enhancements (e.g. using an optional external database instead of a built-in one, or enabling SSO), add them as `TODO` lines in the header comment.
- **Environment variables.** Reuse the existing common variables (`TIMEZONE`, `PUID`, `PGID`, `MYDOMAIN`, `DOCKER_VOLUMES`) — they are already defined, do not redefine them. For any *new* variable the service needs, add it with a **placeholder value only (never a real secret)** to the correct `.env` example file, following the precedence in the guidelines:
  - Common, non-secret, same for every host → `config-example/docker/.env`
  - Host-specific values or secrets/API keys → `config-example/docker/myhost/.env` (the usual case for a new service)

#### AMD GPU acceleration (only if the PRP says the app supports it)

If the PRP's research indicates the application supports AMD GPU acceleration (VAAPI for video decode/transcode, or ROCm for compute/inference), create a **separate compose override file** for it following the **"GPU Acceleration Overrides"** section of `docker/guidelines.md` — do not put GPU config in the base compose file. Name it `docker/<category>/<application>/<application>-amdgpu.yaml`, include only the changed fields, and make its header comment record any manual in-app steps the PRP identified.

### Part 2 - Register the service

A compose file alone is **not** deployable — the service must be registered so `labctl.py` / `task docker:apply` discovers it.

- Add the service to `config-example/docker/myhost/services.yaml`. The file's `services:` key holds a list of single-key category blocks (e.g. `- ai:`, `- tools:`, `- media/video:`); find the block matching its `<category>` and append the entry to that block's list. Create a new `- <category>:` block only if one does not already exist. Use:
  ```yaml
  - name: <application>
    state: up
  ```
- Keep the entries within a category grouped together and consistent with the existing formatting.

### Part 3 - Finishing steps

- Run `pre-commit run --files <docker-compose-filename>` and resolve any reported issues.
- Validate the compose file with `scripts/labctl.py service config <category>/<application>` and fix any errors or warnings (this confirms env-var interpolation resolves).
- Pull the container image(s) with `scripts/labctl.py service pull <category>/<application> --quiet` (with a 15 minute timeout) and verify success.
- **If any of these steps still fails after a couple of fix attempts, stop and report the exact error to the user** rather than guessing further or leaving the repo half-changed.
- Finish with a short summary: the file path created, the category/dashboard group used, the access middleware chosen, any new env vars added (and to which file), and any `TODO`s left for the user (e.g. joining Traefik to a new isolated network).
