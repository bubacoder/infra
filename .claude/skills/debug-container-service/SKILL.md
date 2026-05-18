---
name: debug-container-service
description: >
  Debug, troubleshoot, and fix container-based services (Docker, Podman) configured in this
  homelab infrastructure repo. Use when a service is broken, crashing, returning errors, or
  behaving unexpectedly. Triggers on: "X is not working", "X gives an error", "debug service X",
  "fix container X", "troubleshoot X", service crashes, 500/400 errors from a running service,
  unexpected behavior after an update, config changes that broke something. Also use when asked
  to investigate why a service stopped or started failing.
---

# Container Service Debugging

Work through the steps below in order. **Stop as soon as the problem is resolved** — do not continue to further steps unnecessarily.

## Before You Begin

Make sure you have:
- The error message or symptom (ask the user if not provided)
- The service name (`category/service-name` format, e.g. `ai/open-webui`, `security/traefik`)

If the user mentions an error message but not the service, ask. If the service is obvious from context, proceed.

---

## Step 1 — Get Compose Config and Identify Services

Use the MCP tool to read the resolved compose configuration:

```
mcp__infra-mcp__container-service-config(service_name="category/service-name")
```

From the config, identify:
- **Container name** (needed for `docker logs`)
- **Volumes** (paths to check for file-based logs)
- **Environment variables** (may reveal misconfiguration)
- **Dependent / indirect services** — does this service connect to a database, reverse proxy (Traefik), auth provider (Authelia), or another API? Those may also need investigation.

---

## Step 2 — Check Docker Logs (Always Do This First)

**Never make config changes before reading the actual logs.** The log output reveals:
- The exact error message and exception type
- The file and line number where the error occurs — this identifies which code path is failing, which determines which fix applies
- Whether the problem is in this service or in a dependency it's calling

```bash
docker logs <container_name> --tail 100 2>&1
```

Filter for the signal:
```bash
docker logs <container_name> --tail 200 2>&1 | grep -i "error\|exception\|warn\|fail\|traceback"
```

Or use the labctl wrapper (see [repo-specifics.md](references/repo-specifics.md)):
```bash
scripts/labctl.py service logs category/service-name --tail 200
```

**Key insight from logs:** Pay attention to the source location (e.g. `module.file:function:line`). An error in `process_chat` vs `images_endpoint` are different code paths that may require completely different fixes, even if the symptom looks the same.

If dependent services are suspected, check their logs too.

---

## Step 3 — Check File-Based Logs

Some services write additional structured logs to their data volume. Check:

1. Get the volume path from the compose config (Step 1) — typically `${DOCKER_VOLUMES}/<service>/`
2. Look for log files:
   ```bash
   find /mnt/local/storage/docker-volumes/<service> -name "*.log" -type f | head -20
   find /mnt/local/storage/docker-volumes/<service> -path "*/logs/*" -type f | head -20
   ```
3. Read recent entries of any log files found.

---

## Step 4 — Search Documentation

Use Context7 to search the service's official documentation for the specific error or feature:

```
mcp__context7__resolve-library-id(libraryName="<Service Name>", query="<error or feature>")
mcp__context7__query-docs(libraryId="...", query="<specific error message or config option>")
```

**Critical rule:** Before adding any environment variable or config option to a service YAML, **verify the exact name exists in the source code or official docs**. Do not guess or derive variable names from patterns — look them up.

Use the GitHub API to read the actual source for the version in use:
```bash
gh api repos/<org>/<repo>/contents/<path>?ref=<version-tag> --jq '.content' | base64 -d | grep -i "<variable>"
```

For example, to check if an env var exists in `config.py` for Open WebUI v0.9.5:
```bash
gh api repos/open-webui/open-webui/contents/backend/open_webui/config.py?ref=v0.9.5 \
  --jq '.content' | base64 -d | grep -i "VARIABLE_NAME"
```

---

## Step 5 — Search GitHub Issues

If the error message is specific (a stack trace fragment, a quoted error string, an unusual behavior), search the project's issue tracker early. Many errors in popular open-source services are already documented with working fixes.

```bash
gh issue list -R <org>/<repo> --search "<key error words>" --state all --limit 10
```

Read the comments on relevant issues — the fix is often in the comments, not the issue body. Look for:
- Confirmed fixes (env vars, config changes)
- Workarounds
- Which version introduced or fixed the problem

```bash
gh issue view <number> -R <org>/<repo> --comments
```

---

## Step 6 — Check Version / Release Notes

If the issue appeared after an update, or if a fix exists in a newer version:

```bash
# List available image tags
mcp__infra-mcp__list-container-tags(image="<registry/image>")

# Browse recent release notes
gh api repos/<org>/<repo>/releases --jq '.[0:5] | .[] | {tag: .tag_name, body: .body[:400]}'
```

**Upgrading:** If a newer version contains the fix, update the image tag in the service YAML file (`docker/category/service/service.yaml`) and recreate the container.

**Downgrading:** If a recent update introduced the regression, note the last known-good version and offer to roll back.

---

## Step 7 — Source Code Inspection and Patch (Last Resort)

Only reach this step after Steps 1–6 have not resolved the issue.

**Before making any change:** Explain to the user exactly what you intend to change in the source, why it fixes the issue, and what the trade-offs are. Ask for confirmation.

Read the relevant source for the exact deployed version:
```bash
gh api repos/<org>/<repo>/contents/<path>?ref=<version-tag> --jq '.content' | base64 -d
```

Choose the least invasive fix, in this order:

1. **Environment variable or config change** — no files to mount, most maintainable
2. **Mount a patched file via Docker volume** — add a bind mount in the service YAML pointing to a patched copy stored in the repo (e.g. `./patched_file.py:/app/path/file.py:ro`); document clearly why it exists
3. **Custom Docker image** — only if a volume mount is not feasible; significantly increases maintenance burden

**Always revert wrong fixes before applying the correct one.** Accumulating incorrect changes obscures the actual state and makes future debugging harder.

After applying any fix, recreate the container to pick up changes:
```bash
scripts/labctl.py service recreate category/service-name
# or
mcp__infra-mcp__container-service-recreate(service_name="category/service-name")
```

Then re-check the logs (Step 2) to confirm the fix worked.

---

## Repo-Specific Details

See [references/repo-specifics.md](references/repo-specifics.md) for:
- Service name format and file locations
- Volume path conventions
- Available MCP tools and labctl commands
- Environment variable loading order
- How to read source code of deployed versions
