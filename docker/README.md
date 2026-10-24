# Docker Services

All the user-facing services in this lab setup are deployed using Docker Containers.

> [Docker](https://www.docker.com/) helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

For additional services to host, check [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted).

## Directory structure

- `docker` -- Docker Compose files organized into categories
- `config/docker` -- Host specific service configuration

## Configuration

In the `config/docker` subfolder multiple Docker hosts can be defined.

Configuration files:
- Common settings: `config/docker/.env`
- Common service settings: `config/docker/.env.<service-name>`
- Host settings: `config/docker/<hostname>/.env`
- Host service settings: `config/docker/<hostname>/.env.<service-name>`
- Configure which services to start (`state: up`) or stop (`state: down`): `config/docker/<hostname>/services.yaml`

The configuration files are not committed to the repository. See [Configure Docker
environment files](../docs/manual-setup.md#configure-environment-files) for their
loading order and back them up separately.

## Services

The applications/services are defined in the `docker` folder, ordered by category.  
If possible, avoid any hardcoded configuration values in these files. Use environment variables and init containers for customization.

For file naming, adding or registering a service, environment-variable precedence,
Traefik labels and network/volume conventions, follow the
[Compose architecture and patterns](guidelines.md).

## Service operations

Run these tasks from the repository root on the intended Docker host. Host-wide
commands use `config/docker/<hostname>/services.yaml`:

| Command | Purpose |
| --- | --- |
| `task docker:apply` | Apply the registered service states |
| `task docker:update` | Pull images before applying configured service states |
| `task docker:pull-all` | Pull images for all registered services, including disabled ones |
| `task docker:stop` | Bring down registered services |
| `task docker:apply-update` | Update services, prune old unused images and show restart events |
| `task docker:update-example-env` | Regenerate example environment/configuration files from the local host configuration |

Updating the container image tags is automated with [Renovate](https://docs.renovatebot.com/).
Check mutable image tags with `task docker:check-updates`.

### Container update safety

The repository's [Renovate configuration](../renovate.json) pins image digests
and disables container automerge. Keep the digest when deploying: a tag alone
can resolve to different content after review.
Hash-only updates are disabled: Renovate adds initial digest pins and updates
digests with version changes, but does not refresh the digest of an unchanged
tag. Digest-pinned floating tags such as `v3` or `stable` therefore stay on their
current content until the tag changes or the digest is updated manually.

- **Docker Hub:** Renovate waits seven days after the tag's last push before
  proposing image updates. Missing timestamps block the update.
  The existing Saturday schedule still applies, so updates may wait longer.
- **GHCR and other registries:** updates are ungrouped and require Dependency
  Dashboard approval before Renovate creates a PR, followed by manual merge.
  Before approving/merging, check the upstream release date, the proposed digest,
  and security advisories; wait at least seven days after publication. This is a
  **manual review policy**, not an automatically enforced cooldown.

Use upstream-published Docker Hub equivalents where available. Registry changes
must preserve image content/platforms, not just similar names or tags. An image
signature or a passing vulnerability scan does not guarantee a release is clean.
For a security emergency, explicitly review any exception to the waiting period.

For a single service, use [`labctl.py`](guidelines.md#managing-individual-services-labctlpy)
rather than applying every configured service. Rendered Compose configuration may
contain credentials; do not print or share it without redaction.

## Tips

### Compose

Convert `docker run` commands to [docker compose](https://docs.docker.com/compose/compose-file/) format:
- [Composerize - Online](https://www.composerize.com/)
- [Composerize - CLI tool](https://github.com/composerize/composerize)

### Container vulnerability scanning and SBOMs

The combined scanner uses **Trivy's native image scan** independently of
**Syft's software inventory (SBOM) scanned by Grype**. Neither replaces the other:
their component discovery and advisory matching have different coverage. Both
pipelines feed one human-readable report.

Install the native CLIs, for example with Homebrew on this host:

```sh
brew install trivy syft grype
```

Python 3.11+ and access to the intended Docker daemon are also required. Verify your
Docker context before scanning. The task honors `DOCKER_HOST` / `DOCKER_CONTEXT`
and explicitly passes the resolved Unix socket to the scanners. SSH/TCP targets
are rejected; run the task directly on that Docker host. State is separated by
daemon identity and socket, not just a possibly reused context name.

```sh
task docker:scan
task docker:scan CONTAINER=adminer
task docker:scan FAIL_ON=CRITICAL
task docker:scan-report
```

The task snapshots **running containers**, including those outside this repository,
and deduplicates by the exact deployed image ID rather than mutable tags. It never
pulls application images, executes commands inside containers, updates services,
restarts containers or deletes Docker data. Native Docker access is privileged;
run only trusted scanner binaries.

Scans run sequentially, with a twenty-minute timeout per scanner stage. A lock
prevents overlapping runs against shared tool databases and the inventory cache.
Each invocation refreshes advisory databases once, then freezes updates during
the scans. Failed refreshes, invalid/missing metadata and databases older than
the policy limit (72 hours by default) make the report incomplete, even if cached
databases allow results to be generated. The freshness limit also applies to
Trivy's Java package index; a missing or stale index is a coverage problem, even
when the vulnerability database is fresh. No tools are automatically installed or
upgraded. Explicit scanner settings prevent hidden scanner configuration or
ignore files from silently removing findings.

Syft native JSON and CycloneDX inventories are cached by image ID, platform,
Syft version and cataloging settings. Go function-symbol capture is enabled.
Cache reuse verifies source image identity, JSON structure and file hashes.
Corrupt entries are preserved under `.invalid-*` names and regenerated, not
silently trusted or deleted. Every invocation still reruns **both vulnerability
matchers**; a cached SBOM is not a cached vulnerability result. Grype consumes
native Syft JSON because interchange formats can lose matching evidence.

Private, Git-ignored artifacts remain under `reports/trivy/` for compatibility:

| Path | Purpose |
| --- | --- |
| `<target>/runs/<UTC-run-id>/summary.md` | Investigate first, coverage problems, changes and stage timings |
| `<target>/runs/<UTC-run-id>/findings.json` / `findings.csv` | All combined findings, versions, scanner severities and triage |
| `<target>/runs/<UTC-run-id>/inventory.json` | Target, exact images, tool/DB versions, stages and coverage status |
| `<target>/runs/<UTC-run-id>/images/` | Native scanner reports, CycloneDX SBOMs and private logs |
| `<target>/state.json` | Last trustworthy baseline for each container |
| `cache/syft/` | Verified inventories reused across runs |

`scan-report` shows the latest **combined** summary for the current Docker target,
including incomplete runs. Older Trivy-only reports and benchmark artifacts are
preserved; they are not silently treated as combined reports. Reports/logs may
contain sensitive image metadata. Keep them private. No reports, history or cache
entries are automatically deleted.
The repository's KICS pre-commit hook explicitly excludes this generated report
directory; infrastructure source files remain in its normal scan scope.

The report merges explicitly linked CVE/GHSA/GO aliases and repeated component
matches while retaining scanner provenance and severity disagreements. Shared
vendor bulletins such as DSA/DLA are **not** treated as vulnerability aliases.
The first page prioritizes known-exploitation flags where available and severe
findings with reported fixes; all other findings remain in JSON/CSV. Kernel-header
matches are marked for applicability review, not automatically suppressed. A
reported fix is not a guarantee that an updated application image is available.

Changes are tracked per container only when both pipelines completed and coverage
is not degraded. Initial baselines are distinguished from newly reported issues.
Missing/failed scans never make old findings disappear. Changes in advisory data
can also cause a finding to be "no longer reported"; that is not proof of a patch.
Scanning one container does not resolve findings for other containers. Corrupt
history is preserved and flagged instead of being reset.

By default, vulnerability findings do not fail the task. `FAIL_ON` is an optional
gate using the highest reported scanner severity after active scoped triage;
it is not an exploitability assessment. The script returns **1** when that gate
fails and **2** for incomplete scans/coverage (which takes precedence). Task may
normalize these exit codes. A zero status is not a declaration that images are safe.

The non-secret policy is [`scan-policy.json`](scan-policy.json). Its expected
components map container names to alternative Syft component names; at least one
must be detected. Adminer requires a PHP interpreter so a detection regression
cannot silently pass. Extend expectations for other important runtimes as their
inventory is validated. Empty inventories, missing images, EOL/unknown distro
warnings and unavailable matching evidence remain explicit coverage problems.

The policy's optional `triage` list supports **exact** `container`, `advisory` and
`component` matches (use the component identifier from `findings.json`). Every
entry also requires `reason`, `evidence` and an ISO `expires` date. Exceptions
remain visible in the full results. Expired exceptions stop applying and flag
the report; no wildcard or blanket baseline suppression is supported.

No finding does **not** prove safety: scanners can miss compiled components and
new advisories, and vendor backports may need manual verification. Image scans
exclude writable layers, bind-mounted applications, the running host kernel and
actual network exploitability. The task does not enable scheduling, notifications,
dashboard uploads or deployment hooks. Run it manually after image updates; any
future daily schedule must be explicitly enabled on the intended host.

### Monitoring tools

Use [ctop](https://github.com/bcicen/ctop) to monitor containers from the command-line.

### Copy a Docker image from local machine to a remote host

Prerequisites:
- SSH access: Set up with `ssh-copy-id user@remotehost`
- Docker group: Both local and remote users must be in the docker group: `sudo usermod -aG docker $USER`

List images:
```sh
docker images
```

Transfer:
```sh
docker save app:1.0 | gzip | DOCKER_HOST=ssh://user@remotehost docker load
```

Replace `user@remotehost` as needed.
This command saves, compresses, transfers, and loads the image directly on the remote host.

Reference: [How to copy Docker images from one host to another without using a repository](https://stackoverflow.com/questions/23935141/how-to-copy-docker-images-from-one-host-to-another-without-using-a-repository)

### Useful Visual Studio Code Extensions

Use the [Docker VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker) easy to build, manage, and deploy containerized applications from Visual Studio Code.

Use the [Remote - SSH VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh) to work on a remote machine.  
Initiate a connection with the "Remote-SSH: Connect to Host" command.  
Read more: [Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh)
