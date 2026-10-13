---
description: Plan a container service using the unified repo-aware workflow without creating deployment files
---

# Plan Container Deployment

Compatibility shortcut for `/add-container-service --plan-only --save-plan`.

Read `.claude/commands/add-container-service.md` and follow that workflow with
`$ARGUMENTS` as its input and both `--plan-only` and `--save-plan` enabled.
These flags remain enabled even if the input asks to implement or deploy.

Research in repository context and save the concise proposal to
`docs/PRPs/containers/<application>.md`, or a user-specified destination.
Do not create service files, modify registration or host configuration, pull
images, or deploy. Ask before overwriting an existing plan.

Report the saved path and suggest `/add-container-service <actual-plan-path>`
to continue. Do not maintain a separate research template or implementation policy.
