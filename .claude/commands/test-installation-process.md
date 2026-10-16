---
description: Test the first-time installation process end to end and improve documentation and automation based on issues encountered
---

# Test Installation Process

Test whether a first-time user can reach a working deployment using the repository's tracked
documentation. Discover the supported targets, installation stages, commands, and acceptance checks
from those documents rather than assuming a provider or carrying a separate installation recipe here.

## Operating Principles

- Start from a fresh-user perspective. Do not rely on remembered commands, undocumented repository
  knowledge, or existing local setup to fill gaps silently.
- Use only explicitly supplied credentials or approved private configuration. Do not hunt for or
  guess secrets. Arrange private handoff and never expose secret values in chat, command arguments,
  logs, documentation, or commits. Redact sensitive infrastructure details from shared evidence.
- Preserve existing infrastructure, configuration, deployment state, and unrelated worktree changes.
  Do not bypass safety checks or silently work around conflicts.
- Obtain approval before destructive or disruptive actions, additional provisioning, repeat runs,
  or teardown outside the agreed test scope. Do not commit or push without explicit approval.

## Workflow

### 1. Discover the documented journey

Start at `README.md` and follow its installation links as a new user would. Read repository guidance
and the selected target's linked documentation. Discover prerequisites, configuration, access and
credential requirements, supported deployment scope, verification, recovery, and cleanup expectations.

Use the target and scope supplied by the user. If either is unclear, ask rather than silently choosing
a provider. Follow that target's recommended path; do not combine unrelated installation methods or
invent stages. Treat missing guidance, contradictory instructions, and unclear choices as onboarding
defects. Consult implementation code to diagnose or verify a documented step, not to conceal a gap.

### 2. Agree on the test scope

Resolve non-sensitive facts through read-only inspection. Ask one concise batch of questions for
missing inputs and consequential choices identified by the documentation. Do not ask again for values
already supplied or defined by repository policy. Stop at unavailable credentials or prerequisites;
explain what is needed rather than guessing.

Before changing infrastructure, confirm the selected environment, intended changes, acceptance
criteria, and test boundaries, including any billable resources and their cleanup expectations.
Make clear that failures can leave resources running and incurring charges.

### 3. Execute and verify

Follow the documented sequence and commands, including its validation and operator checkpoints.
Verify prerequisites instead of assuming the administrative environment is ready. Do not substitute
manual steps for documented automation without recording the defect and obtaining any needed approval.

For each stage, record the documented instruction, expected outcome, observed result, and verification
evidence without secrets. Use bounded waits for asynchronous work. Check observable functionality and
persistence appropriate to the documented scope, not just command exit codes or resource creation.

When a step fails, diagnose the cause before editing or retrying. Distinguish an environment problem
from a documentation or automation defect. Stop when blocked or when retries provide no new evidence;
report the required input or decision instead of bypassing a check.

### 4. Close gaps and revalidate

- **Clear, low-risk defect:** Apply the smallest correct documentation or automation fix, run focused
  checks, and retry the affected step within the approved scope.
- **Judgment required:** Explain security, architectural, compatibility, or disruptive tradeoffs and
  ask for a decision before changing behavior.
- **Non-blocking improvement:** Record friction and automation opportunities in a concise Markdown
  backlog using the repository's documentation conventions. Include the proposed improvement,
  benefit, and dependencies; keep resolved defects separate.

Keep user-facing documentation aligned with behavior changes. Validate documented instructions
against the real workflow and run repository checks relevant to every modified file.

Revisit the journey from a clean-user perspective. Perform repeatability checks only within the
approved scope; never destroy resources just to prove repeatability. Identify temporary workarounds,
remove only approved test artifacts, and state which stages could not be revalidated.

## Completion Report

Report separately:

1. **Installation:** Selected target, documentation followed, tested scope, verification evidence,
   untested stages, and remaining resources or charges. Do not claim success while a required check
   is unverified.
2. **Onboarding improvements:** Defects fixed, checks run, outstanding decisions, automation
   opportunities, and backlog location if one was needed.

For each blocker, include the failing instruction, observed evidence, impact, and exact input or
decision needed to continue. State whether cleanup was approved and completed or remains outstanding.
