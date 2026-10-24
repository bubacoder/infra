"""Independent native scans, frozen databases and verified Syft inventory reuse."""

import shutil
import time
import uuid

from .common import database_issue, digest, execute, file_digest, read_json, scanner_environment, validate_json_stage, write_json

SYFT_SETTINGS = "check-for-app-update: false\ngolang:\n  capture-symbols: all\n"
GRYPE_SETTINGS = "check-for-app-update: false\ndb:\n  auto-update: false\n"


def native_sbom(value, image_id, architecture=None):
    if not isinstance(value, dict) or not isinstance(value.get("artifacts"), list):
        return False
    source = value.get("source", {})
    metadata = source.get("metadata") or source.get("target") or {}
    # Docker's containerd store can expose a repository/index digest as .Image;
    # Syft's imageID instead identifies the selected platform's config blob.
    identities = {metadata.get("imageID"), metadata.get("manifestDigest")}
    identities.update(ref.rsplit("@", 1)[-1] for ref in metadata.get("repoDigests") or [])
    return (
        source.get("type") == "image"
        and image_id in identities
        and metadata.get("userInput", image_id) == image_id
        and (architecture is None or metadata.get("architecture") == architecture)
    )


def native_trivy(value, image_id):
    # A valid zero-package report omits Results entirely. It is a coverage gap,
    # not a failed process or malformed artifact; runner flags the empty inventory.
    return (
        isinstance(value, dict)
        and value.get("SchemaVersion") == 2
        and value.get("ArtifactName") == image_id
        and isinstance(value.get("Metadata"), dict)
        and (value.get("Results") is None or isinstance(value["Results"], list))
    )


def warning_issues(directory, label):
    path = directory / f"{label}.stderr.log"
    if not path.exists():
        return []
    issues = set()
    for line in path.read_text(errors="replace").splitlines():
        if "WARN" not in line and "ERROR" not in line and "FATAL" not in line:
            continue
        if "Using severities from other vendors" in line:
            continue
        if "Unable to get vulnerability details" in line:
            issues.add(f"{label}: advisory details missing; inspect private logs")
        elif "no longer supported" in line or "security updates are not provided" in line:
            issues.add(f"{label}: end-of-life distribution; vulnerability coverage may be incomplete")
        elif "distro" in line and ("failed" in line or "unable" in line):
            issues.add(f"{label}: distribution could not be identified")
        elif "symbol" in line:
            issues.add(f"{label}: function symbols unavailable; matches may be less precise")
        else:
            issues.add(f"{label}: scanner warning; inspect private logs")
    return sorted(issues)


