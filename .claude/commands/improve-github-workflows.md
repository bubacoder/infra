---
description: Analyze GitHub Actions workflows and recommend improvements for speed and efficiency
---

Analyze the GitHub Actions workflows in this repository and provide recommendations for improving pipeline execution speed and efficiency.

**IMPORTANT: Token Management**
- Use small batch sizes for all GitHub API calls to avoid exceeding token limits
- Be selective: analyze the most important workflows in detail, others only at a high level
- Get targeted data: use specific API calls for individual runs rather than listing many runs

Follow these steps:

1. **Discover workflow files**:
   - List all workflow YAML files in `.github/workflows/`
   - Read each workflow file to understand the structure
   - If there are more than 5 workflows, prioritize the most critical ones (CI, deployments) for detailed analysis

2. **Analyze recent workflow executions**:
   - Use `mcp__github__list_workflows` to get workflow IDs
   - For each workflow, use `mcp__github__list_workflow_runs` to get recent runs (use parameter: perPage=3)
   - Focus on the most frequently run workflows first
   - Use `mcp__github__get_workflow_run` to get details for 1-2 representative runs per workflow
   - Use `mcp__github__list_workflow_jobs` to examine job execution (use parameter: perPage=10)
   - Use `mcp__github__get_job_logs` with `failed_only: true` to identify common failure patterns
   - Analyze execution times, bottlenecks, and patterns across runs

3. **Examine workflow configuration**:
   - Job dependencies and sequencing
   - Matrix strategies
   - Caching configuration (actions/cache, Docker layer caching, etc.)
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
