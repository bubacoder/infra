"""Offline regressions for independent scanners, inventory reuse and reporting."""

# This repository runs unittest, not pytest.
# ruff: noqa: PT009, PT027

import argparse
import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from container_scan import common, findings, inventory, policy, reporting, runner, scanners  # noqa: E402


def snapshot():
    return {
        "target": {"context": "test", "endpoint": "unix:///docker.sock", "daemon_id": "daemon-one"},
        "issues": [],
        "images": [{"id": "sha256:one", "platform": "amd64", "containers": [{"name": "adminer"}], "stages": {}, "coverage": []}],
    }


class InventoryTests(unittest.TestCase):
    def command(self, args):
        if args[1:3] == ["context", "show"]:
            return "default"
        if args[1:3] == ["context", "inspect"]:
            return "unix:///docker.sock"
        if args[1] == "info":
            return "daemon-one"
        if args[1] == "ps":
            return "\n".join(
                json.dumps(row)
                for row in [
                    {"id": "abc123", "name": "first", "reference": "app:latest"},
                    {"id": "abc456", "name": "second", "reference": "app:latest"},
                ]
            )
        if args[1] == "inspect":
            return "sha256:shared"
        if args[1:3] == ["image", "inspect"]:
            return '{"platform":"amd64","digests":[]}'
        self.fail(f"Unexpected command: {args}")

    def test_deduplicates_actual_ids(self):
        with patch.object(inventory, "run", side_effect=self.command), patch.dict("os.environ", {}, clear=True):
            result = inventory.inventory()
        self.assertEqual(len(result["images"]), 1)
        self.assertEqual(len(result["images"][0]["containers"]), 2)

    def test_selection_exact_and_ambiguous_prefix(self):
        with patch.object(inventory, "run", side_effect=self.command), patch.dict("os.environ", {}, clear=True):
            result = inventory.inventory("second")
            with self.assertRaises(ValueError):
                inventory.inventory("abc")
        self.assertEqual(result["images"][0]["containers"][0]["name"], "second")

    def test_missing_image_preserves_inventory(self):
        def command(args):
            if args[1:3] == ["image", "inspect"]:
                raise subprocess.CalledProcessError(1, args)
            return self.command(args)

        with patch.object(inventory, "run", side_effect=command), patch.dict("os.environ", {}, clear=True):
            result = inventory.inventory()
        self.assertIn("inventory_error", result["images"][0])

    def test_remote_target_rejected_without_printing_credentials(self):
        with (
            patch.object(inventory, "run", side_effect=self.command),
            patch.dict("os.environ", {"DOCKER_HOST": "ssh://secret@host"}, clear=True),
            self.assertRaisesRegex(ValueError, "Unix-socket") as error,
        ):
            inventory.target()
        self.assertNotIn("secret", str(error.exception))

    def test_disappearing_container_does_not_abort_others(self):
        def command(args):
            if args[1] == "inspect" and args[-1] == "abc123":
                raise subprocess.CalledProcessError(1, args)
            return self.command(args)

        with patch.object(inventory, "run", side_effect=command), patch.dict("os.environ", {}, clear=True):
            result = inventory.inventory()
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["images"][0]["containers"][0]["name"], "second")