class Scanners:
    def __init__(self, root, directory, target, timeout):
        self.root = root
        self.directory = directory
        self.env = scanner_environment(target["endpoint"])
        self.endpoint = target["endpoint"]
        self.timeout = timeout
        self.versions = {}
        self.setup = {}
        self.issues = []
        self.syft_config = directory / "syft.yaml"
        self.grype_config = directory / "grype.yaml"
        self.syft_config.write_text(SYFT_SETTINGS)
        self.grype_config.write_text(GRYPE_SETTINGS)

    def command(self, args, directory, label):
        return execute(args, directory, label, env=self.env, timeout=self.timeout)

    def json_command(self, args, label):
        stage = self.command(args, self.directory, label)
        value = validate_json_stage(stage, self.directory / f"{label}.stdout.log", lambda v: isinstance(v, dict))
        self.setup[label] = stage
        if value is None:
            self.issues.append(f"{label}: tool metadata unavailable")
        return value or {}

    def metadata(self, suffix):
        trivy = self.json_command(["trivy", "--version", "--format", "json"], f"trivy-metadata-{suffix}")
        grype = self.json_command(["grype", "-c", str(self.grype_config), "db", "status", "-o", "json"], f"grype-metadata-{suffix}")
        return {"trivy": {**trivy.get("VulnerabilityDB", {}), "java_index": trivy.get("JavaDB")}, "grype": grype}

    def prepare(self, maximum_age):
        for tool, args in [
            ("trivy", ["trivy", "--version", "--format", "json"]),
            ("syft", ["syft", "version", "-o", "json"]),
            ("grype", ["grype", "version", "-o", "json"]),
        ]:
            value = self.json_command(args, f"{tool}-version")
            self.versions[tool] = value.get("version") or value.get("Version") or "unknown"
            if self.versions[tool] == "unknown":
                self.issues.append(f"{tool}: version could not be identified")
        for label, args in [
            ("trivy-db", ["trivy", "image", "--config", "", "--download-db-only", "--no-progress", "--disable-telemetry"]),
            ("trivy-java-db", ["trivy", "image", "--config", "", "--download-java-db-only", "--no-progress", "--disable-telemetry"]),
            ("grype-db", ["grype", "-c", str(self.grype_config), "db", "update"]),
        ]:
            stage = self.command(args, self.directory, label)
            self.setup[label] = stage
            if stage["status"] != "complete":
                self.issues.append(f"{label}: refresh failed; any cached results are degraded")
            self.issues.extend(warning_issues(self.directory, label))
        databases = self.metadata("before")
        java_index = databases["trivy"]["java_index"]
        for tool, value in [*databases.items(), ("trivy-java", java_index if isinstance(java_index, dict) else {})]:
            issue = database_issue(value, maximum_age, tool)
            if issue:
                self.issues.append(issue)
        return databases

    def trivy(self, image, directory):
        stages = image["stages"]
        stages["trivy"] = self.command(
            [
                "trivy",
                "image",
                "--config",
                "",
                "--docker-host",
                self.endpoint,
                "--image-src",
                "docker",
                "--scanners",
                "vuln",
                "--format",
                "json",
                "--list-all-pkgs",
                "--severity",
                "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
                "--ignore-unfixed=false",
                "--ignorefile",
                "",
                "--exit-code",
                "0",
                "--timeout",
                f"{self.timeout}s",
                "--skip-db-update",
                "--skip-java-db-update",
                "--offline-scan",
                "--disable-telemetry",
                "--skip-version-check",
                "--no-progress",
                "--output",
                str(directory / "trivy.json"),
                image["id"],
            ],
            directory,
            "trivy",
        )
        report = validate_json_stage(stages["trivy"], directory / "trivy.json", lambda v: native_trivy(v, image["id"]))
        if report is not None:
            stages["trivy-cyclonedx"] = self.command(
                [
                    "trivy",
                    "convert",
                    "--config",
                    "",
                    "--format",
                    "cyclonedx",
                    "--ignorefile",
                    "",
                    "--output",
                    str(directory / "trivy.cdx.json"),
                    str(directory / "trivy.json"),
                ],
                directory,
                "trivy-cyclonedx",
            )
            validate_json_stage(stages["trivy-cyclonedx"], directory / "trivy.cdx.json", lambda v: v.get("bomFormat") == "CycloneDX")
        image["coverage"].extend(warning_issues(directory, "trivy"))
        return report

    def cache_identity(self, image):
        return {"schema": 1, "image": image["id"], "platform": image.get("platform"), "syft": self.versions["syft"], "settings": SYFT_SETTINGS}

    def cached_sbom(self, cache, identity):
        try:
            if cache.is_symlink():
                return False
            manifest = read_json(cache / "manifest.json")
            return (
                manifest["identity"] == identity
                and all(
                    not (cache / name).is_symlink() and file_digest(cache / name) == manifest["hashes"][name]
                    for name in ("syft.json", "syft.cdx.json")
                )
                and native_sbom(read_json(cache / "syft.json"), identity["image"], identity["platform"])
                and read_json(cache / "syft.cdx.json").get("bomFormat") == "CycloneDX"
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def publish_cache(self, cache, identity, directory):
        cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = cache.with_name(cache.name + ".new-" + uuid.uuid4().hex)
        temporary.mkdir(mode=0o700)
        for name in ("syft.json", "syft.cdx.json"):
            shutil.copyfile(directory / name, temporary / name)
        write_json(
            temporary / "manifest.json",
            {
                "identity": identity,
                "hashes": {name: file_digest(temporary / name) for name in ("syft.json", "syft.cdx.json")},
            },
        )
        if cache.exists() or cache.is_symlink():
            cache.rename(cache.with_name(cache.name + ".invalid-" + uuid.uuid4().hex))
        temporary.rename(cache)

    def syft(self, image, directory):
        started = time.monotonic()
        identity = self.cache_identity(image)
        cache = self.root / "cache" / "syft" / digest(identity)
        reusable = self.versions["syft"] != "unknown" and self.cached_sbom(cache, identity)
        if reusable:
            for name in ("syft.json", "syft.cdx.json"):
                shutil.copyfile(cache / name, directory / name)
            image["stages"]["syft"] = {"status": "complete", "cached": True, "seconds": time.monotonic() - started}
        else:
            stage = self.command(
                [
                    "syft",
                    "scan",
                    "-c",
                    str(self.syft_config),
                    "--from",
                    "docker",
                    image["id"],
                    "-o",
                    "syft-json=" + str(directory / "syft.json"),
                    "-o",
                    "cyclonedx-json=" + str(directory / "syft.cdx.json"),
                ],
                directory,
                "syft",
            )
            image["stages"]["syft"] = stage
            native = validate_json_stage(stage, directory / "syft.json", lambda v: native_sbom(v, image["id"], image.get("platform")))
            cdx = validate_json_stage(stage, directory / "syft.cdx.json", lambda v: v.get("bomFormat") == "CycloneDX")
            if native is None or cdx is None:
                return None
            issues = warning_issues(directory, "syft")
            image["coverage"].extend(issues)
            if self.versions["syft"] != "unknown" and not issues:
                self.publish_cache(cache, identity, directory)
        return read_json(directory / "syft.json")

    def grype(self, image, directory):
        stage = self.command(
            [
                "grype",
                "-c",
                str(self.grype_config),
                "sbom:" + str(directory / "syft.json"),
                "-o",
                "json",
                "--file",
                str(directory / "grype.json"),
            ],
            directory,
            "grype",
        )
        image["stages"]["grype"] = stage
        report = validate_json_stage(stage, directory / "grype.json", lambda v: isinstance(v, dict) and isinstance(v.get("matches"), list))
        image["coverage"].extend(warning_issues(directory, "grype"))
        return report
