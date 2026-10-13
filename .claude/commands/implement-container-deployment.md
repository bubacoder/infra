---
description: Add a container service from an existing plan using the unified repo-aware workflow
---

# Implement Container Deployment

Compatibility shortcut for `/add-container-service <plan-path>`.

Read `.claude/commands/add-container-service.md` and follow that workflow with
`$ARGUMENTS` as the path to an existing deployment plan/PRP and any optional flags.
If the path is absent or the document does not exist, stop and ask for a valid path.

Use the document as research input, not a required schema. Verify current facts
and repository assumptions, then create and validate files under the unified
workflow's scope and approval rules. This command does not authorize live deployment.

For new work without a plan, suggest `/add-container-service <application-or-url>`.
Do not maintain a second copy of the deployment instructions.
