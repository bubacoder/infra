# Ubuntu crash diagnostics

## Contents

- [Crash workflow](#crash-workflow)
- [Host and boot selection](#host-and-boot-selection)
- [Journal and preserved crashes](#journal-and-preserved-crashes)
- [Live freeze](#live-freeze)
- [Historical resource usage](#historical-resource-usage)
- [Scheduled jobs](#scheduled-jobs)
- [Storage and hardware](#storage-and-hardware)
- [Observed NVMe incident](#observed-nvme-incident)

Replace `BOOT_ID`, `START`, `END`, `DEVICE`, `UNIT`, and `PID` with discovered
values; do not run placeholders literally. Use absolute incident dates and the
host timezone. Check tool availability; do not install packages just to diagnose.
These commands are selective examples, not a batch to run blindly.

## Crash workflow

### Establish the incident boot and preserve evidence

- Establish whether the host is frozen now or has rebooted; select the incident
  boot from `journalctl --list-boots`, not automatically `-1`. Resolve incident
  date/time against the host clock/timezone; ask about AM/PM only if ambiguous.
- Distinguish one frozen app, desktop-only hang, network loss, storage stall and
  kernel lockup. Ask whether SSH/TTY/services still worked and how recovery
  happened: automatic reboot, reset, power cycle or GUI/session restart.
- **Check pstore early alongside the incident journal.** Root-drive failure can
  stop journald before decisive kernel messages. Inspect live/archived pstore,
  its archival service, `/var/crash` and existing kdump output when available.
- Build a timeline from the incident boot's last records and the onset window,
  including informational events, OOM, hung tasks, lockups, GPU resets, disk
  timeout/reset failures, filesystem errors, PCIe AER, machine checks, thermal
  events, panic and orderly shutdown markers.
- Treat empty journal/pstore as an evidence limitation; check retention/access
  and whether archives belong to this incident. Correlate boot identity, crash
  metadata and monotonic timestamps with dated events from that same boot.
  Label wall-clock conversions approximate if suspend/clock changes affect them.

### Trace cause versus consequence

Follow the earliest supported failure in a short ordered timeline.

| Evidence | Investigate next |
| --- | --- |
| NVMe/ATA timeout/reset failure before I/O/filesystem errors | Controller, firmware/health, PCIe link, power and cooling |
| OOM or memory-pressure stall before unresponsiveness | Historical available memory, swap rates, PSI, process/cgroup limits |
| GPU/compositor fault while SSH/services remain usable | Affected desktop session and GPU/driver; read [desktop.md](desktop.md) |
| Lockup, RCU stall, panic or machine-check report | First meaningful kernel stack, hardware/driver context, prior working kernel |
| Orderly shutdown/reboot | Initiating user/service, update policy, timer, power/suspend events |
| Abrupt end without preserved failure | Remote telemetry, power/reset history, log gaps; leave cause unresolved |

- Do not blame a process merely because its stack appears in a hung-task dump;
  multiple tasks may wait on the same failed storage/kernel subsystem.
- Trace events before the final panic: failed swap reads can kill PID 1 and
  cause "Attempted to kill init". The panic is not necessarily the initiator.
- Separate SMART media errors from controller availability. Healthy SMART after
  reboot does not disprove a controller hang. Clean current filesystem counters
  do not prove the previous boot was healthy; aborted transactions can prevent
  error persistence.
- Compare recurring warnings against working periods. Generic warnings, optional
  CUDA-library messages on AMD hosts, and unrelated app crashes are not causal
  without temporal and mechanism evidence.

### Test overload and scheduling only when relevant

- Use existing historical sysstat/sar, atop, Prometheus or external metrics;
  current memory/process lists cannot explain pre-reboot usage. Compare an onset
  window with a baseline: available memory, swap rates, PSI, CPU idle/iowait,
  runnable/blocked tasks, disk latency/throughput and process/cgroup limits.
- Low free RAM, high virtual commitment, or occupied swap alone do not prove
  exhaustion. Account for sampling gaps; ten-minute samples can miss brief spikes.
  Validate suspicious disk counters before claiming saturation or precise onset.
- Check system and affected-user timers/crontabs, root's crontab, cron periodic
  directories, anacron, unattended upgrades, backups/dedupe/scrubs, container jobs
  and app schedulers only when relevant. Correlate actual execution and duration,
  not post-reboot schedules. Read implicated scripts; do not execute them to
  discover their workload. Hand off implicated containers via the core routing table.

### Choose and verify a targeted next step

- Report the confirmed mechanism, suspected triggers, confidence and missing
  evidence before changes. Honor diagnosis-only requests.
- For storage failures, verify backup health before scheduling integrity scans;
  scrub status with "no stats available" is not a completed clean scan. Follow
  the core's confirmation requirements for disruptive changes/heavy tests.
- If evidence is missing, propose the smallest useful capture improvement:
  persistent/remote logging, metric retention, pstore support, or kdump for a
  reproducible panic. Explain capture limits: power loss/hard lockups may leave
  no dump. Do not install a whole monitoring stack by default.
- After an approved repair, test the affected path and observe over the prior
  recurrence interval when practical. A reboot or clean SMART result is recovery
  evidence, not proof of a permanent fix; report longer-term checks as pending.

## Host and boot selection

```bash
date --iso-8601=seconds
hostnamectl
uptime
id
journalctl --list-boots --no-pager
last -x -n 20
systemctl --failed --no-pager
```

Use journal boot IDs and bounds as primary evidence; `last`/wtmp may be missing,
stale, or omit hard resets. Check whether the execution environment is the affected
host. Read `/proc/cmdline` for the current kernel parameters, not as proof of the
previous boot's command line.

## Journal and preserved crashes

```bash
journalctl -b BOOT_ID --since 'START' --until 'END' --no-pager -o short-iso
journalctl -b BOOT_ID --no-pager -o short-iso -n 100
journalctl -b BOOT_ID -k --since 'START' --until 'END' --no-pager -o short-iso
journalctl -b BOOT_ID -k --grep 'oom|Out of memory|Killed process|blocked for|lockup|watchdog|rcu.*stall|GPU|amdgpu|i915|NVRM|nvme|ata[0-9]|I/O error|BTRFS|EXT4-fs error|AER|Hardware Error|thermal|panic' --no-pager -n 150
journalctl -b BOOT_ID --since 'START' --until 'END' --no-pager -o short-monotonic -n 100
journalctl -b 0 -u systemd-pstore.service --no-pager
systemctl status systemd-pstore.service --no-pager
coredumpctl list --since 'START' --until 'END' --no-pager
```

Explicitly select the boot for `journalctl -k`; without a selection it implies
the current boot. For a cross-boot search use `_TRANSPORT=kernel` with an absolute
time range instead of relying on an unqualified `-k`.

Inspect these locations with file tools, including nested archive directories:

- `/sys/fs/pstore`: firmware/RAM-backed kernel records, if supported.
- `/var/lib/systemd/pstore`: records archived at boot; look for `dmesg.txt`
  and individual `dmesg-*` fragments. Archives/layout vary by systemd version.
- `/var/crash`: Ubuntu crash reports and, depending on configuration, kdump output.
- `/etc/systemd/pstore.conf` and drop-ins: only if archival behavior needs explaining.

If a file reader cannot read root-owned pstore records, use an available
privileged read-only command (for example `sudo -n cat` on the exact discovered
path). Record permission failures rather than silently treating them as no data.
Do not delete EFI variables, pstore files, crash reports, or journal archives.

Pstore can retain only the tail of a panic: missing initial timeout messages
do not make downstream errors the initiator. Match the kernel version, uptime,
and archive metadata to the incident. A numeric archive name may represent an
epoch timestamp, but verify rather than assuming. Use `date -d @EPOCH` when
appropriate. Never add uptime to the journal's first entry as if it were
necessarily the true boot instant; anchor to a same-boot dated monotonic event.

## Live freeze

If SSH or a TTY still works, collect a lightweight snapshot before recovery:

```bash
free -h
df -h / /var/log /tmp
vmstat 1 5
ps -eo pid,ppid,state,wchan:32,comm,%cpu,%mem --sort=-%cpu
systemctl list-jobs --no-pager
journalctl -b 0 -k --since '-15 minutes' --no-pager -n 100
loginctl list-sessions
```

Read `/proc/pressure/{cpu,memory,io}` if available. Investigate a small number of
implicated D-state tasks via `/proc/PID/stack` with suitable privileges. Do not
dump every process environment. If output is large, inspect captured output with
file tools rather than repeatedly rerunning expensive queries.

If only the graphical session is affected, follow the core routing table and
read [desktop.md](desktop.md); confirm session/protocol before desktop operations.
If only SSH failed, inspect network and SSH evidence before calling it a host lockup.

Do not deliberately reproduce a full-host crash during diagnosis. SysRq crash,
controller resets, and compositor/display-manager restarts change state and can
lose work. Arrange any disruptive capture/recovery explicitly with the user.

## Historical resource usage

Inspect `/var/log/sysstat` first; filenames can use day-of-month or full dates.
Check the report header to ensure the selected file matches the incident date.
Use a baseline before onset and a narrow window through failure:

```bash
LC_ALL=C sar -f /var/log/sysstat/saDD -s HH:MM:SS -e HH:MM:SS -u -r -S -W -q
LC_ALL=C sar -f /var/log/sysstat/saDD -s HH:MM:SS -e HH:MM:SS -d --dev=DEVICE
```

Use the actual device name such as `nvme0n1`, not its `/dev/` path, for `--dev`.
Check installed sar help if that filter is unsupported. Avoid unfiltered disk
reports containing dozens of snap loop devices. Do not run unbounded `sar -A`.

Interpret:

- `kbavail`, OOM evidence, swap **rates**, and memory PSI together; distinguish
  cached memory from exhausted RAM and virtual commitment from resident usage.
- CPU idle and load relative to CPU count; inspect per-CPU data if a single-core
  bottleneck is plausible.
- Disk await, queue depth, throughput, blocked tasks, and kernel errors together.
  Counter artifacts/long completions and interval averaging can produce unusual
  values; high await alone does not prove the physical drive is worn out.
- Existing Prometheus/atop data for process/cgroup attribution and shorter
  intervals. Avoid exposing credentials when querying local monitoring.

State when no pre-crash telemetry exists. Do not retrofit post-reboot process
RSS or current sensor readings into the historical incident.

## Scheduled jobs

```bash
systemctl list-timers --all --no-pager
systemctl --user list-timers --all --no-pager
crontab -l
sudo -n crontab -l
journalctl -b BOOT_ID --since 'START' --until 'END' -u cron.service -u anacron.service --no-pager
journalctl -b BOOT_ID --since 'START' --until 'END' -u UNIT --no-pager
```

Run user commands on the affected user's bus, not as root's user manager.
Inspect `/etc/crontab`, `/etc/cron.d`, `/etc/cron.hourly`, `/etc/cron.daily`,
`/etc/anacrontab`, and implicated unit definitions with file tools. Read scripts
to identify workload; do not execute them. Use journal CRON/CMD searches if
unit filtering misses syslog records. Check app schedulers (e.g. Hermes), backup
logs, and container-local cron only when relevant. Hide webhook URLs/secrets.

Record start, finish, resource peak, and overlap—not merely schedule coincidence.
Compare routine hourly restarts or recurring warnings against unaffected hours.

## Storage and hardware

Discover device topology first, then query only implicated hardware:

```bash
lsblk -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINTS
findmnt -no SOURCE,FSTYPE,OPTIONS /
sudo -n smartctl -x /dev/DEVICE
sensors
sudo -n lspci -s PCI_ADDRESS -vv
sudo -n btrfs device stats /
sudo -n btrfs scrub status /
sysctl kernel.panic kernel.hung_task_timeout_secs
```

Use Btrfs commands only for Btrfs. SMART reads may wake sleeping disks. Querying
scrub status is read-only; starting a scrub is a separate workload. Zero persisted
device counters and "no stats available" do not establish post-crash integrity.
Check NVMe SMART temperature, wear, critical warnings, media errors, error log,
firmware, and unsafe shutdowns. Separate current health from crash evidence.

If power management is a supported hypothesis, inspect current values in
`/sys/module/nvme_core/parameters/default_ps_max_latency_us`, the device's
`power/control`, and PCIe ASPM state. Do not assume runtime PCI power management,
NVMe autonomous power states, and PCIe ASPM are interchangeable. Do not disable
all power management as a default fix. Check AER and machine-check logs; distinguish
normal platform link-speed limits from evidence of link failure.

## Observed NVMe incident

On 2026-10-04, an Ubuntu/Kubuntu host appeared frozen around 05:00. Ordinary
journal records ended at 05:20, yet firmware-preserved records showed a panic
around 05:26. The archived sequence was:

```text
nvme nvme0: Device not ready; aborting reset, CSTS=0x1
nvme nvme0: Disabling device after reset failure: -19
I/O error, dev nvme0n1 ...
Read-error on swap-device
BTRFS ... Transaction aborted (error -5)
BTRFS ... forced readonly
Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b
```

Hung Btrfs users, failed service coredumps, and desktop failures were consequences
of losing root/swap access. Historical samples through 05:20 showed about 88%
CPU idle and 14 GiB available RAM; the 05:00 scheduled worker had finished quickly.
After reboot, the Samsung 990 PRO passed SMART with zero media errors, and current
Btrfs counters were zero. These checks did not invalidate the preserved failure.

Generalize the method, not the device-specific conclusion: confirm storage loss
when supported, but leave firmware, kernel, power, PCIe, or hardware triggers
unresolved until independent evidence distinguishes them.
