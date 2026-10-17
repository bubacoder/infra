"""Destroy AWS bootstrap through Terraform, then remove owned DNS and local files."""

import copy
import json
import shutil
from pathlib import Path

import yaml

from . import aws, dns
from .core import ROOT, AwsPlan, BootstrapConfig, BootstrapError, RepositoryConfig, Runner
from .deploy import atomic_write

DATA_VOLUME_OVERRIDE = 'resource "aws_ebs_volume" "data" {\n  lifecycle {\n    prevent_destroy = false\n  }\n}\n'


def remove_inventory_host(text: str, name: str, address: str | None) -> str:
    """Remove this host's entries without reformatting other inventory content."""
    try:
        document = yaml.safe_load(text) or {}
        tree = yaml.compose(text)
        expected = copy.deepcopy(document)
        lines, edits = text.splitlines(keepends=True), []
        for group_key, group in tree.value:
            if group_key.value not in {"debian", "docker_hosts"}:
                continue
            for hosts_key, hosts in group.value:
                if hosts_key.value != "hosts" or name not in (document[group_key.value].get("hosts") or {}):
                    continue
                if not isinstance(hosts, yaml.MappingNode) or hosts.flow_style:
                    raise BootstrapError("Review inline/aliased inventory entries before teardown")
                actual = document[group_key.value]["hosts"][name] or {}
                if actual.get("ansible_host", address) != address:
                    raise BootstrapError("Inventory hostname points to another host; teardown cancelled")
                expected[group_key.value]["hosts"].pop(name)
                for index, (key, value) in enumerate(hosts.value):
                    if key.value == name:
                        end = (
                            hosts.value[index + 1][0].start_mark.line
                            if index + 1 < len(hosts.value)
                            else value.end_mark.line + bool(value.end_mark.column)
                        )
                        comments = "".join(line for line in lines[key.start_mark.line : end] if line.lstrip().startswith("#"))
                        replacement = comments + (" " * key.start_mark.column + "{}\n" if len(hosts.value) == 1 else "")
                        edits.append((key.start_mark.line, end, replacement))
        for start, end, replacement in sorted(edits, reverse=True):
            lines[start:end] = [replacement] if replacement else []
        result = "".join(lines)
        if yaml.safe_load(result) != expected:
            raise BootstrapError("Inventory edit would change unrelated settings; review it manually")
    except (yaml.YAMLError, AttributeError, TypeError, KeyError):
        raise BootstrapError("Cannot safely edit inventory; review it before teardown") from None
    return result


def remove_generated_files(directory: Path, names: tuple[str, ...]) -> None:
    """Delete known generated files, preserving additional operator content."""
    if not directory.exists():
        return
    for name in names:
        (directory / name).unlink(missing_ok=True)
    if not any(directory.iterdir()):
        directory.rmdir()
    else:
        print("Additional operator files outside the generated runtime were preserved.")


def destroy(  # noqa: PLR0913
    config: BootstrapConfig,
    runner: Runner,
    *,
    delete_data: bool = False,
    dry_run: bool = False,
    assume_yes: bool = False,
    root: Path = ROOT,
) -> None:
    """Use the original Terraform backend; retain evidence on every failure."""
    if config.target != "aws":
        raise BootstrapError("Automated teardown supports AWS only")
    if not delete_data:
        raise BootstrapError("Full teardown deletes both disks; explicit DELETE_DATA=1 / --delete-data is required")
    directory = root / "config/terraform/bootstrap" / config.vm.name
    docker = root / "config/docker" / config.vm.name
    dns_dir = root / "config/bootstrap-dns" / config.vm.name
    inventory = root / "config/ansible/inventory/inventory.yaml"
    for path in (directory / "runtime/terraform.tfstate", docker, dns_dir, inventory):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise BootstrapError("Teardown refuses symlink deployment paths")
    if not (directory / "runtime/terraform.tfstate").is_file():
        raise BootstrapError("Deployment state is missing; recover it before teardown")
    with aws.deployment_lock(config, root), dns.journal_lock(config, root):
        manifest = aws.read_manifest(directory) or {}
        identity = manifest.get("identity", {})
        settings = identity.get("aws", {})
        if (identity.get("name"), settings.get("account_id"), settings.get("region")) != (config.vm.name, config.aws.account_id, config.aws.region):
            raise BootstrapError("Teardown hostname/account/region differs from the deployment manifest")
        original = inventory.read_text() if inventory.exists() else None
        updated = remove_inventory_host(original, config.vm.name, manifest.get("public_ip")) if original is not None else None
        plan = AwsPlan(config, RepositoryConfig("", "", ""), directory, manifest.get("ami_id", ""))
        override = directory / "runtime/bootstrap_destroy_override.tf"
        if override.exists() or override.is_symlink():
            raise BootstrapError("A teardown override remains; inspect it before retrying")
        aws.verify_identity(config, runner)
        try:
            # Terraform's override mechanism changes only the generated runtime;
            # the tracked template and all its other lifecycle rules stay intact.
            atomic_write(override, DATA_VOLUME_OVERRIDE)
            aws.terraform(plan, runner, ["init", "-input=false"])
            aws.terraform(
                plan, runner, ["plan", "-destroy", "-input=false", "-lock-timeout=30s", "-var-file=bootstrap.tfvars.json", "-out=teardown.tfplan"]
            )
            document = json.loads(aws.terraform(plan, runner, ["show", "-json", "teardown.tfplan"]))
            if not isinstance(document.get("format_version"), str):
                raise BootstrapError("Terraform returned an invalid destroy plan; nothing was applied")
            changes = [r for r in document.get("resource_changes", []) if r.get("mode") == "managed"]
            if any(r["change"]["actions"] not in (["delete"], ["no-op"]) for r in changes):
                raise BootstrapError("Destroy plan contains non-deletion changes; nothing was applied")
            print(f"Destroy AWS deployment {config.vm.name}: account {config.aws.account_id}, region {config.aws.region}")
            for resource in changes:
                if resource["change"]["actions"] == ["delete"]:
                    print(f"  delete: {resource['address']}")
            dns.cleanup(config, root=root)
            print("Also remove this host's generated Docker files, inventory entries and Terraform runtime/state/backups.")
            print("Both disks and their data will be deleted. Bootstrap YAML, SSH keys and unrelated configuration are preserved.")
            if dry_run:
                print("Preview only. No AWS or DNS resources changed.")
                return
            if not assume_yes and input("Destroy this deployment and its data? [y/N] ").strip().lower() not in {"y", "yes"}:
                raise BootstrapError("Teardown cancelled")
            aws.terraform(plan, runner, ["apply", "-input=false", "-lock-timeout=30s", "teardown.tfplan"])
            state = json.loads(aws.terraform(plan, runner, ["show", "-json"]))
            if not isinstance(state.get("format_version"), str):
                raise BootstrapError("Terraform state could not be verified; local files were retained")
            if any(r.get("mode") == "managed" for r in aws.state_resources(state)):
                raise BootstrapError("Terraform still manages resources; state and local files were retained")
            dns.cleanup(config, execute=True, root=root)
        finally:
            override.unlink(missing_ok=True)
        if (inventory.read_text() if inventory.exists() else None) != original:
            raise BootstrapError("Inventory changed during teardown; local artifacts were retained")
        if original is not None and updated != original:
            atomic_write(inventory, updated)
        remove_generated_files(docker, (".env", ".env.traefik", "services.yaml"))
        remove_generated_files(dns_dir, ("journal.json", ".lock"))
        shutil.rmtree(directory)
        print("Teardown completed. Terraform resources, owned DNS and generated deployment files removed.")
