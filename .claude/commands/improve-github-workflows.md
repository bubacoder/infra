---
description: Analyze GitHub Actions workflows and recommend improvements for speed and efficiency
---

Analyze the GitHub Actions workflows in this repository and provide recommendations for improving pipeline execution speed and efficiency.

**This command only analyzes and reports — do not edit any workflow files.** Show before/after code in the report; leave applying changes to the user.

**Preflight (do this first, abort if it fails):**
This command uses the GitHub CLI (`gh`) for all run data. Verify it is available and authenticated:
```bash
gh --version   # must exist on PATH
gh auth status # must report a logged-in account with repo/actions access
```
If `gh` is not installed or `gh auth status` fails, **stop and tell the user**: report exactly what failed and how to fix it (install `gh`, or run `gh auth login`). Do not attempt `gh auth login` yourself and do not fall back to unauthenticated API calls — without run data this command cannot do its job.

`gh` infers the repository from the git remote; add `-R <owner>/<repo>` only if the wrong repo is picked up.

**Token management:** request only the JSON fields you need (`--json ...`), limit runs to a handful (`--limit 5`), and use `--log-failed` rather than pulling full logs.

Follow these steps:

1. **Discover workflow files**:
   - List all workflow YAML files in `.github/workflows/`
   - Read each workflow file to understand the structure
   - If there are more than 5 workflows, prioritize the most critical ones (CI, deployments) for detailed analysis

2. **Analyze recent workflow executions** (via `gh`):
   - List workflows: `gh workflow list`
   - For each workflow, get recent runs (timing + status):
     `gh run list --workflow <workflow-file-or-name> --limit 5 --json databaseId,status,conclusion,createdAt,updatedAt,event`
   - Focus on the most frequently run workflows first.
   - For 1-2 representative runs, get per-job/step timings:
     `gh run view <run-id> --json jobs` (each job has `startedAt`/`completedAt` and a `steps` array with the same)
   - For failing runs, inspect only the failed logs: `gh run view <run-id> --log-failed`
   - Compute execution times from the `startedAt`/`completedAt` timestamps; look for bottlenecks and patterns across runs.

3. **Examine workflow configuration**:
   - Job dependencies and sequencing
   - Matrix strategies
   - Caching configuration (actions/cache, Docker layer caching, etc.) — note what caching **already exists** so you don't recommend adding caching a job already has
   - Concurrency settings
   - Conditional execution
   - Runner types (ubuntu-latest, self-hosted, etc.)
   - Action versions and usage patterns
   - Artifact handling

4. **Provide specific, actionable recommendations** organized by impact:

   **High Impact**:
   - Jobs that could run in parallel but currently run sequentially
   - Missing or ineffective caching strategies
   - Slow steps that could be optimized or replaced
   - Redundant work across jobs or workflows
   - Opportunities for matrix strategy optimization

   **Medium Impact**:
   - Action version updates that improve performance
   - Conditional job execution to skip unnecessary work
   - Concurrency group optimizations
   - Artifact optimization (size, retention, sharing)
   - Dependencies that could be pre-installed in custom runners

   **Low Impact**:
   - Minor optimizations (cleanup steps, logging verbosity, etc.)
   - Documentation improvements
   - Workflow organization and naming

5. **For each recommendation**:
   - Explain the current behavior and why it's suboptimal
   - Provide the expected improvement (time saved, resource efficiency)
   - Show concrete code examples with before/after comparisons
   - Include relevant workflow file paths and line numbers
   - Cite specific execution data from recent runs when applicable

6. **Prioritize recommendations**:
   - Focus on changes that will have the biggest impact on overall pipeline duration
   - Consider the frequency of workflow execution
   - Balance quick wins vs. long-term improvements

**Analysis Guidelines**:
- Be data-driven: use actual execution times from recent runs
- Use minimal API calls: fetch only 3-5 recent runs per workflow
- Consider both PR workflows and main branch workflows
- Look for patterns across the few runs analyzed
- Account for cold-start vs. warm-cache scenarios
- Consider the tradeoffs between speed and resource costs
- Prioritize quality insights over exhaustive data collection

**Output Format**:
Present findings in a clear, actionable format with:
- Executive summary with key metrics (average run time, slowest jobs, etc.)
- Prioritized list of recommendations with estimated time savings
- Code examples for each recommendation
- Additional considerations (costs, complexity, maintenance)
