# Desktop diagnostic branches

## Contents

- [Desktop workflow](#desktop-workflow)
- [Session and bounded evidence](#session-and-bounded-evidence)
- [KDE Plasma](#kde-plasma-missing-panelmenu-or-crashed-shell)
- [GNOME](#gnome-shell-dock-extensions-and-notifications)
- [Shared font-rendering crashes](#shared-font-rendering-crashes)
- [Displays and login failures](#displays-scaling-black-screens-and-login-loops)

Use commands selectively, replacing placeholders with discovered values.
Run user commands as the affected user. Check command availability and installed
help; unit names and D-Bus interfaces vary by desktop release.

## Desktop workflow

### Identify the affected session

- Inspect `loginctl list-sessions` and `loginctl show-session SESSION_ID`.
  Identify the session by user, seat, type, state and leader; distinguish local,
  remote and nested desktops from the agent's SSH/TTY shell.
- Inspect `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`, `DISPLAY`,
  `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` as clues,
  then confirm against session/process data. A nonempty `DISPLAY` under Wayland
  usually means Xwayland, not an X11 session.
- Detect the actual shell/compositor and installed version rather than inferring
  them from the distribution name. Run user-service and D-Bus commands on the
  affected user's bus. For SSH/TTY access, establish the runtime directory and
  bus first. Never invent a display/socket or run the desktop shell as root.
- With multiple graphical sessions for the same UID, verify process ownership
  and relevant session variables: the user systemd manager/bus may be shared.
  If `/proc/PID/environ` is inaccessible, use session metadata and the user
  manager's relevant variables as corroborating clues; do not dump its full environment.

### Identify the failure before recovery

- Record login/onset time, intermittency, affected monitors, recent updates or
  configuration changes, and whether other applications fail.
- Separate a missing/crashed shell from a healthy but hidden/off-screen panel,
  unresponsive shell, extension failure, or disconnected output assignment.
- Inspect relevant configuration read-only: verify expected panels, launchers,
  widgets/extensions still exist. Compare fault frames across apps; shared
  Fontconfig/Qt/Mesa frames suggest shared state/library trouble.
- Check disk space, memory/swap, OOM, GPU/DRM errors, and package versions when
  evidence warrants it. For preceding host-level faults, follow the core routing
  table and read [crash.md](crash.md).

| Evidence | Next action |
| --- | --- |
| Shell absent, unit failed | Inspect the crash and trigger first; recover only the shell if the desktop supports it |
| Shell running but unresponsive | Use a bounded D-Bus Ping on the verified session bus; capture logs and panel/output state, then restart only plasmashell if the hang is confirmed |
| Shell healthy, panel hidden/off-screen | Inspect visibility, output assignment and geometry; correct the specific setting |
| Implicated widget/extension stack or reproducible trigger | Back up its configuration; disable only that widget/extension and retest |
| Shared font crashes and abnormal matches | Compare cached matching with direct font scanning before rebuilding the relevant cache |
| GPU reset, DRM failures or compositor crash | Inspect driver/kernel/update consistency and output state |
| Login loop or session exits | Inspect display-manager/session logs, disk space, ownership and startup hooks |

### Preserve layout and verify the visible result

- Back up the exact affected settings before persistent edits. For GNOME, dump
  only the affected dconf subtree. Do not start with deleting `~/.config`,
  resetting layouts, disabling all extensions, removing fonts, switching display
  protocols, reinstalling the desktop, or blanket upgrades.
- Inspect existing restart policy. A start-limit failure after crashes is a
  consequence; do not hide it with unlimited restarts or a watchdog.
- Distinguish recovery from prevention: a shell restart need not explain a crash;
  a successful cache rebuild need not identify what originally generated bad state.
- After startup settles, check PID, service state, D-Bus responsiveness, logs and
  stable restart counts. Observe longer than the previous crash interval.
- Verify the original failure path: menu activation, panel on the correct output,
  text rendering, shortcut or application launch. Obtain permitted UI evidence
  or user confirmation; process health alone does not prove a visible panel.
- For intermittent login issues, arrange a check at the next normal login rather
  than forcing logout. Report any visual/next-login verification still pending.

## Session and bounded evidence

```bash
hostname
loginctl list-sessions
loginctl show-session SESSION_ID -p Name -p User -p Type -p Desktop -p State -p Active -p Seat -p Leader
pgrep -a -x plasmashell
pgrep -a -x kwin_wayland
pgrep -a -x kwin_x11
pgrep -a -x gnome-shell
systemctl --user --failed --no-pager
journalctl --user -b --since 'INCIDENT_START' --until 'INCIDENT_END' --no-pager -n 120
coredumpctl list --since 'INCIDENT_START' --until 'INCIDENT_END' --no-pager
df -h / /home /tmp
free -h
journalctl -k -b --since 'INCIDENT_START' --no-pager -g 'oom|Out of memory|Killed process|drm|GPU|reset|hang' -n 100
```

Read `/etc/os-release` with a file reader. Inspect installed package versions
with `dpkg-query -W` and candidates with `apt-cache policy` for implicated
packages only. Avoid refreshing/upgrading packages merely to diagnose.

Qt applications may initialize a display backend even for `--version`. From a
TTY without a confirmed graphical environment, prefer package metadata. If a
version invocation is necessary, `QT_QPA_PLATFORM=offscreen plasmashell --version`
avoids connecting to a display; do not mistake a TTY display-plugin failure for
the graphical session's original crash. Keep unrelated checks running if it fails.

For a relevant crash, query `coredumpctl info PID --no-pager`. It may contain
hundreds of module/thread records: use a content filter or bounded saved-output
reader to examine metadata and the faulting thread. Use a debugger only if
the summary cannot identify the failure path and core access is available.

## KDE Plasma: missing panel/menu or crashed shell

```bash
dpkg-query -W plasma-workspace
systemctl --user status plasma-plasmashell.service --no-pager
systemctl --user cat plasma-plasmashell.service
journalctl --user -b -u plasma-plasmashell.service --since 'INCIDENT_START' --no-pager -n 100
busctl --user status org.kde.plasmashell
```

Inspect `~/.config/plasma-org.kde.plasma.desktop-appletsrc` and
`~/.config/plasmashellrc` with file tools. Look for `org.kde.panel`, launcher
plugins such as `org.kde.plasma.kickoff`, task managers, tray containment,
visibility/geometry and screen assignments. Compare with current outputs;
`lastScreen` alone is not a reliable physical connector mapping.

After correcting the crash trigger, recover a systemd-managed shell with:

```bash
systemctl --user reset-failed plasma-plasmashell.service
systemctl --user start plasma-plasmashell.service
```

Use `restart` instead of `start` only if replacing an existing shell is needed.

For a running shell suspected of hanging, test responsiveness first:

```bash
timeout 7s busctl --user --timeout=3 call org.kde.plasmashell \
  /PlasmaShell org.freedesktop.DBus.Peer Ping
```

A timeout alone does not locate the fault: corroborate it with the correct
session bus, shell ownership, logs and display state. If the shell is confirmed
unresponsive, capture evidence and run:

```bash
systemctl --user restart plasma-plasmashell.service
```

Allow for the installed unit's stop timeout. If systemd must kill the old
process before starting its replacement, record that as evidence of the hang,
not a new spontaneous crash. Verify D-Bus responsiveness and panel visibility.
Display-loss events preceding the hang are possible triggers, not proof of
the underlying cause.

Restarting `plasmashell` generally preserves application windows but briefly
removes desktop/panels. Do not restart KWin on Wayland: it is the display server
and restarting it may terminate the session.

For older Plasma without this unit, inspect `plasmashell --help` and available
KDE launch tools before using a session-attached replacement. Do not create a
second unmanaged shell alongside a systemd-managed one.

For live panel inspection, discover the installed `qdbus`, `qdbus6` or
`qdbus-qt5` command and introspect `org.kde.plasmashell /PlasmaShell` first.
Use scripting interfaces read-only initially. Do not invoke layout-changing
scripts until the target panel and intended setting are established.

## GNOME: shell, dock, extensions and notifications

```bash
gnome-shell --version
systemctl --user list-units --all --no-pager 'org.gnome.Shell*'
journalctl --user -b --since 'INCIDENT_START' --no-pager _COMM=gnome-shell -n 100
gnome-extensions list --enabled
gnome-extensions info EXTENSION_UUID
gsettings list-recursively org.gnome.shell
```

Inspect logs for the implicated extension UUID and compare its state with the
expected dock/menu behavior. Ubuntu Dock is commonly an extension; identify
the installed UUID instead of assuming it. Query its settings only when that
schema exists (`gsettings list-schemas`). Record current values before edits.

Disable only an extension implicated by evidence:

```bash
gnome-extensions disable EXTENSION_UUID
```

Reverse with `gnome-extensions enable EXTENSION_UUID`. Check the visible result
and logs; some changes require a later session restart.

On Wayland, GNOME Shell is also the compositor: do not kill/restart it or use
`gnome-shell --replace` as a panel-only recovery. `Alt+F2`, then `r`, is an X11
mechanism, not a Wayland recovery. For any shell replacement/session restart,
confirm protocol, version and user acceptance of disruption first.

For notification failures, inspect `org.freedesktop.Notifications` on the
session bus and GNOME's notification/do-not-disturb settings. Treat D-Bus
activation timeouts as possible consequences of shell failure.

## Shared font-rendering crashes

Use this branch when meaningful crash frames point to `FcCharSetHasChar`,
Fontconfig, Qt font fallback or shaping, particularly in multiple GUI apps.

```bash
fc-match -f '%{file} | %{family} | %{style}\n' sans
fc-match -f '%{file} | %{family} | %{style}\n' monospace
fc-match -f '%{file} | %{family} | %{style}\n' 'Noto Sans'
fc-scan --format '%{family} | %{style} | %{charset}\n' /path/to/suspect-font
dpkg -S /path/to/suspect-font
```

Inspect `~/.config/fontconfig`, `~/.fonts.conf`, `/etc/fonts/conf.d` and relevant
cache locations. A math/web font unexpectedly matching all normal families,
with blank cached metadata but correct direct-scan metadata, is evidence for
bad cached records. WOFF files and multiple cache-format versions alone are
not proof of corruption; do not remove fonts based only on file extension.

To test stale/corrupt caches, rebuild as the affected user:

```bash
fc-cache -f -r
```

This regenerates disposable caches in locations writable by that user; it does
not guarantee repair of root-owned system caches. Compare the exact font
matches again, then restart only the affected safely restartable application
or shell. Already-running applications may retain old font state.

If unchanged, identify which cache/configuration is actually being used before
escalating. Back up targeted state before further changes. Use elevated cache
repair only when system-cache evidence warrants it and privileges are available.

### Observed Kubuntu incident

Plasma under Wayland crashed three times at login, then hit systemd's start
limit. Plasma's Klipper initialization and separate Konsole crashes shared
`FcCharSetHasChar` / Qt font-fallback frames. Ordinary font matches incorrectly
selected `KaTeX_AMS-Regular.woff`; direct scanning returned valid metadata.
After `fc-cache -f -r`, matching returned Noto Sans / Noto Sans Mono, and starting
`plasma-plasmashell.service` restored a healthy running shell.

During panel recovery with this evidence chain, user confirmation established
that the panel was visible and usable after cache rebuilding and shell startup.
Preserve this verification step rather than assuming process health proves the
visible result.

Generalize the evidence chain, not the remedy: the cache-generation cause was
not established. Do not automatically rebuild caches for every missing panel.

## Displays, scaling, black screens and login loops

- Plasma: use `kscreen-doctor -o` if installed to inspect enabled connectors,
  modes, scale and positions. Inspect KWin/DRM logs before changing outputs.
- GNOME: inspect display settings and `~/.config/monitors.xml`; back up before
  targeted edits. Use installed Mutter interfaces/tools only after discovery.
- X11: use `xrandr --query` for output state. Under Wayland, Xwayland's `xrandr`
  output does not describe the compositor's real physical output configuration.
- Identify GPU and driver using `lspci -nnk`; inspect incident-scoped kernel
  logs. Distinguish rendering errors from compositor exits or disconnected
  outputs. Avoid treating every warning as causal.
- Login loop: discover `display-manager.service`, inspect its status and
  incident-scoped journal, then inspect the affected session's logs. Check home
  disk space, specific ownership errors and user startup hooks. Avoid recursive
  home ownership changes or deleting Xauthority on a Wayland session by default.
- Black screen with working apps: first check shell/compositor process health
  and output mapping. Black screen with session termination: investigate login,
  compositor or driver failure. Do not restart the display manager before
  capturing evidence and obtaining confirmation.