class FakeTools:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.empty = False
        self.warning = ""
        self.syft_version = "1.55.0"
        self.stamp = datetime.now(UTC).isoformat()
        self.java_metadata = {"UpdatedAt": self.stamp}
        self.php_version = "8.4.26"
        self.platform = "amd64"
        self.advisories = ["CVE-2026-109618", "CVE-2026-109619"]

    def execute(self, args, directory, label, **kwargs):
        self.calls.append(label)
        directory.mkdir(parents=True, exist_ok=True)
        out = directory / f"{label}.stdout.log"
        err = directory / f"{label}.stderr.log"
        out.write_text("")
        err.write_text(self.warning if label == "trivy" else "")
        if self.failure == label:
            err.write_text("secret must not appear in summary")
            return {"status": "failed", "error": "Mock failure; see private logs", "seconds": 1}
        value = None
        if label.startswith("trivy-metadata") or label == "trivy-version":
            value = {"Version": "0.76.1", "VulnerabilityDB": {"UpdatedAt": self.stamp}, "JavaDB": self.java_metadata}
        elif label.startswith("grype-metadata"):
            value = {"valid": True, "built": self.stamp}
        elif label == "syft-version":
            value = {"version": self.syft_version}
        elif label == "grype-version":
            value = {"version": "0.121.0"}
        elif label == "trivy":
            data = {"SchemaVersion": 2, "ArtifactName": args[-1], "Metadata": {}}
            if not self.empty:
                data["Results"] = [{"Type": "alpine", "Packages": [{"Name": "openssl", "Version": "3.5.8"}]}]
            Path(args[args.index("--output") + 1]).write_text(json.dumps(data))
        elif label == "trivy-cyclonedx":
            Path(args[args.index("--output") + 1]).write_text('{"bomFormat":"CycloneDX"}')
        elif label == "syft":
            image = args[args.index("--from") + 2]
            data = {
                "source": {"type": "image", "metadata": {"imageID": image, "userInput": image, "architecture": self.platform}},
                "artifacts": []
                if self.empty
                else [{"name": "php-cli", "version": self.php_version, "type": "binary", "purl": "pkg:generic/php-cli@" + self.php_version}],
            }
            for arg in args:
                if arg.startswith("syft-json="):
                    Path(arg.split("=", 1)[1]).write_text(json.dumps(data))
                if arg.startswith("cyclonedx-json="):
                    Path(arg.split("=", 1)[1]).write_text('{"bomFormat":"CycloneDX"}')
        elif label == "grype":
            data = {
                "matches": [
                    {
                        "vulnerability": {"id": identifier, "severity": "Critical", "fix": {"versions": ["8.2.35", "8.4.27"]}},
                        "artifact": {"name": "php-cli", "version": self.php_version, "type": "binary"},
                    }
                    for identifier in self.advisories
                ]
            }
            Path(args[args.index("--file") + 1]).write_text(json.dumps(data))
        if value is not None:
            out.write_text(json.dumps(value))
        return {"status": "complete", "seconds": 1, "returncode": 0}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tools = FakeTools()
        self.policy_path = self.root / "policy.json"
        self.settings = {"version": 1, "database_max_age_hours": 72, "expected_components": {"adminer": ["php-cli"]}, "triage": []}
        common.write_json(self.policy_path, self.settings)

    def invoke(self, *, data=None, fail_on=None):
        args = argparse.Namespace(container=None, output=self.root / "reports", policy=self.policy_path, timeout=10, fail_on=fail_on)
        with (
            patch.object(runner, "inventory", return_value=copy.deepcopy(data or snapshot())),
            patch.object(scanners, "execute", side_effect=self.tools.execute),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = runner.scan(args)
        target_dir = args.output / common.target_key((data or snapshot())["target"])
        pointer = common.read_json(target_dir / "latest.json")
        directory = target_dir / "runs" / pointer["run"]
        return code, common.read_json(directory / "inventory.json"), directory

    def test_both_php_cves_and_applicable_fix_reported(self):
        code, report, directory = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual({f["id"] for f in report["images"][0]["findings"]}, set(self.tools.advisories))
        self.assertIn("8.4.27", (directory / "summary.md").read_text())
        self.assertNotIn("8.2.35", (directory / "summary.md").read_text())
        self.assertTrue((directory / "findings.csv").exists())

    def test_sbom_reused_but_both_matchers_run_again(self):
        self.invoke()
        self.tools.calls.clear()
        code, report, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertNotIn("syft", self.tools.calls)
        self.assertIn("trivy", self.tools.calls)
        self.assertIn("grype", self.tools.calls)
        self.assertIn("grype-db", self.tools.calls)
        self.assertTrue(report["images"][0]["stages"]["syft"]["cached"])

    def test_syft_version_invalidates_inventory(self):
        self.invoke()
        self.tools.calls.clear()
        self.tools.syft_version = "1.56.0"
        self.invoke()
        self.assertIn("syft", self.tools.calls)

    def test_cataloger_settings_invalidate_inventory(self):
        self.invoke()
        self.tools.calls.clear()
        with patch.object(scanners, "SYFT_SETTINGS", scanners.SYFT_SETTINGS + "# changed\n"):
            self.invoke()
        self.assertIn("syft", self.tools.calls)

    def test_image_id_invalidates_inventory(self):
        self.invoke()
        self.tools.calls.clear()
        data = snapshot()
        data["images"][0]["id"] = "sha256:new"
        self.invoke(data=data)
        self.assertIn("syft", self.tools.calls)

    def test_corrupt_cache_is_preserved_and_regenerated(self):
        self.invoke()
        cached = next((self.root / "reports/cache/syft").glob("*/syft.json"))
        cached.write_text("corrupt")
        self.tools.calls.clear()
        code, _, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn("syft", self.tools.calls)
        self.assertTrue(list((self.root / "reports/cache/syft").glob("*.invalid-*")))

    def test_missing_images_do_not_abort_other_images(self):
        data = snapshot()
        data["images"].append(
            {"id": "sha256:missing", "containers": [{"name": "missing"}], "stages": {}, "coverage": [], "inventory_error": "Image missing"}
        )
        code, report, _ = self.invoke(data=data)
        self.assertEqual(code, 2)
        self.assertEqual(report["images"][0]["status"], "complete")
        self.assertEqual(report["images"][1]["status"], "unscannable")

    def test_one_failed_scanner_does_not_stop_other_pipeline(self):
        self.tools.failure = "trivy"
        code, report, directory = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("grype", self.tools.calls)
        self.assertEqual(len(report["images"][0]["findings"]), 2)
        self.assertNotIn("secret", (directory / "summary.md").read_text())

    def test_empty_inventory_and_expected_runtime_are_not_clean(self):
        self.tools.empty = True
        code, report, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertTrue(any("expected runtime absent" in issue for issue in report["images"][0]["coverage"]))
        self.assertTrue(any("no packages detected" in issue for issue in report["images"][0]["coverage"]))

    def test_warnings_visible_and_do_not_prevent_sbom_caching(self):
        self.tools.warning = "WARN Unable to get vulnerability details\n"
        code, _, directory = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("advisory details missing", (directory / "summary.md").read_text())
        self.tools.calls.clear()
        self.invoke()
        self.assertNotIn("syft", self.tools.calls)

    def test_stale_database_marks_run_incomplete(self):
        self.tools.stamp = "2000-01-01T00:00:00Z"
        code, report, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertTrue(any("freshness" in i for i in report["issues"]))

    def test_database_refresh_failure_still_produces_degraded_results(self):
        self.tools.failure = "grype-db"
        code, report, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("grype", self.tools.calls)
        self.assertTrue(any("refresh failed" in i for i in report["issues"]))

    def test_invalid_java_index_cannot_pass_coverage_or_replace_baseline(self):
        _, original, _ = self.invoke()
        for metadata in (None, {}, {"UpdatedAt": "2000-01-01T00:00:00Z"}, {"UpdatedAt": "invalid"}):
            with self.subTest(metadata=metadata):
                self.tools.java_metadata = metadata
                code, report, _ = self.invoke()
                self.assertEqual(code, 2)
                self.assertTrue(any("trivy-java" in issue for issue in report["issues"]))
                self.assertEqual(report["changes"][0]["status"], "not_compared")
                state = common.read_json(self.root / "reports" / common.target_key(snapshot()["target"]) / "state.json")
                self.assertEqual(state["containers"]["adminer"]["run"], original["run"])

    def test_changes_and_still_vulnerable_upgrade(self):
        self.invoke()
        self.tools.php_version = "8.4.25"
        _, report, _ = self.invoke()
        self.assertEqual(report["changes"][0]["new"], [])
        self.assertEqual(report["changes"][0]["no_longer_reported"], [])
        self.tools.advisories = []
        _, report, _ = self.invoke()
        self.assertEqual(len(report["changes"][0]["no_longer_reported"]), 2)

    def test_partial_run_does_not_resolve_or_replace_baseline(self):
        _, original, _ = self.invoke()
        self.tools.failure = "grype"
        code, report, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(report["changes"][0]["status"], "not_compared")
        state = common.read_json(self.root / "reports" / common.target_key(snapshot()["target"]) / "state.json")
        self.assertEqual(state["containers"]["adminer"]["run"], original["run"])

    def test_vulnerability_gate_is_opt_in(self):
        code, _, _ = self.invoke(fail_on="CRITICAL")
        self.assertEqual(code, 1)

    def test_expiring_scoped_triage_and_gate(self):
        rule = {
            "container": "adminer",
            "component": "generic/php-cli",
            "advisory": "CVE-2026-109618",
            "reason": "Test assessment",
            "evidence": "https://example.org/advisory",
            "expires": "2099-01-01",
        }
        self.settings["triage"] = [{**rule, "advisory": advisory} for advisory in self.tools.advisories]
        common.write_json(self.policy_path, self.settings)
        code, _, _ = self.invoke(fail_on="CRITICAL")
        self.assertEqual(code, 0)
        self.settings["triage"][0]["expires"] = "2000-01-01"
        common.write_json(self.policy_path, self.settings)
        code, report, _ = self.invoke(fail_on="CRITICAL")
        self.assertEqual(code, 2)
        self.assertTrue(report["gate_failed"])

    def test_corrupt_history_is_preserved(self):
        self.invoke()
        state = self.root / "reports" / common.target_key(snapshot()["target"]) / "state.json"
        state.write_text("broken recovery data")
        code, _, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(state.read_text(), "broken recovery data")

    def test_other_stage_failures_cannot_advance_history(self):
        for label in ("syft", "grype", "trivy-cyclonedx"):
            with self.subTest(label=label):
                self.tools.failure = label
                data = snapshot()
                data["images"][0]["id"] = "sha256:" + label
                code, report, _ = self.invoke(data=data)
                self.assertEqual(code, 2)
                self.assertEqual(report["changes"][0]["status"], "not_compared")

    def test_platform_change_invalidates_sbom(self):
        self.invoke()
        self.tools.calls.clear()
        data = snapshot()
        data["images"][0]["platform"] = "arm64"
        self.tools.platform = "arm64"
        self.invoke(data=data)
        self.assertIn("syft", self.tools.calls)

    def test_interrupted_scan_has_partial_report_without_resolutions(self):
        self.invoke()
        args = argparse.Namespace(container=None, output=self.root / "reports", policy=self.policy_path, timeout=10, fail_on=None)
        with (
            patch.object(runner, "inventory", return_value=snapshot()),
            patch.object(scanners, "execute", side_effect=self.tools.execute),
            patch.object(runner, "scan_image", side_effect=KeyboardInterrupt),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = runner.scan(args)
        self.assertEqual(code, 2)
        target_dir = args.output / common.target_key(snapshot()["target"])
        pointer = common.read_json(target_dir / "latest.json")
        report = common.read_json(target_dir / "runs" / pointer["run"] / "inventory.json")
        self.assertEqual(report["changes"][0]["status"], "not_compared")
        self.assertTrue(any("interrupted" in i for i in report["issues"]))

    def test_latest_report_uses_current_daemon(self):
        self.invoke()
        with patch.object(runner, "target", return_value=snapshot()["target"]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.show_report(self.root / "reports"), 0)
        self.assertIn("Investigate first", output.getvalue())
        other = {**snapshot()["target"], "daemon_id": "another-daemon"}
        with patch.object(runner, "target", return_value=other), self.assertRaises(FileNotFoundError):
            runner.show_report(self.root / "reports")

    def test_scoped_exception_cannot_hide_another_container_sharing_image(self):
        data = snapshot()
        data["images"][0]["containers"].append({"name": "other"})
        self.settings["triage"] = [
            {
                "container": "adminer",
                "component": "generic/php-cli",
                "advisory": advisory,
                "reason": "Test assessment",
                "evidence": "https://example.org/advisory",
                "expires": "2099-01-01",
            }
            for advisory in self.tools.advisories
        ]
        common.write_json(self.policy_path, self.settings)
        code, report, _ = self.invoke(data=data, fail_on="CRITICAL")
        self.assertEqual(code, 1)
        self.assertTrue(report["gate_failed"])


class NormalizationTests(unittest.TestCase):
    def test_single_finding_preserves_scanner_severity_disagreement(self):
        trivy = {
            "Results": [
                {
                    "Type": "generic",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-1",
                            "PkgName": "php-cli",
                            "InstalledVersion": "8.4.26",
                            "Severity": "HIGH",
                            "FixedVersion": "8.4.27",
                        }
                    ],
                }
            ]
        }
        grype = {
            "matches": [
                {
                    "vulnerability": {"id": "GHSA-abcd-ef12-gh34", "severity": "Critical"},
                    "relatedVulnerabilities": [{"id": "CVE-2026-1"}],
                    "artifact": {"name": "php-cli", "version": "8.4.26", "type": "binary"},
                }
            ]
        }
        result = findings.combine(trivy, grype)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["scanners"], ["grype", "trivy"])
        self.assertEqual(result[0]["severities"], {"trivy": ["HIGH"], "grype": ["CRITICAL"]})

    def test_vendor_bulletin_does_not_merge_different_cves(self):
        aliases = findings.Aliases()
        aliases.join(["CVE-2026-1", "DSA-1000-1"])
        aliases.join(["CVE-2026-2", "DSA-1000-1"])
        self.assertNotEqual(aliases.find("CVE-2026-1"), aliases.find("CVE-2026-2"))

    def test_explicit_cve_ghsa_aliases_merge(self):
        aliases = findings.Aliases()
        aliases.join(["CVE-2026-1", "GHSA-abcd-ef12-gh34"])
        self.assertEqual(aliases.find("CVE-2026-1"), aliases.find("GHSA-abcd-ef12-gh34"))

    def test_go_python_and_debian_versions(self):
        self.assertEqual(findings.component("stdlib", "v1.20.5", "", "golang"), findings.component("stdlib", "go1.20.5", "", "golang"))
        self.assertEqual(findings.component("Typing_Extensions", "4", "", "pypi"), findings.component("typing-extensions", "4", "", "pypi"))
        self.assertEqual(findings.component("a", "1", "pkg:deb/debian/a@1-2?epoch=1", ""), ("deb/debian/a", "1:1-2"))

    def test_fix_suggestion_never_selects_old_php_branch(self):
        self.assertEqual(findings.fix_suggestion("8.4.26", ["8.2.35", "8.3.36", "8.4.27"]), "8.4.27")
        self.assertIsNone(findings.fix_suggestion("8.4.26", ["8.2.35", "8.5.12"]))

    def test_alias_added_between_runs_does_not_create_false_resolution(self):
        before = [{"id": "GHSA-abcd-ef12-gh34", "aliases": ["GHSA-abcd-ef12-gh34"], "component": "npm/test"}]
        after = [{"id": "CVE-2026-1", "aliases": ["GHSA-abcd-ef12-gh34", "CVE-2026-1"], "component": "npm/test"}]
        self.assertEqual(findings.changed(before, after), {"new": [], "no_longer_reported": []})


