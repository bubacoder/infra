---
description: Test the first-time installation process end to end and improve documentation and automation based on issues encountered
---

# Test Installation Process

Treat the repository's tracked documentation as the source of truth and test whether it enables a
genuine first-time user to reach a working deployment. Complete the deployment when possible, but
prioritize leaving the documented process clearer, safer, and reproducible.

## Operating Principles

- Work from the administrative host and keep the new-user perspective. Do not silently rely on
  undocumented repository knowledge, pre-existing local state, or remembered commands.
- Follow the documented recommended path when one exists. If several paths are presented without
  guidance, treat that ambiguity as an onboarding defect.
- Make the smallest correct change. Fix clear, low-risk documentation or automation defects as
  soon as they are confirmed, then retry the failed step.
- Do not silently work around a problem. Record the symptom and either fix it or identify the
  decision needed from the user.
- Never search for, infer, guess, expose, or commit credentials. Use the password vault or ignored
  host-specific configuration for credential handoff. Never place secret values in chat or command
  arguments; redact them from logs, examples, documentation, and the final report.
- Do not alter or remove existing infrastructure to resolve naming, addressing, storage, or other
  conflicts. Ask before any destructive or potentially disruptive action.
- Redact secrets and sensitive infrastructure details from logs, examples, documentation, and the
  final report.

## Workflow

### 1. Establish the deployment contract

Inspect the repository only enough to understand its stated prerequisites and installation flow.
Then ask one concise batch of questions for all missing deployment-specific values, including:

- Proxmox target and VM identity
- VM compute, storage, network, and operating-system requirements
- Administrative access method
- Hostnames, domains, DNS, and certificate expectations
- Which services constitute the required core deployment
- Required credentials or external integration values

Do not ask for values already supplied by the user or clearly defined by repository policy. Resolve
non-sensitive facts using read-only inspection. Stop at a missing credential or consequential
choice rather than inventing a value.

Before provisioning, summarize the intended target and scope. Explicitly confirm any action that
could overwrite, delete, expose, or disrupt existing resources.

### 2. Find and assess the starting point

Approach the repository as if freshly cloned from GitHub:

- Identify the most likely first page a new user would read.
- Follow links and commands in the order presented instead of constructing a private shortcut.
- Check whether prerequisites, supported environment, configuration, secrets handling, deployment
  stages, verification, troubleshooting, and rollback expectations are discoverable when needed.
- Record dead ends, circular references, stale commands, hidden assumptions, excessive choice, and
  places where the reader must infer an important value or next action.

If no clear starting point or recommended path exists, treat that as the first defect and improve it
before continuing when the correction is unambiguous.

### 3. Provision the VM

Use the repository's documented provisioning mechanism to create a new VM on Proxmox. Prefer the
documented defaults and automation over ad hoc host commands. Validate that the resulting VM:

- Matches the agreed resource and network settings
- Boots successfully and is reachable through the documented access method
- Has the prerequisites needed by the next stage
- Does not collide with or modify existing resources

Capture failures with the attempted documented step, expected result, actual result, and diagnosed
cause. Do not include secret values.

### 4. Bootstrap the host

Follow the documented path to prepare the repository, its configuration, and the new VM. Verify
prerequisites rather than assuming they were installed. Confirm that examples, generated
configuration, validation commands, and secret-handling instructions agree with the actual
automation. Preserve enough evidence to distinguish an environment problem from a documentation
or automation defect.

Run the repository's relevant validation before moving on. When a documented command fails, find
the root cause before editing anything. After success:

- Verify the host state required for container deployment.
- Re-run the bootstrap to check idempotence only with explicit user approval, unless the
  administrative workstation is known to be disposable. Do not rerun it automatically otherwise.
- Treat unexplained changes or a failed second run as defects to investigate.

### 5. Deploy core services

Determine the core service set from the documentation or ask the user if the repository does not
define it clearly. Deploy it using the documented Docker workflow. Verify more than container
creation:

- Required containers are running and healthy.
- Service dependencies and networks are functional.
- Documented access paths respond as expected.
- Authentication, persistence, DNS, TLS, and external access work when included in scope.
- A repeat deployment is safe and produces no unexplained changes.

Use bounded waits and inspect health or logs when startup is asynchronous. Do not declare success
from a command exit code alone.

### 6. Close each gap

Classify each issue as it is encountered:

- **Clear defect:** A typo, stale command, missing prerequisite, misleading sequence, absent check,
  unsafe default, or automation bug with one low-risk correction. Fix it immediately, run focused
  validation, and repeat the affected onboarding step.
- **Judgment required:** A security tradeoff, architectural choice, compatibility break, broad
  behavior change, destructive migration, or multiple plausible recommended paths. Explain the
  options and impact, ask the user for a decision, and do not conceal the issue with a workaround.
- **Nice to have:** A non-blocking improvement that would make onboarding faster, clearer, safer,
  or easier to diagnose. Add it to a dedicated Markdown improvement backlog in the repository,
  choosing its location from existing documentation conventions. Create the backlog if needed.

Keep the backlog concise and actionable. For each item, include the observed friction, proposed
improvement, expected benefit, and any decision or dependency. Do not mix resolved defects into
the nice-to-have backlog. Explicitly identify and record opportunities to automate manual,
repetitive, error-prone, or undocumented steps, even when they did not cause a deployment failure.

When changing behavior, update its user-facing documentation in the same change. When changing
documentation, execute the documented command or otherwise validate it against the real workflow.

### 7. Verify the final journey

Run repository checks relevant to every modified file. Revisit the complete documented path from a
clean-user perspective and repeat stages where practical. Confirm that the written sequence now
matches the tested sequence and that temporary troubleshooting steps did not become required
installation steps.

Do not destroy the test VM merely to prove repeatability unless the user explicitly approves it.
If a full clean rerun is impractical, state exactly which portions were revalidated and the
remaining risk.

## Completion Report

Report both deliverables separately:

1. **Deployment:** Identify the VM and deployed scope without revealing sensitive details. Summarize
   provisioning, host bootstrap, service health, access verification, and anything incomplete.
2. **Onboarding improvements:** List documentation and automation defects fixed, validation
   performed, decisions still required, identified automation opportunities, and the location of
   the nice-to-have backlog.

For every unresolved blocker, include the failing stage, observed evidence, impact, and exact input
or decision needed from the user. Never describe the deployment as complete while a required
acceptance check remains unverified.
