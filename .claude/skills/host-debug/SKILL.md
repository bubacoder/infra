---
name: host-debug
description: >-
  Diagnose and repair Ubuntu/Kubuntu host and desktop failures. Use for missing
  KDE/GNOME panels, taskbars, docks or application menus; desktop shell crashes
  or freezes; login loops or black screens; display, scaling and multi-monitor
  issues; broken shortcuts, notifications, widgets or extensions; GUI apps
  crashing in shared font/graphics libraries; whole-system freezes, hard lockups,
  unexpected reboots and kernel panics. Covers "host became unresponsive",
  "machine froze around a time", "why did it reboot", and suspected memory,
  GPU, disk, cron or background-service causes on live hosts and after reboot.
---

# Host Debug

Investigate the actual affected host, find the failure chain, and restore the
affected path with the smallest evidence-backed repair. Separate the confirmed
failure mechanism from an unproven underlying trigger. If available, load
`systematic-debugging`; the workflow below remains sufficient without it.

## 1. Establish the target and route the incident

- Confirm hostname, OS/kernel, host versus container/VM, affected user, access
  method, privileges, host clock/timezone, onset, and whether the issue is live
  or recovered. Resolve relative incident times against the host clock.
- Ask only questions that change the next action; continue independent checks
  while waiting. For a freeze, establish whether apps, SSH/TTY, and services
  still worked and how recovery happened. Ping proves reachability, not healthy
  userspace. Do not assume the agent's shell is the affected desktop session.
- Select the branch below and **read its reference before branch-specific
  diagnostics or repairs**. Run only sections supported by symptoms/evidence.

| Symptom or evidence | Route |
| --- | --- |
| Missing panel/menu, GUI app failure, desktop-only hang, login or display issue | [desktop.md](references/desktop.md): identify the actual session/protocol, then inspect the affected component |
| Whole-host freeze, unexpected reboot, panic, kernel/storage stall | [crash.md](references/crash.md): select the incident boot and check journal plus pstore early |
| Ambiguous "machine froze" | Use lightweight live-freeze triage in [crash.md](references/crash.md); if only the desktop failed, continue in [desktop.md](references/desktop.md) |
| Desktop failure preceded by kernel/storage errors | Follow the earlier host failure in [crash.md](references/crash.md); desktop symptoms may be consequences |
| A specific container service is implicated | Load `debug-container-service` and use the repo's infra tools for that branch; retain relevant host evidence |

For a recovered/rebooted ambiguous freeze, use the crash branch's incident-boot
evidence instead of treating current process/resource state as historical proof.
Do not run full crash diagnostics for a missing panel without host-failure evidence.

## 2. Capture evidence before changing state

- Use scoped, bounded logs with the correct boot, incident time window, component,
  and user/session. Include informational events when reconstructing a timeline;
  extend the window only for recurrence or comparison with a working period.
- Inspect process/unit state, relevant configuration read-only, and applicable
  crash records. Follow the earliest supported failure, not merely the last error.
  Extract meaningful fault frames below signal/crash-reporting handlers.
- Preserve decisive logs and relevant state before recovery. Use a small private
  evidence bundle if needed. Avoid clipboard history, credentials, unrelated home
  files, and full process environments; extract only needed session variables.
- Check tool availability and installed help/man pages. Prefer dedicated file
  tools. Do not install packages or execute scheduled jobs/heavy scans merely to
  diagnose. Record access failures and unavailable evidence explicitly.
- Keep independent checks independent: a failed version query or missing tool
  must not suppress other diagnostics through an `&&` chain. Handle failures
  explicitly; chain only operations whose prerequisites must succeed.
- Bound potentially blocking D-Bus/display probes with an external `timeout`,
  even when the tool has its own timeout option. Run them separately from
  other evidence collection so a hung probe cannot suppress later checks.

## 3. Form and test one evidence-backed hypothesis

- Before recommending a version-sensitive setting, check installed versions and
  current upstream/distribution documentation for the affected component and
  protocol. Generic man-page advice may not apply to the active backend.
  Follow repository documentation-tool requirements.
- State the suspected mechanism and supporting evidence briefly before changing
  a variable. Compare with prior working periods or another affected application
  when useful. Schedule coincidence or a process in a stack is not causation.
- Distinguish failure mechanism, suspected trigger, and downstream consequences.
  A restart limit is a consequence of repeated crashes; a final panic may follow
  earlier storage loss. Clean post-reboot health counters do not erase prior faults.
- If evidence is insufficient, report uncertainty and the smallest useful next
  capture/check rather than guessing. For diagnosis-only requests, stop after
  findings and recommendations; for repair requests, carry out supported repairs.

## 4. Repair with minimal disruption

- Make one targeted, reversible change. Preserve user customization: before
  persistent edits, back up the exact file/settings with a timestamp and record
  the reversal procedure. Avoid blanket resets, upgrades, or reinstallations.
- Use the selected reference's recovery procedure. Run user services and D-Bus
  operations as the affected user on the correct session bus; never launch a
  desktop shell as root or guess a display/socket.
- Obtain explicit confirmation before ending a graphical session, restarting its
  compositor/display manager, logging out, rebooting, resetting a controller,
  changing boot parameters, updating firmware, or starting a heavy scan/self-test.
  Explain the relevant loss-of-work or disruption risk. Never repair a mounted
  root filesystem destructively or deliberately reproduce a whole-host crash.
- If the hypothesis fails, collect new evidence and undo unsuccessful temporary
  workarounds before another change. After three failed fixes, pause and reassess
  with the user rather than stacking speculative changes.

## 5. Verify and report

- Verify service/process stability and incident-scoped logs after recovery settles,
  then test the original affected path. Use the branch's success criteria; a live
  process, successful reboot, or clean SMART result alone is not proof of a fix.
- Distinguish successful recovery from recurrence prevention. Verify over the
  prior failure interval when practical; report next-login or longer-term checks
  as pending instead of forcing a disruptive test.
- For visible desktop symptoms, obtain permitted UI evidence or user confirmation.
  Do not mark visual verification complete based only on service health.
- Stop once the requested issue is resolved and applicable verification is done.

Provide a concise final report: host/session/protocol and relevant incident time,
confirmed failure chain with decisive evidence, remaining trigger uncertainty,
exact repair and persistent changes with backup/undo, checks passed and pending,
and a useful recurrence/recovery step if needed. Include checked scheduling/resource
hypotheses only when relevant. Keep raw logs and routine command narration out.