class SafetyTests(unittest.TestCase):
    def test_native_trivy_zero_packages_omits_results_but_is_valid(self):
        value = {"SchemaVersion": 2, "ArtifactName": "sha256:test", "Metadata": {}}
        self.assertTrue(scanners.native_trivy(value, "sha256:test"))
        self.assertFalse(scanners.native_trivy(value, "sha256:other"))
        self.assertFalse(scanners.native_trivy({}, "sha256:test"))

    def test_native_sbom_handles_containerd_repository_vs_config_digest(self):
        value = {
            "source": {
                "type": "image",
                "metadata": {"imageID": "sha256:config", "userInput": "sha256:index", "repoDigests": ["adminer@sha256:index"]},
            },
            "artifacts": [],
        }
        self.assertTrue(scanners.native_sbom(value, "sha256:index"))
        self.assertFalse(scanners.native_sbom(value, "sha256:other"))

    def test_lock_prevents_overlapping_runs(self):
        with tempfile.TemporaryDirectory() as root, common.scan_lock(Path(root)), self.assertRaises(RuntimeError), common.scan_lock(Path(root)):
            self.fail("Second scan acquired the lock")

    def test_timeout_keeps_private_logs(self):
        with tempfile.TemporaryDirectory() as root:
            result = common.execute([sys.executable, "-c", "import time; time.sleep(30)"], Path(root), "timeout", timeout=0.05)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "Command timed out")
            self.assertTrue((Path(root) / "timeout.stage.json").exists())

    def test_scanner_environment_removes_hidden_tool_settings(self):
        with patch.dict("os.environ", {"TRIVY_IGNORE_UNFIXED": "true", "GRYPE_IGNORE": "something", "DOCKER_CONTEXT": "other"}):
            env = common.scanner_environment("unix:///chosen.sock")
        self.assertNotIn("TRIVY_IGNORE_UNFIXED", env)
        self.assertNotIn("GRYPE_IGNORE", env)
        self.assertNotIn("DOCKER_CONTEXT", env)
        self.assertEqual(env["DOCKER_HOST"], "unix:///chosen.sock")

    def test_invalid_json_is_a_failed_stage(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "report.json"
            path.write_text("[]")
            stage = {"status": "complete"}
            self.assertIsNone(common.validate_json_stage(stage, path, lambda v: v.get("Results") is not None))
            self.assertEqual(stage["status"], "failed")

    def test_database_metadata_must_be_fresh_and_valid(self):
        self.assertIsNotNone(common.database_issue({}, 72, "test"))
        self.assertIsNotNone(common.database_issue({"built": "2000-01-01T00:00:00Z"}, 72, "test"))
        self.assertIsNone(common.database_issue({"built": datetime.now(UTC).isoformat(), "valid": True}, 72, "test"))

    def test_policy_rejects_unexplained_exception(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "policy.json"
            common.write_json(path, {"version": 1, "database_max_age_hours": 72, "triage": [{"advisory": "CVE-2026-1"}]})
            with self.assertRaises(ValueError):
                policy.load_policy(path)

    def test_markdown_cannot_inject_a_table_row(self):
        self.assertEqual(reporting.escape("name|value\nnew"), "name\\|value new")


if __name__ == "__main__":
    unittest.main()
