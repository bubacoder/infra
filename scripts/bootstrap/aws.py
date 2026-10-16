"""AWS target using the canonical Terraform template and trusted SSM discovery."""

import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import tempfile
import time
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path

import yaml

from .config import detect_repository
from .core import ROOT, AwsPlan, BootstrapConfig, BootstrapError, Runner, private_key_for, vm_ssh_command
from .deploy import atomic_write, configure_host, deploy_services, prepare_remote_repository, render_config, verify_services
from .network import verify_dns


@contextlib.contextmanager
def deployment_lock(config: BootstrapConfig, root: Path = ROOT) -> Iterator[Path]:
    """Lock the whole workflow, not just individual Terraform operations."""
    directory = root / "config/terraform/bootstrap" / config.vm.name
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    descriptor = os.open(directory / ".bootstrap.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BootstrapError("Another bootstrap operation holds this deployment lock") from error
        yield directory
    finally:
        os.close(descriptor)


def environment(config: BootstrapConfig, directory: Path) -> dict[str, str]:
    """Use the credential chain, but isolate Terraform CLI inputs and state."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("TF_")}
    env.update(
        AWS_DEFAULT_REGION=config.aws.region,
        AWS_REGION=config.aws.region,
        AWS_PAGER="",
        AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true",
        TF_IN_AUTOMATION="1",
        TF_INPUT="0",
        TF_WORKSPACE="default",
        TF_DATA_DIR=str(directory / "runtime/.terraform"),
    )
    if config.aws.profile:
        env["AWS_PROFILE"] = config.aws.profile
    return env


def aws_command(config: BootstrapConfig, runner: Runner, arguments: list[str], *, timeout: int = 30) -> dict:
    """Parse AWS JSON without exposing credential-bearing errors or command output."""
    if any(key.startswith("AWS_ENDPOINT_URL") for key in os.environ):
        raise BootstrapError("AWS endpoint overrides are not supported by bootstrap")
    try:
        result = runner.run(
            ["aws", "--region", config.aws.region, "--output", "json", *arguments],
            capture=True,
            timeout=timeout,
            env=environment(config, config.source.parent),
        )
        document = json.loads(result) if result.strip() else {}
    except (BootstrapError, json.JSONDecodeError) as error:
        raise BootstrapError(f"AWS {arguments[0]} {arguments[1]} failed; check credentials, permissions, and connectivity") from error
    if not isinstance(document, dict):
        raise BootstrapError("AWS returned an unexpected response shape")
    return document


def terraform(plan: AwsPlan, runner: Runner, arguments: list[str], *, timeout: int = 1200) -> str:
    """Capture Terraform output privately; never emit raw state or plan JSON."""
    try:
        result = runner.run(
            ["terraform", *arguments], cwd=plan.directory / "runtime", capture=True, timeout=timeout, env=environment(plan.config, plan.directory)
        )
    except BootstrapError as error:
        raise BootstrapError(
            f"Terraform {arguments[0]} failed; resources may remain. Inspect private state in {plan.directory} and rerun bootstrap"
        ) from error
    finally:
        for pattern in ("terraform.tfstate*", "*.tfplan"):
            for path in (plan.directory / "runtime").glob(pattern):
                path.chmod(0o600)
    return result


def verify_identity(config: BootstrapConfig, runner: Runner) -> None:
    """Fail closed on the wrong AWS account."""
    identity = aws_command(config, runner, ["sts", "get-caller-identity"])
    if identity.get("Account") != config.aws.account_id:
        raise BootstrapError("Authenticated AWS account does not match aws.account_id")


def verify_ssh_identity(config: BootstrapConfig, runner: Runner) -> None:
    """Check that the private key or agent can authenticate with the supplied key."""
    supplied = config.vm.ssh_public_key.read_text().split()[:2]
    if key := private_key_for(config.vm.ssh_public_key):
        if key.stat().st_mode & 0o077:
            raise BootstrapError("SSH private key must have mode 0600 or stricter")
        try:
            public = runner.run(["ssh-keygen", "-y", "-P", "", "-f", str(key)], capture=True, timeout=10)
            candidates = [public.split()[:2]]
        except BootstrapError:
            # An encrypted private key can still be usable through an SSH agent.
            candidates = [line.split()[:2] for line in runner.run(["ssh-add", "-L"], capture=True, timeout=10).splitlines()]
    else:
        candidates = [line.split()[:2] for line in runner.run(["ssh-add", "-L"], capture=True, timeout=10).splitlines()]
    if supplied not in candidates:
        raise BootstrapError("Supplied SSH public key has no matching usable private key or agent identity")


def template_files(root: Path) -> list[Path]:
    """Allowlist tracked Terraform and cloud-init source, never standalone state."""
    source = root / "terraform/aws-vm"
    return sorted([*source.glob("*.tf"), *source.glob("cloud-init/*.tpl")])


def source_digest(root: Path) -> str:
    """Hash the allowlisted provisioning sources in stable path order."""
    digest = hashlib.sha256()
    for path in template_files(root):
        digest.update(str(path.relative_to(root / "terraform/aws-vm")).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def provision_identity(config: BootstrapConfig, root: Path) -> dict:
    """Freeze guest inputs; changing user data never silently mutates a running VM."""
    aws = asdict(config.aws)
    aws.pop("profile")
    return {
        "aws": aws,
        "name": config.vm.name,
        "username": config.vm.username,
        "public_key": " ".join(config.vm.ssh_public_key.read_text().split()[:2]),
        "template": source_digest(root),
    }


def read_manifest(directory: Path) -> dict | None:
    """Read private deployment metadata, failing closed on invalid content."""
    path = directory / "manifest.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise BootstrapError("Deployment manifest is unreadable; inspect it before retrying") from error
    if not isinstance(value, dict):
        raise BootstrapError("Deployment manifest is invalid")
    return value


def resolve_plan(config: BootstrapConfig, runner: Runner, root: Path = ROOT) -> AwsPlan:
    """Pin the official AMI and bind state to one account, region, and template."""
    for tool in ("git", "task", "ssh", "ssh-keyscan", "ssh-keygen", "rsync", "ansible-playbook", "curl", "aws", "terraform"):
        if shutil.which(tool) is None:
            raise BootstrapError(f"Required executable is not installed: {tool}")
    verify_identity(config, runner)
    verify_ssh_identity(config, runner)
    repository = detect_repository(config, runner, root)
    if repository.url.startswith("git@github.com:"):
        repository = replace(repository, url=f"https://github.com/{repository.url.removeprefix('git@github.com:')}")
    if not repository.url.startswith("https://"):
        raise BootstrapError("AWS bootstrap requires a guest-accessible public HTTPS repository")
    directory = root / "config/terraform/bootstrap" / config.vm.name
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    manifest = read_manifest(directory)
    identity = provision_identity(config, root)
    state_exists = (directory / "runtime/terraform.tfstate").exists()
    if manifest is not None and not manifest.get("apply_started") and not state_exists:
        # A read-only plan must not freeze provisioning inputs or an aging AMI.
        manifest = None
    if manifest is not None:
        if manifest.get("identity") != identity:
            raise BootstrapError("Provisioning inputs or template changed; explicit maintenance is required, not automatic replacement")
        if manifest.get("apply_started") and not state_exists:
            raise BootstrapError("Deployment state is missing after apply began; recover state before retrying")
        ami_id = manifest.get("ami_id", "")
    else:
        if state_exists:
            raise BootstrapError("Unowned Terraform state exists; explicit state migration is required")
        images = aws_command(
            config,
            runner,
            [
                "ec2",
                "describe-images",
                "--owners",
                "099720109477",
                "--filters",
                f"Name=name,Values=ubuntu/images/hvm-ssd-gp3/{config.aws.ubuntu_version}-amd64-server-*",
                "Name=architecture,Values=x86_64",
                "Name=state,Values=available",
            ],
        )
        candidates = images.get("Images", [])
        if not candidates:
            raise BootstrapError("No available official Canonical AMI matches the requested Ubuntu release")
        ami_id = max(candidates, key=lambda image: image["CreationDate"])["ImageId"]
    if not isinstance(ami_id, str) or not re.fullmatch(r"ami-[0-9a-f]+", ami_id):
        raise BootstrapError("Resolved AMI ID is invalid")
    if manifest is None:
        atomic_write(directory / "manifest.json", json.dumps({"identity": identity, "ami_id": ami_id, "apply_started": False}))
    return AwsPlan(config, repository, directory, ami_id)


def render_provisioning(plan: AwsPlan, root: Path = ROOT) -> None:
    """Materialize the canonical template with an isolated private local backend."""
    runtime = plan.directory / "runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    runtime.chmod(0o700)
    sources = {path.relative_to(root / "terraform/aws-vm"): path for path in template_files(root)}
    expected = set(sources) | {Path("backend.tf")}
    # Synchronize generated sources only; state, plans, and caches stay untouched.
    for pattern in ("*.tf", "cloud-init/*.tpl"):
        for path in runtime.glob(pattern):
            if path.relative_to(runtime) not in expected:
                path.unlink()
    for relative, path in sources.items():
        if relative == Path("backend.tf"):
            continue
        atomic_write(runtime / relative, path.read_text())
    atomic_write(runtime / "backend.tf", 'terraform {\n  backend "local" {}\n}\n')
    aws = plan.config.aws
    inputs = {
        "aws_region": aws.region,
        "expected_account_id": aws.account_id,
        "ubuntu_version": aws.ubuntu_version,
        "ami_id": plan.ami_id,
        "architecture": aws.architecture,
        "instance_type": aws.instance_type,
        "spot_instance": False,
        "vm_name": plan.config.vm.name,
        "admin_user": plan.config.vm.username,
        "admin_source_address": aws.admin_source_cidr,
        "os_disk_size_gb": aws.os_disk_size_gb,
        "data_disk_size_gb": aws.data_disk_size_gb,
        "ssh_public_key": plan.config.vm.ssh_public_key.read_text().strip(),
        "allocate_elastic_ip": True,
        "bootstrap_mode": "external",
        "repo_url": plan.repository.url,
    }
    atomic_write(runtime / "bootstrap.tfvars.json", json.dumps(inputs))


def state_resources(document: dict) -> list[dict]:
    """Flatten Terraform state modules without exposing their values."""

    def walk(module: dict) -> list[dict]:
        resources = list(module.get("resources", []))
        for child in module.get("child_modules", []):
            resources.extend(walk(child))
        return resources

    return walk(document.get("values", {}).get("root_module", {}))


def verify_ownership(plan: AwsPlan, runner: Runner) -> None:
    """Do not adopt matching-name cloud resources outside this deployment state."""
    owned: set[str] = set()
    owned_roles: set[str] = set()
    owned_profiles: set[str] = set()
    if (plan.directory / "runtime/terraform.tfstate").exists():
        state = json.loads(terraform(plan, runner, ["show", "-json"]))
        for resource in state_resources(state):
            values = resource.get("values", {})
            if resource.get("mode") != "data":
                for attribute in ("id", "key_pair_id", "allocation_id"):
                    value = values.get(attribute)
                    if value is not None:
                        owned.add(str(value))
            # EC2 tags list root EBS volumes separately from their instance.
            if resource.get("mode") == "managed" and resource.get("type") == "aws_instance":
                for device in values.get("root_block_device") or []:
                    if device.get("volume_id"):
                        owned.add(device["volume_id"])
            if resource.get("type") == "aws_iam_role":
                owned_roles.add(resource["values"]["id"])
            if resource.get("type") == "aws_iam_instance_profile":
                owned_profiles.add(resource["values"]["id"])
    manifest = read_manifest(plan.directory) or {}
    if any(manifest.get(field) and manifest[field] not in owned for field in ("instance_id", "data_volume_id")):
        raise BootstrapError("Recorded AWS identities are missing from deployment state; recover state before retrying")
    name = plan.config.vm.name
    tags = aws_command(
        plan.config, runner, ["ec2", "describe-tags", "--filters", "Name=key,Values=Name", f"Name=value,Values={name},{name}-sg,{name}-data"]
    )
    collisions = [tag["ResourceId"] for tag in tags.get("Tags", []) if tag.get("ResourceId") not in owned]
    roles = aws_command(plan.config, runner, ["iam", "list-roles"])
    for role in roles.get("Roles", []):
        role_name = role.get("RoleName")
        if role_name == f"{name}-ec2-role" and role_name not in owned_roles:
            collisions.append(role_name)
    profiles = aws_command(plan.config, runner, ["iam", "list-instance-profiles"])
    for profile in profiles.get("InstanceProfiles", []):
        profile_name = profile.get("InstanceProfileName")
        if profile_name in {name, f"{name}-ec2-profile"} and profile_name not in owned_profiles:
            collisions.append(profile_name)
    if collisions:
        raise BootstrapError("Matching-name AWS resources are outside bootstrap state; choose a new name or perform an explicit state migration")


def inspect_plan(document: dict) -> list[str]:
    """Reject destruction, replacement, detach, or unexpected credential resources."""
    summaries = []
    for resource in document.get("resource_changes", []):
        if resource.get("mode") == "data":
            continue
        change = resource.get("change", {})
        actions = change.get("actions", [])
        if "delete" in actions:
            raise BootstrapError("Terraform plan contains deletion or replacement; explicit maintenance is required")
        if resource.get("type") == "aws_volume_attachment" and actions not in (["create"], ["no-op"]):
            raise BootstrapError("Terraform plan would modify or detach persistent storage")
        if resource.get("type") in {"tls_private_key", "aws_secretsmanager_secret", "aws_secretsmanager_secret_version"}:
            raise BootstrapError("External bootstrap must not create Terraform-managed credentials")
        if actions not in (["create"], ["update"], ["no-op"]):
            raise BootstrapError("Terraform plan contains unsupported resource actions")
        if actions != ["no-op"]:
            summaries.append(f"{resource['address']}: {','.join(actions)}")
    return summaries


def plan_infrastructure(plan: AwsPlan, runner: Runner) -> list[str]:
    """Save and privately inspect exactly the plan which may subsequently apply."""
    previous = set()
    if (plan.directory / "runtime/terraform.tfstate").exists():
        state = json.loads(terraform(plan, runner, ["show", "-json"]))
        previous = {resource["address"] for resource in state_resources(state) if resource.get("mode") == "managed"}
    terraform(plan, runner, ["plan", "-input=false", "-lock-timeout=30s", "-var-file=bootstrap.tfvars.json", "-out=bootstrap.tfplan"])
    path = plan.directory / "runtime/bootstrap.tfplan"
    if path.exists():
        path.chmod(0o600)
    document = json.loads(terraform(plan, runner, ["show", "-json", "bootstrap.tfplan"]))
    if any(
        resource.get("address") in previous and "create" in resource.get("change", {}).get("actions", [])
        for resource in document.get("resource_changes", [])
    ):
        raise BootstrapError("Terraform would recreate a previously owned missing resource; explicit maintenance is required")
    return inspect_plan(document)


def preflight(plan: AwsPlan, runner: Runner, root: Path = ROOT) -> None:
    """Check connectivity and create a read-only cloud plan; no resource apply."""
    address = runner.run(
        ["curl", "--ipv4", "--fail", "--silent", "--show-error", "--max-time", "10", "https://ipinfo.io/ip"], capture=True, timeout=15
    )
    try:
        permitted = ipaddress.IPv4Address(address) in ipaddress.IPv4Network(plan.config.aws.admin_source_cidr)
    except ValueError as error:
        raise BootstrapError("Could not determine administrator public IPv4 address") from error
    if not permitted:
        raise BootstrapError("Administrator public IPv4 address is outside aws.admin_source_cidr")
    verify_inventory_name(plan, root)
    verify_public_repository(plan, runner)
    images = aws_command(plan.config, runner, ["ec2", "describe-images", "--owners", "099720109477", "--image-ids", plan.ami_id])
    if not any(
        image.get("ImageId") == plan.ami_id and image.get("Architecture") == "x86_64" and image.get("State") == "available"
        for image in images.get("Images", [])
    ):
        raise BootstrapError("Pinned AMI is not an available official x86_64 Ubuntu image")
    types = aws_command(plan.config, runner, ["ec2", "describe-instance-types", "--instance-types", plan.config.aws.instance_type])
    if not any("x86_64" in instance.get("ProcessorInfo", {}).get("SupportedArchitectures", []) for instance in types.get("InstanceTypes", [])):
        raise BootstrapError("Requested EC2 instance type does not support x86_64")
    if not any(instance.get("EbsInfo", {}).get("NvmeSupport") in {"supported", "required"} for instance in types.get("InstanceTypes", [])):
        raise BootstrapError("Requested EC2 instance type must support EBS NVMe for verified storage initialization")
    render_provisioning(plan, root)
    terraform(plan, runner, ["init", "-input=false"])
    verify_ownership(plan, runner)
    changes = plan_infrastructure(plan, runner)
    print_plan(plan, changes)


def verify_inventory_name(plan: AwsPlan, root: Path) -> None:
    """Do not merge a fresh AWS host into an unrelated existing Ansible target."""
    manifest = read_manifest(plan.directory) or {}
    for relative in ("ansible/inventory/inventory.yaml", "config/ansible/inventory/inventory.yaml"):
        path = root / relative
        if not path.exists():
            continue
        try:
            document = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError) as error:
            raise BootstrapError("Cannot validate existing Ansible inventory before provisioning") from error
        if not isinstance(document, dict):
            raise BootstrapError("Existing Ansible inventory must be a mapping")
        for group in ("debian", "docker_hosts"):
            if group not in document:
                continue
            if not isinstance(document[group], dict):
                raise BootstrapError("Existing Ansible inventory group must be a mapping")
            if not isinstance(document[group].get("hosts", {}), dict):
                raise BootstrapError("Existing Ansible inventory hosts must be a mapping")

        def walk(value: object) -> bool:
            if not isinstance(value, dict):
                return False
            hosts = value.get("hosts")
            if isinstance(hosts, dict) and plan.config.vm.name in hosts:
                return True
            return any(walk(child) for child in value.values())

        if walk(document) and (relative.startswith("ansible/") or not manifest.get("public_ip")):
            raise BootstrapError("VM name already belongs to an existing Ansible inventory host; choose a new AWS hostname")


def verify_public_repository(plan: AwsPlan, runner: Runner) -> None:
    """Prove the fresh guest can fetch the pinned revision without Git credentials."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    try:
        with tempfile.TemporaryDirectory(prefix="anonymous-git-", dir=plan.directory) as directory:
            env["HOME"] = directory
            env["GIT_CEILING_DIRECTORIES"] = str(plan.directory)
            result = runner.run(
                [
                    "git",
                    "-c",
                    "credential.helper=",
                    "-c",
                    "core.askPass=",
                    "ls-remote",
                    "--heads",
                    plan.repository.url,
                    f"refs/heads/{plan.repository.branch}",
                ],
                capture=True,
                timeout=30,
                env=env,
                cwd=Path(directory),
            )
    except BootstrapError as error:
        raise BootstrapError(
            "AWS bootstrap requires an anonymously readable HTTPS repository; private Git authentication is not configured"
        ) from error
    if not result or result.split()[0] != plan.repository.commit:
        raise BootstrapError("Public repository branch no longer matches the planned commit")


def print_plan(plan: AwsPlan, changes: list[str]) -> None:
    """Print only allowlisted non-secret planning details."""
    print(f"AWS target: account {plan.config.aws.account_id}, region {plan.config.aws.region}, name {plan.config.vm.name}")
    print(f"AMI: {plan.ami_id}; on-demand {plan.config.aws.instance_type}; administrator CIDR {plan.config.aws.admin_source_cidr}")
    print("Cost-bearing resources: EC2, root and persistent EBS volumes, Elastic IP/public IPv4")
    print(f"Private state: {plan.directory}; Cloudflare token: <redacted>")
    for change in changes:
        print(f"  {change}")
    if not changes:
        print("  No infrastructure changes")


def ssm(plan: AwsPlan, runner: Runner, instance_id: str, commands: list[str], timeout: int = 600) -> str:
    """Run secret-free checks via the authenticated control plane on one instance."""
    result = aws_command(
        plan.config,
        runner,
        [
            "ssm",
            "send-command",
            "--instance-ids",
            instance_id,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            json.dumps({"commands": commands, "executionTimeout": [str(timeout)]}),
        ],
    )
    command_id = result["Command"]["CommandId"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            invocation = aws_command(plan.config, runner, ["ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance_id])
        except BootstrapError:
            time.sleep(3)
            continue
        status = invocation.get("Status")
        if status == "Success":
            return invocation.get("StandardOutputContent", "")
        if status not in {"Pending", "InProgress", "Delayed"}:
            raise BootstrapError("SSM guest check failed; inspect cloud-init and volume mount through the AWS console")
        time.sleep(3)
    raise BootstrapError("SSM command timed out; resources remain, rerun after correcting the problem")


def output(plan: AwsPlan, runner: Runner, name: str) -> str:
    """Read one Terraform output privately with the short command timeout."""
    return terraform(plan, runner, ["output", "-raw", name], timeout=30).strip()


def wait_ready(plan: AwsPlan, runner: Runner, instance_id: str) -> None:
    """Require EC2 health and a live SSM agent before any guest SSH connection."""
    result = aws_command(plan.config, runner, ["ec2", "describe-instances", "--instance-ids", instance_id])
    instances = []
    for reservation in result.get("Reservations", []):
        instances.extend(reservation.get("Instances", []))
    if len(instances) != 1 or instances[0].get("InstanceId") != instance_id:
        raise BootstrapError("AWS instance identity does not match deployment state")
    state = instances[0].get("State", {}).get("Name")
    if state == "stopped":
        aws_command(plan.config, runner, ["ec2", "start-instances", "--instance-ids", instance_id])
    elif state not in {"pending", "running"}:
        raise BootstrapError("Owned EC2 instance is not resumable; inspect its state before retrying")
    aws_command(plan.config, runner, ["ec2", "wait", "instance-running", "--instance-ids", instance_id], timeout=600)
    aws_command(plan.config, runner, ["ec2", "wait", "instance-status-ok", "--instance-ids", instance_id], timeout=600)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        info = aws_command(plan.config, runner, ["ssm", "describe-instance-information", "--filters", f"Key=InstanceIds,Values={instance_id}"])
        if any(
            instance.get("InstanceId") == instance_id and instance.get("PingStatus") == "Online"
            for instance in info.get("InstanceInformationList", [])
        ):
            ssm(plan, runner, instance_id, ["cloud-init status --wait >/dev/null"], timeout=900)
            return
        time.sleep(5)
    raise BootstrapError("SSM agent did not register; check cloud-init, instance role and outbound HTTPS. Resources remain")


def verify_storage(plan: AwsPlan, runner: Runner, instance_id: str, volume_id: str) -> None:
    """Fail if /storage is absent, on the root filesystem, or the wrong EBS disk."""
    serial = volume_id.replace("-", "")
    command = (
        'set -eu; mountpoint -q /storage; test "$(findmnt -n -o FSTYPE --target /storage)" = ext4; '
        "device=$(findmnt -n -o SOURCE --target /storage); "
        f'test "$(lsblk -dn -o SERIAL "$device" | tr -d \' -\')" = {shlex.quote(serial)}'
    )
    ssm(plan, runner, instance_id, [command], timeout=60)


def initialize_storage(plan: AwsPlan, runner: Runner, instance_id: str, volume_id: str) -> None:
    """Format only a newly created, owned EBS volume with a one-time receipt."""
    manifest = read_manifest(plan.directory) or {}
    if manifest.get("data_volume_id") != volume_id or manifest.get("instance_id") != instance_id:
        raise BootstrapError("Storage initialization identities do not match deployment state")
    serial = volume_id.replace("-", "")
    device_check = (
        f"set -eu; device=$(readlink -f /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_{shlex.quote(serial)}); "
        'test -b "$device"; '
        f'test "$(lsblk -dn -o SERIAL "$device" | tr -d \' -\')" = {shlex.quote(serial)}; '
        'test "$(lsblk -nr -o NAME "$device" | wc -l)" -eq 1; '
    )
    filesystem = ssm(plan, runner, instance_id, [device_check + 'blkid -s TYPE -o value "$device" || true'], timeout=60).strip()
    if filesystem == "ext4":
        ssm(plan, runner, instance_id, ["bash /usr/local/bin/mount-storage.sh"], timeout=60)
        verify_storage(plan, runner, instance_id, volume_id)
        manifest["storage_initialized"] = True
        atomic_write(plan.directory / "manifest.json", json.dumps(manifest))
        return
    if (
        filesystem
        or manifest.get("storage_initialized")
        or manifest.get("storage_initialization_started")
        or not manifest.get("allow_storage_initialization")
    ):
        raise BootstrapError("Storage initialization is not authorized for this volume; inspect it manually rather than reformatting")
    result = aws_command(plan.config, runner, ["ec2", "describe-volumes", "--volume-ids", volume_id])
    volumes = result.get("Volumes", [])
    if len(volumes) != 1:
        raise BootstrapError("Cannot identify the newly created EBS volume")
    volume = volumes[0]
    tags = {tag["Key"]: tag["Value"] for tag in volume.get("Tags", [])}
    if (
        volume.get("VolumeId") != volume_id
        or volume.get("SnapshotId")
        or tags.get("Name") != f"{plan.config.vm.name}-data"
        or len(volume.get("Attachments", [])) != 1
        or volume["Attachments"][0].get("InstanceId") != instance_id
        or volume["Attachments"][0].get("State") != "attached"
    ):
        raise BootstrapError("Storage initialization requires the owned fresh, snapshot-free volume attached to this instance")
    # Persist BEFORE mkfs: an interrupted operation never grants a second format.
    manifest["storage_initialization_started"] = True
    atomic_write(plan.directory / "manifest.json", json.dumps(manifest))
    command = (
        device_check + 'test -z "$(blkid -s TYPE -o value "$device" || true)"; '
        'signatures=$(wipefs --no-act --noheadings --output TYPE "$device"); test -z "$signatures"; '
        'mkfs.ext4 "$device"; bash /usr/local/bin/mount-storage.sh'
    )
    ssm(plan, runner, instance_id, [command], timeout=180)
    verify_storage(plan, runner, instance_id, volume_id)
    manifest["storage_initialized"] = True
    atomic_write(plan.directory / "manifest.json", json.dumps(manifest))


def establish_ssh_trust(plan: AwsPlan, runner: Runner, instance_id: str) -> None:
    """Pin SSH keys retrieved from SSM and fail rather than replacing trust."""
    trusted = ssm(plan, runner, instance_id, ["cat /etc/ssh/ssh_host_ed25519_key.pub"], timeout=60).split()
    if len(trusted) < 2 or trusted[0] != "ssh-ed25519" or not re.fullmatch(r"[A-Za-z0-9+/=]+", trusted[1]):
        raise BootstrapError("SSM returned an invalid SSH host public key")
    network = runner.run(["ssh-keyscan", "-T", "10", "-t", "ed25519", plan.config.network.expected_ipv4], capture=True, timeout=15)
    keys = set()
    for line in network.splitlines():
        fields = line.split()
        if len(fields) == 3 and not line.startswith("#"):
            keys.add(tuple(fields[1:3]))
    if keys != {tuple(trusted[:2])}:
        raise BootstrapError("SSH network host key does not match the trusted SSM key")
    desired = f"{plan.config.network.expected_ipv4} {' '.join(trusted[:2])}\n"
    if plan.known_hosts.exists() and plan.known_hosts.read_text() != desired:
        raise BootstrapError("Stored AWS host trust changed; inspect it manually before retrying")
    atomic_write(plan.known_hosts, desired)
    runner.run(vm_ssh_command(plan, "true"), timeout=30)


def complete_deployment(plan: AwsPlan, runner: Runner, manifest: dict, root: Path) -> None:
    """Resolve the created host and run shared guest deployment and acceptance."""
    instance_id = output(plan, runner, "instance_id")
    address = output(plan, runner, "public_ip")
    volume_id = output(plan, runner, "data_volume_id")
    if not re.fullmatch(r"i-[0-9a-f]+", instance_id) or not re.fullmatch(r"vol-[0-9a-f]+", volume_id):
        raise BootstrapError("Terraform returned invalid AWS resource identities")
    try:
        ipaddress.IPv4Address(address)
    except ValueError as error:
        raise BootstrapError("Terraform returned an invalid public IPv4 address") from error
    if plan.config.network.expected_ipv4 and plan.config.network.expected_ipv4 != address:
        raise BootstrapError("AWS Elastic IP does not match network.expected_ipv4")
    manifest.update(instance_id=instance_id, public_ip=address, data_volume_id=volume_id)
    atomic_write(plan.directory / "manifest.json", json.dumps(manifest))
    print(f"AWS resources: instance {instance_id}, Elastic IP {address}, data volume {volume_id}")
    print("Waiting for EC2 health, SSM, cloud-init and the persistent storage mount")
    plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4=address)))
    wait_ready(plan, runner, instance_id)
    initialize_storage(plan, runner, instance_id, volume_id)
    verify_storage(plan, runner, instance_id, volume_id)
    establish_ssh_trust(plan, runner, instance_id)
    verify_dns(plan, address, discovered=True)
    print("Configuring the host and deploying core Docker services")
    render_config(plan, root)
    configure_host(plan, runner)
    prepare_remote_repository(plan, runner, root)
    deploy_services(plan, runner)
    verify_services(plan, runner)
    verify_storage(plan, runner, instance_id, volume_id)
    if plan_infrastructure(plan, runner):
        raise BootstrapError("Repeat Terraform plan has unexpected infrastructure changes")


def apply(plan: AwsPlan, runner: Runner, *, assume_yes: bool = False, root: Path = ROOT) -> None:
    """Apply the inspected saved plan, then converge on shared host deployment."""
    verify_identity(plan.config, runner)
    if not assume_yes and input("Apply the displayed AWS plan and deploy core services? AWS charges apply. [y/N] ").strip().lower() not in {
        "y",
        "yes",
    }:
        raise BootstrapError("Bootstrap cancelled")
    manifest = read_manifest(plan.directory)
    if manifest is None:
        raise BootstrapError("Deployment manifest is missing")
    document = json.loads(terraform(plan, runner, ["show", "-json", "bootstrap.tfplan"]))
    inspect_plan(document)
    if any(
        resource.get("address") == "aws_ebs_volume.data" and resource.get("change", {}).get("actions") == ["create"]
        for resource in document.get("resource_changes", [])
    ):
        manifest["allow_storage_initialization"] = True
    manifest["apply_started"] = True
    atomic_write(plan.directory / "manifest.json", json.dumps(manifest))
    try:
        terraform(plan, runner, ["apply", "-input=false", "-lock-timeout=30s", "bootstrap.tfplan"])
        complete_deployment(plan, runner, manifest, root)
    except BootstrapError:
        print(
            f"AWS resources may still incur charges. State and resource IDs: {plan.directory}. Correct the issue and rerun the same apply; no cleanup was performed."
        )
        raise
    print("AWS bootstrap completed successfully.")
