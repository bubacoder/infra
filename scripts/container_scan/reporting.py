"""Human summaries, optional gates and conservative per-container history."""

import csv
from datetime import UTC, date, datetime

from .common import read_json, write_json
from .findings import SEVERITIES, changed
from .policy import exception_for


def escape(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("`", "'")


def fix_hint(finding):
    suggestions = sorted({e["suggested_fix"] for e in finding["evidence"] if e["suggested_fix"]})
    return ", ".join(suggestions) or ("Reported; verify applicable branch" if finding["reported_fix"] else "Not reported")


def load_history(path):
    state = read_json(path) if path.exists() else {"schema": 1, "containers": {}}
    if not isinstance(state, dict):
        raise TypeError("History must be an object")
    if state.get("schema") != 1 or not isinstance(state.get("containers"), dict):
        raise ValueError("Invalid history schema")
    # Corrupt history is recovery data, not an empty baseline.
    for entry in state["containers"].values():
        if not isinstance(entry, dict) or not isinstance(entry.get("findings"), list):
            raise TypeError("Invalid history entry")
        for finding in entry["findings"]:
            if not isinstance(finding, dict) or not all(k in finding for k in ("id", "aliases", "component")):
                raise ValueError("Invalid history finding")
            if not isinstance(finding["aliases"], list) or any(not isinstance(v, str) for v in finding["aliases"]):
                raise ValueError("Invalid history advisory aliases")
            if not isinstance(finding["id"], str) or not isinstance(finding["component"], str):
                raise TypeError("Invalid history advisory/component")
    return state


def history_changes(report, target_dir):
    path = target_dir / "state.json"
    try:
        state = load_history(path)
    except (ValueError, OSError, TypeError, KeyError):
        report["issues"].append("History unavailable or invalid; preserved without changes")
        report["changes"] = []
        return
    changes = []
    for image in report["images"]:
        safe = image["status"] == "complete" and not image["coverage"] and not report["issues"]
        for container in image["containers"]:
            name = container["name"]
            previous = state["containers"].get(name)
            if not safe:
                changes.append({"container": name, "status": "not_compared", "reason": "Coverage incomplete; previous findings retained"})
                continue
            current = [{k: f[k] for k in ("id", "aliases", "component")} for f in image["findings"]]
            difference = changed(previous["findings"] if previous else [], current)
            changes.append({"container": name, "status": "compared" if previous else "initial", **difference})
            state["containers"][name] = {"image": image["id"], "run": report["run"], "findings": current}
    report["changes"] = changes
    write_json(path, state)


def apply_triage(report, policy):
    for rule in policy.get("triage", []):
        if date.fromisoformat(rule["expires"]) < datetime.now(UTC).date():
            report["issues"].append(f"Expired triage exception: {rule['advisory']} / {rule['container']}")
    for image in report["images"]:
        for finding in image.get("findings", []):
            finding["triage"] = {}
            for container in image["containers"]:
                rule = exception_for(finding, container["name"], policy)
                if rule:
                    finding["triage"][container["name"]] = rule


def gate_failed(report, fail_on):
    if not fail_on:
        return False
    threshold = SEVERITIES.index(fail_on)
    return any(
        any(c["name"] not in f["triage"] for c in image["containers"])
        and any(SEVERITIES.index(s) >= threshold for values in f["severities"].values() for s in values if s in SEVERITIES)
        for image in report["images"]
        for f in image.get("findings", [])
    )


def rows_for(report):
    return [(image, finding) for image in report["images"] for finding in image.get("findings", [])]


def write_csv(report, directory):
    with (directory / "findings.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["containers", "image", "advisory", "component", "versions", "scanner_severities", "fix", "known_exploitation", "triaged_for", "note"]
        )
        for image, finding in rows_for(report):
            values = [
                ", ".join(c["name"] for c in image["containers"]),
                image["id"],
                finding["id"],
                finding["component"],
                ", ".join(finding["versions"]),
                str(finding["severities"]),
                fix_hint(finding),
                "flagged" if finding["known_exploited"] else "not flagged/unknown",
                ", ".join(finding["triage"]),
                finding["note"],
            ]
            # Avoid spreadsheet formula injection from package/image metadata.
            writer.writerow(["'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values])


def summary_lines(report):
    rows = rows_for(report)
    lines = [
        "# Combined container vulnerability scan",
        "",
        f"Status: **{report['status']}** — not a declaration of safety.",
        f"Target: `{escape(report['target']['context'])}`; started {report['started']}.",
        f"Containers: {sum(len(i['containers']) for i in report['images'])}; unique images: {len(report['images'])}; "
        f"combined component/advisory findings: {len(rows)}.",
        f"Elapsed: {report['seconds']:.1f}s. Optional vulnerability gate: {'failed' if report['gate_failed'] else 'not failed'}.",
        "",
        "## Coverage problems",
        "",
    ]
    issues = list(report["issues"])
    for image in report["images"]:
        names = ", ".join(c["name"] for c in image["containers"])
        issues.extend(f"{names}: {issue}" for issue in image["coverage"])
        if image["status"] != "complete":
            issues.append(f"{names}: pipeline {image['status']}; inspect image stage records")
    lines.extend(["- " + escape(i) for i in issues] or ["No recorded coverage problems. This does not prove complete software detection."])
    lines += [
        "",
        "## Investigate first",
        "",
        "Untriaged findings; scanner-only findings are retained. Severity is not exploitability.",
        "",
        "| Containers | Advisory | Component / installed versions | Scanner severities | Reported fix |",
        "| --- | --- | --- | --- | --- |",
    ]
    candidates = [(i, f) for i, f in rows if any(c["name"] not in f["triage"] for c in i["containers"])]
    candidates.sort(
        key=lambda pair: (
            bool(pair[1]["note"]),
            not pair[1]["known_exploited"],
            -SEVERITIES.index(pair[1]["severity"]) if pair[1]["severity"] in SEVERITIES else 0,
            not pair[1]["reported_fix"],
            pair[1]["id"],
        )
    )
    for image, finding in candidates[:25]:
        names = ", ".join(c["name"] for c in image["containers"] if c["name"] not in finding["triage"])
        severity = "; ".join(k + ": " + ",".join(v) for k, v in finding["severities"].items())
        advisory = finding["id"] + (" (known exploitation flagged)" if finding["known_exploited"] else "")
        lines.append(
            "| "
            + " | ".join(
                escape(v) for v in [names, advisory, finding["component"] + " / " + ", ".join(finding["versions"]), severity, fix_hint(finding)]
            )
            + " |"
        )
    if not candidates:
        lines.append("| — | No untriaged findings reported | — | — | — |")
    lines += [
        "",
        "Shows at most 25 prioritized findings. Full results, triage evidence and scanner provenance: `findings.json` / `findings.csv`.",
        f"Kernel-header matches retained for applicability review: {sum(bool(f['note']) for _, f in rows)}. They do not describe the running host kernel.",
        "",
        "## Changes",
        "",
    ]
    for change in report.get("changes", []):
        if change["status"] == "not_compared":
            text = change["reason"]
        elif change["status"] == "initial":
            text = f"Initial baseline: {len(change['new'])} findings (not all newly introduced)"
        else:
            text = f"{len(change['new'])} newly reported; {len(change['no_longer_reported'])} no longer reported (not proof of remediation)"
        lines.append(f"- {escape(change['container'])}: {text}")
        if change["status"] == "compared":
            for key, label in [("new", "Newly reported"), ("no_longer_reported", "No longer reported")]:
                if change[key]:
                    examples = "; ".join(f"{identifier} ({name})" for identifier, name in change[key][:5])
                    suffix = "; more in inventory.json" if len(change[key]) > 5 else ""
                    lines.append(f"  - {label}: {escape(examples + suffix)}")
    lines += [
        "",
        "## Per-image execution",
        "",
        "| Containers | Trivy | Syft | Grype | Syft cache | Packages T / S |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for image in report["images"]:
        stages = image["stages"]
        cells = [", ".join(c["name"] for c in image["containers"])]
        cells += [
            s + f" {stages[tool].get('seconds', 0):.1f}s" if tool in stages else s
            for tool in ("trivy", "syft", "grype")
            for s in [stages.get(tool, {}).get("status", "not run")]
        ]
        cells += ["reused" if stages.get("syft", {}).get("cached") else "not reused", str(image.get("packages", {}))]
        lines.append("| " + " | ".join(escape(c) for c in cells) + " |")
    lines += [
        "",
        "## Limits",
        "",
        "Inventories can miss components. Unknown distributions, new advisories, backports and compiled binaries need review.",
        "Writable container layers, mounted applications, host kernel vulnerabilities and actual network exploitability are not assessed.",
        "Native reports and logs may contain sensitive image metadata; keep this directory private.",
        "No application images were pulled; no containers were executed, modified or restarted.",
        "",
    ]
    return lines


def finish(report, directory, target_dir, policy, fail_on):
    apply_triage(report, policy)
    history_changes(report, target_dir)
    report["gate_failed"] = gate_failed(report, fail_on)
    incomplete = bool(report["issues"]) or any(i["status"] != "complete" or i["coverage"] for i in report["images"])
    report["status"] = "incomplete" if incomplete else "complete"
    write_json(directory / "inventory.json", report)
    write_json(
        directory / "findings.json",
        [{"image": image["id"], "containers": [c["name"] for c in image["containers"]], **finding} for image, finding in rows_for(report)],
    )
    write_csv(report, directory)
    (directory / "summary.md").write_text("\n".join(summary_lines(report)))
    write_json(target_dir / "latest.json", {"run": report["run"], "status": report["status"]})
    return 2 if incomplete else 1 if report["gate_failed"] else 0
