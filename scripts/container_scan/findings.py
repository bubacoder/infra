"""Conservative advisory aliases and cross-scanner component identities."""

import re
from urllib.parse import parse_qs, unquote

SEVERITIES = ("UNKNOWN", "NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
FAMILIES = {
    "alpine": "apk",
    "debian": "deb",
    "ubuntu": "deb",
    "go-module": "golang",
    "gobinary": "golang",
    "gomod": "golang",
    "python": "pypi",
    "python-pkg": "pypi",
    "java-archive": "maven",
    "jar": "maven",
    "binary": "generic",
}


class Aliases:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def join(self, identifiers):
        # DSA/DLA bulletins may cover many unrelated CVEs; never merge on them.
        keys = [key for key in identifiers if re.fullmatch(r"CVE-[0-9]{4}-[0-9]+|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}|GO-[0-9]{4}-[0-9]+", key)]
        for key in keys[1:]:
            left, right = self.find(keys[0]), self.find(key)
            preferred = min((left, right), key=lambda v: (not v.startswith("CVE-"), v))
            self.parent[left] = preferred
            self.parent[right] = preferred


def component(name, version, purl, family):
    if purl and purl.startswith("pkg:"):
        path = purl[4:].split("?", 1)[0].split("#", 1)[0]
        if "@" in path:
            path, encoded_version = path.rsplit("@", 1)
            version = unquote(encoded_version)
        family, name = path.split("/", 1)
        name = unquote(name)
        epoch = parse_qs(purl.partition("?")[2].split("#", 1)[0]).get("epoch", ["0"])[0]
        if family in ("deb", "rpm") and epoch != "0" and ":" not in version:
            version = epoch + ":" + version
    else:
        family = FAMILIES.get(family, family)
    if family == "golang":
        version = re.sub(r"^(?:go|v)(?=[0-9])", "", version)
    if family == "pypi":
        name = re.sub(r"[-_.]+", "-", name).lower()
    return f"{family}/{name}", version


def fix_suggestion(version, candidates):
    """Do not choose another PHP/Python/OpenSSL branch or suggest a downgrade."""
    installed = re.match(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)$", version)
    if installed:
        current = tuple(map(int, installed.groups()))
        for candidate in candidates:
            parsed = re.match(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)$", candidate)
            if parsed:
                fixed = tuple(map(int, parsed.groups()))
                if fixed[:2] == current[:2] and fixed > current:
                    return candidate
        return None
    # Distro versions include revisions/epochs; keep native advice, do not invent ordering.
    return candidates[0] if len(candidates) == 1 else None


def trivy_evidence(report):
    evidence = []
    for result in report.get("Results") or []:
        for finding in result.get("Vulnerabilities") or []:
            identifier = finding["VulnerabilityID"]
            key, version = component(
                finding["PkgName"], finding.get("InstalledVersion", ""), finding.get("PkgIdentifier", {}).get("PURL", ""), result.get("Type", "")
            )
            candidates = [v.strip() for v in (finding.get("FixedVersion") or "").split(",") if v.strip()]
            evidence.append(
                {
                    "id": identifier,
                    "aliases": [identifier, *(finding.get("VendorIDs") or [])],
                    "component": key,
                    "version": version,
                    "scanner": "trivy",
                    "severity": finding.get("Severity", "UNKNOWN").upper(),
                    "fix_candidates": candidates,
                    "suggested_fix": fix_suggestion(version, candidates),
                    "known_exploited": None,
                    "source": finding.get("DataSource", {}).get("ID", "unknown"),
                }
            )
    return evidence


def grype_evidence(report):
    evidence = []
    for match in report.get("matches") or []:
        finding, package = match["vulnerability"], match["artifact"]
        identifier = finding["id"]
        key, version = component(package["name"], package.get("version", ""), package.get("purl", ""), package.get("type", ""))
        candidates = finding.get("fix", {}).get("versions") or []
        suggested = next(
            (m.get("fix", {}).get("suggestedVersion") for m in match.get("matchDetails") or [] if m.get("fix", {}).get("suggestedVersion")), None
        )
        # Validate semver suggestions too: a generic CPE can list fixes for several branches.
        suggested = fix_suggestion(version, [suggested] if suggested else candidates)
        evidence.append(
            {
                "id": identifier,
                "aliases": [identifier, *(a["id"] for a in match.get("relatedVulnerabilities") or [])],
                "component": key,
                "version": version,
                "scanner": "grype",
                "severity": finding.get("severity", "Unknown").upper(),
                "fix_candidates": candidates,
                "suggested_fix": suggested,
                "known_exploited": bool(finding["knownExploited"]) if "knownExploited" in finding else None,
                "source": finding.get("namespace", "unknown"),
            }
        )
    return evidence


def combine(trivy, grype):
    evidence = trivy_evidence(trivy or {}) + grype_evidence(grype or {})
    aliases = Aliases()
    for row in evidence:
        aliases.join(row["aliases"])
    grouped = {}
    for row in evidence:
        identifier = aliases.find(row["id"])
        key = identifier, row["component"]
        if key not in grouped:
            grouped[key] = {
                "id": identifier,
                "aliases": set(),
                "component": row["component"],
                "versions": set(),
                "scanners": set(),
                "severities": {},
                "evidence": [],
                "known_exploited": False,
            }
        finding = grouped[key]
        finding["aliases"].update(v for v in row["aliases"] if aliases.find(v) == identifier)
        finding["aliases"].add(identifier)
        finding["versions"].add(row["version"])
        finding["scanners"].add(row["scanner"])
        finding["severities"].setdefault(row["scanner"], set()).add(row["severity"])
        finding["known_exploited"] |= row["known_exploited"] is True
        if row not in finding["evidence"]:
            finding["evidence"].append(row)
    results = []
    for finding in grouped.values():
        for field in ("aliases", "versions", "scanners"):
            finding[field] = sorted(finding[field])
        finding["severities"] = {k: sorted(v) for k, v in finding["severities"].items()}
        finding["severity"] = max(
            (s for values in finding["severities"].values() for s in values), key=lambda s: SEVERITIES.index(s) if s in SEVERITIES else 0
        )
        finding["reported_fix"] = any(e["fix_candidates"] for e in finding["evidence"])
        finding["note"] = (
            "Kernel headers are not the running host kernel; assess host exposure separately"
            if ("linux-libc-dev" in finding["component"] or "linux-headers" in finding["component"])
            else ""
        )
        results.append(finding)
    return sorted(
        results,
        key=lambda f: (
            not f["known_exploited"],
            -SEVERITIES.index(f["severity"]) if f["severity"] in SEVERITIES else 0,
            not f["reported_fix"],
            f["id"],
            f["component"],
        ),
    )


def inventory_counts(trivy, syft):
    trivy_packages = [p for r in (trivy or {}).get("Results") or [] for p in r.get("Packages") or []]
    syft_packages = (syft or {}).get("artifacts") or []
    return {"trivy": len(trivy_packages), "syft": len(syft_packages)}, {p["name"] for p in syft_packages}


def changed(before, after):
    """Versions are evidence, not identity: a still-vulnerable upgrade is not resolved."""
    aliases = Aliases()
    for finding in before + after:
        aliases.join(finding["aliases"])

    def keys(findings):
        return {(aliases.find(f["id"]), f["component"]) for f in findings}

    old, current = keys(before), keys(after)
    return {"new": sorted(current - old), "no_longer_reported": sorted(old - current)}
