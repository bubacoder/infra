"""AWS bootstrap tests; all cloud and guest operations are mocked."""

# ruff: noqa: PT009, PT027

import contextlib
import io
import json
import os
import shlex
import shutil
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from scripts.bootstrap import __main__ as cli
from scripts.bootstrap import aws, config, core, deploy, network


class AwsBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "config").mkdir()
        self.key = self.root / "id_ed25519.pub"
        self.key.write_text("ssh-ed25519 AAAAtest operator@test\n")
        self.path = self.root / "config/bootstrap.yaml"
        self.document = yaml.safe_load((core.ROOT / "config-example/bootstrap-aws.yaml").read_text())
        self.document["network"]["dns"] = {"mode": "external", "verify": True}
        self.document["vm"]["ssh_public_key"] = str(self.key)
        self.document["aws"]["admin_source_cidr"] = "8.8.8.8/32"
        self.document["tls"]["token"] = "test-cloudflare-secret"  # noqa: S105
        self.write()
        shutil.copytree(
            core.ROOT / "terraform/aws-vm", self.root / "terraform/aws-vm", ignore=shutil.ignore_patterns(".terraform", "*.tfstate*", "*.tfplan")
        )
        inventory = self.root / "config-example/ansible/inventory"
        inventory.mkdir(parents=True)
        (inventory / "inventory.yaml").write_text("debian:\n  hosts: {}\ndocker_hosts:\n  hosts: {}\n")
        self.repository = core.RepositoryConfig("https://example.com/infra.git", "main", "a" * 40)
        self.runner = Mock()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write(self) -> None:
        self.path.write_text(yaml.safe_dump(self.document))
        self.path.chmod(0o600)

    def load(self) -> core.BootstrapConfig:
        return config.load_config(self.path, self.root)

    def plan(self) -> core.AwsPlan:
        directory = self.root / "config/terraform/bootstrap/docker-aws"
        directory.mkdir(parents=True, exist_ok=True)
        return core.AwsPlan(self.load(), self.repository, directory, "ami-123abc")

    def manifest(self, plan: core.AwsPlan, *, started: bool = False) -> None:
        deploy.atomic_write(
            plan.directory / "manifest.json",
            json.dumps(
                {
                    "identity": aws.provision_identity(plan.config, self.root),
                    "ami_id": plan.ami_id,
                    "apply_started": started,
                }
            ),
        )

    def test_loads_aws_and_shared_configuration(self) -> None:
        loaded = self.load()
        self.assertEqual(loaded.target, "aws")
        self.assertIsNone(loaded.proxmox)
        self.assertEqual(loaded.aws.account_id, "123456789012")
        self.assertEqual(loaded.vm.username, "ubuntu")
        self.assertIsNone(loaded.network.expected_ipv4)

    def test_rejects_mixed_target_fields(self) -> None:
        for location, field, value in ((None, "proxmox", {}), ("vm", "bridge", "vmbr0"), ("aws", "spot_instance", True)):
            with self.subTest(field=field):
                target = self.document if location is None else self.document[location]
                target[field] = value
                self.write()
                with self.assertRaises(core.ConfigError):
                    self.load()
                del target[field]

    def test_rejects_invalid_aws_values(self) -> None:
        for section, field, invalid in (
            ("aws", "account_id", 123456789012),
            ("aws", "architecture", "arm64"),
            ("aws", "admin_source_cidr", "0.0.0.0/0"),
            ("aws", "region", "-bad"),
            ("aws", "data_disk_size_gb", True),
            ("aws", "instance_type", "-bad"),
            ("vm", "username", "admin"),
            ("host", "docker_volumes", "/srv/docker-volumes"),
            ("host", "docker_volumes", "/storage/../srv"),
        ):
            with self.subTest(field=field):
                previous = self.document[section][field]
                self.document[section][field] = invalid
                self.write()
                with self.assertRaises(core.ConfigError):
                    self.load()
                self.document[section][field] = previous

    def test_instance_types_allow_internal_hyphens_but_reject_malformed_names(self) -> None:
        """Accept EC2 family variants without allowing unsafe or malformed tokens."""
        for instance in ("t3.small", "m7i-flex.large", "u-6tb1.112xlarge", "x2iedn.metal"):
            with self.subTest(instance=instance):
                self.document["aws"]["instance_type"] = instance
                self.write()
                self.assertEqual(self.load().aws.instance_type, instance)
        for instance in ("-m7i.large", "m7i-.large", "m7i--flex.large", "m7i.-large", "m7i.large-", "m7i.large.extra", "m7i.large;id"):
            with self.subTest(instance=instance):
                self.document["aws"]["instance_type"] = instance
                self.write()
                with self.assertRaisesRegex(core.ConfigError, "aws.instance_type is invalid"):
                    self.load()

    def test_rejects_aws_version_one(self) -> None:
        self.document["version"] = 1
        self.write()
        with self.assertRaisesRegex(core.ConfigError, "version 1 supports Proxmox"):
            self.load()

    def test_rejects_missing_explicit_version_two_target(self) -> None:
        del self.document["target"]
        self.write()
        with self.assertRaisesRegex(core.ConfigError, "requires target"):
            self.load()

    def test_wrong_account_fails_closed(self) -> None:
        with patch.object(aws, "aws_command", return_value={"Account": "999999999999"}), self.assertRaisesRegex(core.BootstrapError, "account"):
            aws.verify_identity(self.load(), self.runner)

    def test_environment_isolates_terraform_overrides(self) -> None:
        with patch.dict(os.environ, {"TF_VAR_bootstrap_mode": "standalone", "TF_CLI_ARGS": "-target=wrong", "TF_WORKSPACE": "other"}):
            env = aws.environment(self.load(), self.root)
        self.assertNotIn("TF_VAR_bootstrap_mode", env)
        self.assertNotIn("TF_CLI_ARGS", env)
        self.assertEqual(env["TF_WORKSPACE"], "default")
        self.assertEqual(env["AWS_PROFILE"], "homelab")

    def test_aws_wait_accepts_empty_output(self) -> None:
        self.runner.run.return_value = ""
        self.assertEqual(aws.aws_command(self.load(), self.runner, ["ec2", "wait", "instance-running"]), {})

    def test_command_error_does_not_expose_credentials(self) -> None:
        self.runner.run.side_effect = core.BootstrapError("secret-aws-token")
        with self.assertRaises(core.BootstrapError) as raised:
            aws.aws_command(self.load(), self.runner, ["sts", "get-caller-identity"])
        self.assertNotIn("secret-aws-token", str(raised.exception))

    def test_custom_aws_endpoint_is_rejected(self) -> None:
        with patch.dict(os.environ, {"AWS_ENDPOINT_URL": "https://untrusted.example"}), self.assertRaisesRegex(core.BootstrapError, "endpoint"):
            aws.aws_command(self.load(), self.runner, ["sts", "get-caller-identity"])
        self.runner.run.assert_not_called()

    def test_requires_matching_ssh_identity(self) -> None:
        self.runner.run.return_value = "ssh-ed25519 AAAAother"
        with self.assertRaisesRegex(core.BootstrapError, "matching"):
            aws.verify_ssh_identity(self.load(), self.runner)

    def test_accepts_matching_agent_identity(self) -> None:
        self.runner.run.return_value = self.key.read_text()
        aws.verify_ssh_identity(self.load(), self.runner)

    def test_encrypted_private_key_can_use_agent(self) -> None:
        private = self.key.with_suffix("")
        private.write_text("encrypted fixture")
        private.chmod(0o600)
        self.runner.run.side_effect = [core.BootstrapError("encrypted"), self.key.read_text()]
        aws.verify_ssh_identity(self.load(), self.runner)

    def test_private_key_permissions_are_checked(self) -> None:
        private = self.key.with_suffix("")
        private.write_text("fixture")
        private.chmod(0o644)
        with self.assertRaisesRegex(core.BootstrapError, "0600"):
            aws.verify_ssh_identity(self.load(), self.runner)

    def test_anonymous_repository_check_ignores_local_git_credentials(self) -> None:
        plan = self.plan()
        self.runner.run.return_value = f"{plan.repository.commit}\trefs/heads/main"
        aws.verify_public_repository(plan, self.runner)
        call = self.runner.run.call_args
        self.assertIn("credential.helper=", call.args[0])
        self.assertEqual(call.kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(call.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertNotEqual(call.kwargs["cwd"], core.ROOT)

    def test_private_repository_is_rejected_before_provisioning(self) -> None:
        self.runner.run.side_effect = core.BootstrapError("auth needed")
        with self.assertRaisesRegex(core.BootstrapError, "anonymously readable"):
            aws.verify_public_repository(self.plan(), self.runner)

    def test_public_branch_change_requires_new_plan(self) -> None:
        self.runner.run.return_value = "different-commit refs/heads/main"
        with self.assertRaisesRegex(core.BootstrapError, "planned commit"):
            aws.verify_public_repository(self.plan(), self.runner)

    def test_cli_selects_aws_without_proxmox_calls(self) -> None:
        args = Mock(config=self.path, yes=True, apply=True, destroy=False, delete_data=False, dry_run=False, show_config=False)
        plan = self.plan()
        with (
            patch.object(cli, "parse_args", return_value=args),
            patch.object(cli.config, "load_config", return_value=plan.config),
            patch.object(cli.aws, "deployment_lock", return_value=contextlib.nullcontext()),
            patch.object(cli.aws, "resolve_plan", return_value=plan),
            patch.object(cli.aws, "preflight") as preflight,
            patch.object(cli.aws, "apply") as apply,
            patch.object(cli.proxmox, "resolve_plan") as proxmox,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli.main()
        preflight.assert_called_once()
        apply.assert_called_once()
        proxmox.assert_not_called()

    def test_runtime_copy_has_no_cloudflare_token_or_standalone_state(self) -> None:
        source = self.root / "terraform/aws-vm"
        (source / "terraform.tfstate").write_text("standalone secret")
        (source / "backend.tf").write_text("untrusted backend")
        plan = self.plan()
        aws.render_provisioning(plan, self.root)
        runtime = plan.directory / "runtime"
        self.assertFalse((runtime / "terraform.tfstate").exists())
        self.assertNotIn("untrusted", (runtime / "backend.tf").read_text())
        inputs = json.loads((runtime / "bootstrap.tfvars.json").read_text())
        self.assertEqual(inputs["bootstrap_mode"], "external")
        self.assertTrue(inputs["allocate_elastic_ip"])
        self.assertFalse(inputs["spot_instance"])
        self.assertEqual(inputs["ami_id"], plan.ami_id)
        self.assertEqual(inputs["expected_account_id"], plan.config.aws.account_id)
        self.assertNotIn("test-cloudflare-secret", json.dumps(inputs))
        self.assertEqual((runtime / "bootstrap.tfvars.json").stat().st_mode & 0o777, 0o600)

    def test_runtime_removes_stale_templates_without_touching_deployment_artifacts(self) -> None:
        """Synchronize renamed sources while retaining state, cache, and receipts."""
        source = self.root / "terraform/aws-vm"
        obsolete_sources = (source / "obsolete.tf", source / "cloud-init/obsolete.sh.tpl")
        for path in obsolete_sources:
            path.write_text("# obsolete generated source\n")
        plan = self.plan()
        aws.render_provisioning(plan, self.root)
        runtime = plan.directory / "runtime"
        protected = (
            runtime / "terraform.tfstate",
            runtime / "terraform.tfstate.backup",
            runtime / "bootstrap.tfplan",
            runtime / ".terraform.lock.hcl",
            runtime / ".terraform/providers/cache.tf",
            runtime / "notes.txt",
            runtime / "cloud-init/notes.txt",
            plan.directory / "manifest.json",
            plan.known_hosts,
        )
        for path in protected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("preserve this deployment artifact\n")
        for path in obsolete_sources:
            path.rename(path.with_name(path.name.replace("obsolete", "replacement")))
        aws.render_provisioning(plan, self.root)
        for path in obsolete_sources:
            relative = path.relative_to(source)
            self.assertFalse((runtime / relative).exists())
            replacement = relative.with_name(relative.name.replace("obsolete", "replacement"))
            self.assertEqual((runtime / replacement).read_text(), (source / replacement).read_text())
        for path in protected:
            self.assertEqual(path.read_text(), "preserve this deployment artifact\n")
        self.assertEqual((runtime / "main.tf").read_text(), (source / "main.tf").read_text())
        self.assertEqual((runtime / "backend.tf").read_text(), 'terraform {\n  backend "local" {}\n}\n')

    def test_cloud_init_preparation_propagates_command_failures(self) -> None:
        template = yaml.safe_load((core.ROOT / "terraform/aws-vm/cloud-init/external.yaml.tpl").read_text())
        commands = template["runcmd"]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][:2], ["bash", "-ec"])
        self.assertIn("--defer-initialization", commands[0][2])

    def test_aws_host_render_does_not_write_proxmox_configuration(self) -> None:
        plan = self.plan()
        plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4="8.8.4.4")))
        deploy.render_config(plan, self.root)
        self.assertFalse((self.root / "config/vm/proxmox").exists())
        inventory = yaml.safe_load((self.root / "config/ansible/inventory/inventory.yaml").read_text())
        host = inventory["debian"]["hosts"]["docker-aws"]
        self.assertEqual(host["ansible_host"], "8.8.4.4")
        self.assertIn("StrictHostKeyChecking=yes", host["ansible_ssh_common_args"])
        self.assertIn(str(plan.known_hosts), host["ansible_ssh_common_args"])

    def test_aws_admin_cidr_is_rendered_for_traefik(self) -> None:
        plan = self.plan()
        plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4="8.8.4.4")))
        deploy.render_config(plan, self.root)
        env = (self.root / "config/docker/docker-aws/.env").read_text()
        self.assertIn("LOCAL_ACCESS_ADMIN_CIDR=8.8.8.8/32", env)

    def test_remote_commands_and_rsync_share_strict_ssh_transport(self) -> None:
        """Preserve AWS host pinning and quoted identity paths across transports."""
        plan = self.plan()
        public_key = self.root / "identity with spaces.pub"
        public_key.write_text(self.key.read_text())
        private_key = public_key.with_suffix("")
        private_key.write_text("test fixture")
        guest = replace(plan.config.vm, ssh_public_key=public_key)
        plan = replace(plan, config=replace(plan.config, vm=guest))
        transport = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={plan.known_hosts}",
            "-i",
            str(private_key),
        ]
        self.assertEqual(core.ssh_command(plan), transport)
        self.assertEqual(core.vm_ssh_command(plan, "true")[:-2], transport)
        self.runner.run.side_effect = ["missing", "", "", "yes", "", "", ""]
        deploy.prepare_remote_repository(plan, self.runner, self.root)
        transfers = [call.args[0] for call in self.runner.run.call_args_list if call.args[0][0] == "rsync"]
        self.assertEqual(len(transfers), 1)
        self.assertEqual(shlex.split(transfers[0][3]), transport)

    def test_plan_inspection_rejects_destruction_and_detach(self) -> None:
        for resource_type, actions in (
            ("aws_instance", ["delete"]),
            ("aws_instance", ["delete", "create"]),
            ("aws_volume_attachment", ["update"]),
            ("tls_private_key", ["create"]),
            ("aws_secretsmanager_secret", ["create"]),
            ("aws_instance", ["unknown"]),
        ):
            with self.subTest(actions=actions, resource_type=resource_type), self.assertRaises(core.BootstrapError):
                aws.inspect_plan({"resource_changes": [{"type": resource_type, "address": "test.main", "change": {"actions": actions}}]})

    def test_plan_inspection_reports_only_addresses_and_actions(self) -> None:
        document = {
            "resource_changes": [
                {
                    "type": "aws_instance",
                    "address": "module.ec2.aws_instance.this[0]",
                    "change": {"actions": ["create"], "after": {"secret": "never-print-this"}},
                }
            ]
        }
        self.assertEqual(aws.inspect_plan(document), ["module.ec2.aws_instance.this[0]: create"])

    def test_deleted_owned_instance_cannot_be_automatically_recreated(self) -> None:
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        address = "module.ec2.aws_instance.this[0]"
        state = {"values": {"root_module": {"resources": [{"address": address, "mode": "managed", "values": {"id": "i-old"}}]}}}
        proposed = {"resource_changes": [{"address": address, "type": "aws_instance", "change": {"actions": ["create"]}}]}
        with (
            patch.object(aws, "terraform", side_effect=[json.dumps(state), "", json.dumps(proposed)]),
            self.assertRaisesRegex(core.BootstrapError, "recreate"),
        ):
            aws.plan_infrastructure(plan, self.runner)

    def test_recorded_instance_cannot_disappear_from_state(self) -> None:
        plan = self.plan()
        self.manifest(plan)
        manifest = aws.read_manifest(plan.directory)
        manifest["instance_id"] = "i-recorded"
        deploy.atomic_write(plan.directory / "manifest.json", json.dumps(manifest))
        with self.assertRaisesRegex(core.BootstrapError, "Recorded AWS identities"):
            aws.verify_ownership(plan, self.runner)

    def test_collision_requires_manual_migration(self) -> None:
        plan = self.plan()
        with (
            patch.object(aws, "aws_command", side_effect=[{"Tags": [{"ResourceId": "i-other"}]}, {"Roles": []}, {"InstanceProfiles": []}]),
            self.assertRaisesRegex(core.BootstrapError, "outside bootstrap state"),
        ):
            aws.verify_ownership(plan, self.runner)

    def test_existing_inventory_hostname_is_not_overwritten(self) -> None:
        path = self.root / "config/ansible/inventory/inventory.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("debian:\n  hosts:\n    docker-aws:\n      ansible_host: 192.0.2.10\n")
        with self.assertRaisesRegex(core.BootstrapError, "existing Ansible"):
            aws.verify_inventory_name(self.plan(), self.root)

    def test_inventory_validation_rejects_invalid_group_and_host_shapes(self) -> None:
        """Explicit null groups and host lists cannot bypass name validation."""
        path = self.root / "config/ansible/inventory/inventory.yaml"
        path.parent.mkdir(parents=True)
        cases = (
            ({"debian": None}, "group must be a mapping"),
            ({"docker_hosts": {"hosts": []}}, "hosts must be a mapping"),
        )
        for document, message in cases:
            with self.subTest(document=document):
                path.write_text(yaml.safe_dump(document))
                with self.assertRaisesRegex(core.BootstrapError, message):
                    aws.verify_inventory_name(self.plan(), self.root)

    def test_nested_inventory_hostname_is_not_overwritten(self) -> None:
        """Search nested inventory groups even when standard groups are absent."""
        path = self.root / "config/ansible/inventory/inventory.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("all:\n  children:\n    custom:\n      hosts:\n        docker-aws: {}\n")
        with self.assertRaisesRegex(core.BootstrapError, "existing Ansible"):
            aws.verify_inventory_name(self.plan(), self.root)

    def test_aws_key_pair_cloud_id_is_recognized_as_owned(self) -> None:
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        state = {"values": {"root_module": {"resources": [{"mode": "managed", "values": {"id": "docker-aws", "key_pair_id": "key-123"}}]}}}
        with (
            patch.object(aws, "terraform", return_value=json.dumps(state)),
            patch.object(aws, "aws_command", side_effect=[{"Tags": [{"ResourceId": "key-123"}]}, {"Roles": []}, {"InstanceProfiles": []}]),
        ):
            aws.verify_ownership(plan, self.runner)

    def test_nested_instance_root_volume_is_recognized_as_owned(self) -> None:
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        state = {
            "values": {
                "root_module": {
                    "resources": [
                        {"mode": "managed", "type": "aws_instance", "values": {"id": "i-owned", "root_block_device": [{"volume_id": "vol-root"}]}}
                    ]
                }
            }
        }
        with (
            patch.object(aws, "terraform", return_value=json.dumps(state)),
            patch.object(aws, "aws_command", side_effect=[{"Tags": [{"ResourceId": "vol-root"}]}, {"Roles": []}, {"InstanceProfiles": []}]),
        ):
            aws.verify_ownership(plan, self.runner)

    def test_existing_template_named_iam_profile_is_not_adopted(self) -> None:
        plan = self.plan()
        with (
            patch.object(
                aws,
                "aws_command",
                side_effect=[{"Tags": []}, {"Roles": []}, {"InstanceProfiles": [{"InstanceProfileName": "docker-aws-ec2-profile"}]}],
            ),
            self.assertRaisesRegex(core.BootstrapError, "outside bootstrap state"),
        ):
            aws.verify_ownership(plan, self.runner)

    def test_owned_state_resources_can_resume(self) -> None:
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        state = {
            "values": {
                "root_module": {
                    "resources": [{"type": "aws_iam_role", "values": {"id": "docker-aws-ec2-role"}}],
                    "child_modules": [{"resources": [{"values": {"id": "i-owned"}}]}],
                }
            }
        }
        with (
            patch.object(aws, "terraform", return_value=json.dumps(state)),
            patch.object(
                aws,
                "aws_command",
                side_effect=[{"Tags": [{"ResourceId": "i-owned"}]}, {"Roles": [{"RoleName": "docker-aws-ec2-role"}]}, {"InstanceProfiles": []}],
            ),
        ):
            aws.verify_ownership(plan, self.runner)

    def test_state_resources_preserves_depth_first_module_order(self) -> None:
        """Visit parent resources before descendants, including empty modules."""
        root_resource = {"address": "root"}
        child_resource = {"address": "child"}
        grandchild_resource = {"address": "grandchild"}
        sibling_resource = {"address": "sibling"}
        document = {
            "values": {
                "root_module": {
                    "resources": [root_resource],
                    "child_modules": [
                        {},
                        {"resources": [child_resource], "child_modules": [{"resources": [grandchild_resource]}]},
                        {"resources": [sibling_resource]},
                    ],
                }
            }
        }
        self.assertEqual(aws.state_resources(document), [root_resource, child_resource, grandchild_resource, sibling_resource])
        self.assertEqual(aws.state_resources({}), [])

    def test_data_source_ids_do_not_grant_resource_ownership(self) -> None:
        """Reading a cloud object through Terraform must not authorize adopting it."""
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        resource = {
            "mode": "data",
            "type": "aws_instance",
            "values": {
                "id": "i-other",
                "key_pair_id": "key-other",
                "allocation_id": "eipalloc-other",
                "root_block_device": [{"volume_id": "vol-other"}],
            },
        }
        state = {"values": {"root_module": {"child_modules": [{"resources": [resource]}]}}}
        for identity in ("i-other", "key-other", "eipalloc-other", "vol-other"):
            with (
                self.subTest(identity=identity),
                patch.object(aws, "terraform", return_value=json.dumps(state)),
                patch.object(aws, "aws_command", side_effect=[{"Tags": [{"ResourceId": identity}]}, {"Roles": []}, {"InstanceProfiles": []}]),
                self.assertRaisesRegex(core.BootstrapError, "outside bootstrap state"),
            ):
                aws.verify_ownership(plan, self.runner)

    def test_resolve_pins_ami_and_checks_manifest_inputs(self) -> None:
        """Freeze the AMI and provisioning identity whenever deployment state exists."""
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        changed = replace(plan.config, aws=replace(plan.config.aws, instance_type="t3.medium"))
        for started in (False, True):
            self.manifest(plan, started=started)
            with (
                self.subTest(started=started),
                patch.object(aws.shutil, "which", return_value="stub"),
                patch.object(aws, "verify_identity"),
                patch.object(aws, "verify_ssh_identity"),
                patch.object(aws, "detect_repository", return_value=self.repository),
                patch.object(aws, "aws_command") as command,
            ):
                resolved = aws.resolve_plan(plan.config, self.runner, self.root)
                self.assertEqual(resolved.ami_id, plan.ami_id)
                with self.assertRaisesRegex(core.BootstrapError, "inputs or template changed"):
                    aws.resolve_plan(changed, self.runner, self.root)
                command.assert_not_called()

    def test_resolve_refreshes_pre_apply_manifest(self) -> None:
        """Refresh the AMI and editable inputs before any apply or state exists."""
        plan = self.plan()
        for change in ("unchanged", "configuration", "template"):
            self.manifest(plan)
            candidate = plan.config
            if change == "configuration":
                candidate = replace(candidate, aws=replace(candidate.aws, instance_type="t3.medium"))
            elif change == "template":
                template = self.root / "terraform/aws-vm/main.tf"
                template.write_text(template.read_text() + "\n# Updated provisioning template\n")
            with (
                self.subTest(change=change),
                patch.object(aws.shutil, "which", return_value="stub"),
                patch.object(aws, "verify_identity"),
                patch.object(aws, "verify_ssh_identity"),
                patch.object(aws, "detect_repository", return_value=self.repository),
                patch.object(
                    aws, "aws_command", return_value={"Images": [{"ImageId": "ami-456def", "CreationDate": "2026-10-15T00:00:00Z"}]}
                ) as command,
            ):
                resolved = aws.resolve_plan(candidate, self.runner, self.root)
                self.assertEqual(resolved.ami_id, "ami-456def")
                command.assert_called_once()
                self.assertEqual(
                    aws.read_manifest(plan.directory),
                    {"identity": aws.provision_identity(candidate, self.root), "ami_id": "ami-456def", "apply_started": False},
                )

    def test_state_without_manifest_is_not_adopted(self) -> None:
        """Never treat existing unowned state as a disposable pre-apply plan."""
        plan = self.plan()
        runtime = plan.directory / "runtime"
        runtime.mkdir()
        (runtime / "terraform.tfstate").write_text("{}")
        with (
            patch.object(aws.shutil, "which", return_value="stub"),
            patch.object(aws, "verify_identity"),
            patch.object(aws, "verify_ssh_identity"),
            patch.object(aws, "detect_repository", return_value=self.repository),
            patch.object(aws, "aws_command") as command,
            self.assertRaisesRegex(core.BootstrapError, "Unowned Terraform state"),
        ):
            aws.resolve_plan(plan.config, self.runner, self.root)
        command.assert_not_called()

    def test_missing_applied_state_is_not_recreated(self) -> None:
        plan = self.plan()
        self.manifest(plan, started=True)
        with (
            patch.object(aws.shutil, "which", return_value="stub"),
            patch.object(aws, "verify_identity"),
            patch.object(aws, "verify_ssh_identity"),
            patch.object(aws, "detect_repository", return_value=self.repository),
            self.assertRaisesRegex(core.BootstrapError, "state is missing"),
        ):
            aws.resolve_plan(plan.config, self.runner, self.root)

    def test_only_one_bootstrap_holds_deployment_lock(self) -> None:
        with (
            aws.deployment_lock(self.load(), self.root),
            self.assertRaisesRegex(core.BootstrapError, "lock"),
            aws.deployment_lock(self.load(), self.root),
        ):
            pass

    def test_aws_dns_checkpoint_has_no_dhcp_or_hosts_instructions(self) -> None:
        with (
            patch.object(network.socket, "getaddrinfo", side_effect=socket.gaierror),
            self.assertRaisesRegex(core.BootstrapError, "Elastic IP") as raised,
        ):
            network.verify_dns(self.plan(), "8.8.4.4", discovered=True)
        self.assertNotIn("DHCP", str(raised.exception))
        self.assertNotIn("test-cloudflare-secret", str(raised.exception))

    def test_ssh_trust_uses_ssm_not_tofu(self) -> None:
        plan = self.plan()
        plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4="8.8.4.4")))
        self.runner.run.side_effect = ["8.8.4.4 ssh-ed25519 AAAAhost\n", ""]
        with patch.object(aws, "ssm", return_value="ssh-ed25519 AAAAhost root@guest"):
            aws.establish_ssh_trust(plan, self.runner, "i-123")
        self.assertEqual(plan.known_hosts.read_text(), "8.8.4.4 ssh-ed25519 AAAAhost\n")
        self.assertIn("StrictHostKeyChecking=yes", self.runner.run.call_args.args[0])

    def test_ssh_mismatch_is_not_trusted(self) -> None:
        plan = self.plan()
        self.runner.run.return_value = "8.8.4.4 ssh-ed25519 AAAAdifferent\n"
        with patch.object(aws, "ssm", return_value="ssh-ed25519 AAAAhost"), self.assertRaisesRegex(core.BootstrapError, "does not match"):
            aws.establish_ssh_trust(plan, self.runner, "i-123")
        self.assertFalse(plan.known_hosts.exists())

    def test_ssh_keyscan_ignores_comments_and_malformed_lines(self) -> None:
        """Only complete keyscan records participate in exact SSM key matching."""
        plan = self.plan()
        plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4="8.8.4.4")))
        self.runner.run.side_effect = [
            "# ssh-ed25519 AAAAuntrusted\ninvalid\n8.8.4.4 ssh-ed25519 AAAAextra comment\n"
            "8.8.4.4 ssh-ed25519 AAAAhost\n8.8.4.4 ssh-ed25519 AAAAhost\n",
            "",
        ]
        with patch.object(aws, "ssm", return_value="ssh-ed25519 AAAAhost"):
            aws.establish_ssh_trust(plan, self.runner, "i-123")
        self.assertEqual(plan.known_hosts.read_text(), "8.8.4.4 ssh-ed25519 AAAAhost\n")

    def test_stored_host_trust_is_never_overwritten(self) -> None:
        plan = self.plan()
        plan.known_hosts.write_text("previous key")
        self.runner.run.return_value = "8.8.4.4 ssh-ed25519 AAAAhost\n"
        with patch.object(aws, "ssm", return_value="ssh-ed25519 AAAAhost"), self.assertRaisesRegex(core.BootstrapError, "trust changed"):
            aws.establish_ssh_trust(plan, self.runner, "i-123")
        self.assertEqual(plan.known_hosts.read_text(), "previous key")

    def test_ssm_checks_exact_instance_and_success(self) -> None:
        with patch.object(
            aws, "aws_command", side_effect=[{"Command": {"CommandId": "command-1"}}, {"Status": "Success", "StandardOutputContent": "ok"}]
        ) as command:
            self.assertEqual(aws.ssm(self.plan(), self.runner, "i-123", ["true"]), "ok")
        self.assertIn("i-123", command.call_args_list[0].args[2])
        self.assertIn("i-123", command.call_args_list[1].args[2])

    def test_ssm_failure_is_not_accepted(self) -> None:
        with (
            patch.object(
                aws, "aws_command", side_effect=[{"Command": {"CommandId": "command-1"}}, {"Status": "Failed", "StandardErrorContent": "secret"}]
            ),
            self.assertRaisesRegex(core.BootstrapError, "guest check failed") as raised,
        ):
            aws.ssm(self.plan(), self.runner, "i-123", ["true"])
        self.assertNotIn("secret", str(raised.exception))

    def storage_manifest(self, plan: core.AwsPlan, **fields: object) -> None:
        self.manifest(plan)
        manifest = aws.read_manifest(plan.directory)
        manifest.update(data_volume_id="vol-123", instance_id="i-123", **fields)
        deploy.atomic_write(plan.directory / "manifest.json", json.dumps(manifest))

    def test_raw_volume_requires_approved_creation_receipt(self) -> None:
        plan = self.plan()
        self.storage_manifest(plan)
        with patch.object(aws, "ssm", return_value=""), self.assertRaisesRegex(core.BootstrapError, "initialization"):
            aws.initialize_storage(plan, self.runner, "i-123", "vol-123")

    def test_fresh_owned_volume_initializes_only_once(self) -> None:
        plan = self.plan()
        self.storage_manifest(plan, allow_storage_initialization=True)
        volume = {
            "Volumes": [
                {
                    "VolumeId": "vol-123",
                    "SnapshotId": "",
                    "Tags": [{"Key": "Name", "Value": "docker-aws-data"}],
                    "Attachments": [{"InstanceId": "i-123", "State": "attached"}],
                }
            ]
        }
        with (
            patch.object(aws, "ssm", side_effect=["", ""]) as ssm,
            patch.object(aws, "aws_command", return_value=volume),
            patch.object(aws, "verify_storage"),
        ):
            aws.initialize_storage(plan, self.runner, "i-123", "vol-123")
        self.assertIn("mkfs.ext4", ssm.call_args.args[3][0])
        manifest = aws.read_manifest(plan.directory)
        self.assertTrue(manifest["storage_initialized"])
        self.assertTrue(manifest["storage_initialization_started"])

    def test_previously_initialized_corrupt_volume_is_not_formatted(self) -> None:
        plan = self.plan()
        self.storage_manifest(plan, allow_storage_initialization=True, storage_initialized=True)
        with patch.object(aws, "ssm", return_value="") as ssm, self.assertRaisesRegex(core.BootstrapError, "initialization"):
            aws.initialize_storage(plan, self.runner, "i-123", "vol-123")
        self.assertEqual(ssm.call_count, 1)

    def test_existing_ext4_is_mounted_without_formatting(self) -> None:
        plan = self.plan()
        self.storage_manifest(plan, storage_initialized=True)
        with patch.object(aws, "ssm", side_effect=["ext4", ""]) as ssm, patch.object(aws, "verify_storage"):
            aws.initialize_storage(plan, self.runner, "i-123", "vol-123")
        self.assertNotIn("mkfs", ssm.call_args.args[3][0])

    def test_interrupted_format_is_not_retried_automatically(self) -> None:
        plan = self.plan()
        self.storage_manifest(plan, allow_storage_initialization=True, storage_initialization_started=True)
        with patch.object(aws, "ssm", return_value=""), self.assertRaisesRegex(core.BootstrapError, "initialization"):
            aws.initialize_storage(plan, self.runner, "i-123", "vol-123")

    def test_ready_resumes_only_the_owned_stopped_instance(self) -> None:
        results = [
            {"Reservations": [{"Instances": [{"InstanceId": "i-123", "State": {"Name": "stopped"}}]}]},
            {},
            {},
            {},
            {"InstanceInformationList": [{"InstanceId": "i-123", "PingStatus": "Online"}]},
        ]
        with patch.object(aws, "aws_command", side_effect=results) as command, patch.object(aws, "ssm") as ssm:
            aws.wait_ready(self.plan(), self.runner, "i-123")
        self.assertEqual(command.call_args_list[1].args[2], ["ec2", "start-instances", "--instance-ids", "i-123"])
        self.assertIn("cloud-init status --wait", ssm.call_args.args[3][0])

    def test_terminated_instance_is_never_recreated(self) -> None:
        result = {"Reservations": [{"Instances": [{"InstanceId": "i-123", "State": {"Name": "terminated"}}]}]}
        with patch.object(aws, "aws_command", return_value=result) as command, self.assertRaisesRegex(core.BootstrapError, "not resumable"):
            aws.wait_ready(self.plan(), self.runner, "i-123")
        self.assertEqual(command.call_count, 1)

    def test_preflight_never_applies_cloud_resources(self) -> None:
        """Accept EBS NVMe support without applying any cloud resources."""
        plan = self.plan()
        self.runner.run.return_value = "8.8.8.8"
        for support in ("supported", "required"):
            instance = {"ProcessorInfo": {"SupportedArchitectures": ["x86_64"]}, "EbsInfo": {"NvmeSupport": support}}
            with (
                self.subTest(support=support),
                patch.object(
                    aws,
                    "aws_command",
                    side_effect=[
                        {"Images": [{"ImageId": plan.ami_id, "Architecture": "x86_64", "State": "available"}]},
                        {"InstanceTypes": [instance]},
                    ],
                ),
                patch.object(aws, "verify_ownership"),
                patch.object(aws, "verify_public_repository"),
                patch.object(aws, "terraform") as terraform,
                patch.object(aws, "plan_infrastructure", return_value=[]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                aws.preflight(plan, self.runner, self.root)
            self.assertEqual(terraform.call_args.args[2], ["init", "-input=false"])
            self.assertIn("--ipv4", self.runner.run.call_args.args[0])

    def test_preflight_still_rejects_invalid_or_unpermitted_admin_addresses(self) -> None:
        """Forcing IPv4 must not bypass address parsing or the administrator CIDR."""
        for address, message in (
            ("2001:4860:4860::8888", "Could not determine administrator public IPv4 address"),
            ("not-an-address", "Could not determine administrator public IPv4 address"),
            ("8.8.4.4", "outside aws.admin_source_cidr"),
        ):
            self.runner.run.return_value = address
            with (
                self.subTest(address=address),
                patch.object(aws, "terraform") as terraform,
                self.assertRaisesRegex(core.BootstrapError, message),
            ):
                aws.preflight(self.plan(), self.runner, self.root)
            terraform.assert_not_called()

    def test_preflight_rejects_missing_or_unsupported_ebs_nvme(self) -> None:
        """Fail before Terraform initialization when EBS NVMe cannot be verified."""
        plan = self.plan()
        self.runner.run.return_value = "8.8.8.8"
        for ebs_info in ({}, {"NvmeSupport": "unsupported"}, {"NvmeSupport": "unknown"}):
            instance = {"ProcessorInfo": {"SupportedArchitectures": ["x86_64"]}, "EbsInfo": ebs_info}
            with (
                self.subTest(ebs_info=ebs_info),
                patch.object(
                    aws,
                    "aws_command",
                    side_effect=[
                        {"Images": [{"ImageId": plan.ami_id, "Architecture": "x86_64", "State": "available"}]},
                        {"InstanceTypes": [instance]},
                    ],
                ),
                patch.object(aws, "verify_public_repository"),
                patch.object(aws, "render_provisioning") as render,
                patch.object(aws, "terraform") as terraform,
                self.assertRaisesRegex(core.BootstrapError, "EBS NVMe"),
            ):
                aws.preflight(plan, self.runner, self.root)
            render.assert_not_called()
            terraform.assert_not_called()

    def test_apply_uses_exact_saved_plan_and_shared_pipeline(self) -> None:
        plan = self.plan()
        self.manifest(plan)
        names = [
            "wait_ready",
            "initialize_storage",
            "verify_storage",
            "establish_ssh_trust",
            "verify_dns",
            "render_config",
            "configure_host",
            "prepare_remote_repository",
            "deploy_services",
            "verify_services",
        ]
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(aws, "verify_identity"))
            terraform = stack.enter_context(patch.object(aws, "terraform", return_value="{}"))
            stack.enter_context(patch.object(aws, "output", side_effect=["i-123abc", "8.8.4.4", "vol-123abc"]))
            stack.enter_context(patch.object(aws, "plan_infrastructure", return_value=[]))
            mocks = {name: stack.enter_context(patch.object(aws, name)) for name in names}
            aws.apply(plan, self.runner, assume_yes=True, root=self.root)
        self.assertEqual(terraform.call_args.args[2], ["apply", "-input=false", "-lock-timeout=30s", "bootstrap.tfplan"])
        for name in names:
            self.assertTrue(mocks[name].called, name)
        rendered = mocks["render_config"].call_args.args[0]
        self.assertEqual(rendered.config.network.expected_ipv4, "8.8.4.4")
        self.assertIsNone(plan.config.network.expected_ipv4)

    def test_dns_checkpoint_stops_before_secret_render_and_ansible(self) -> None:
        plan = self.plan()
        self.manifest(plan)
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            for name in ("verify_identity", "terraform", "wait_ready", "initialize_storage", "verify_storage", "establish_ssh_trust"):
                stack.enter_context(patch.object(aws, name, return_value="{}" if name == "terraform" else None))
            stack.enter_context(patch.object(aws, "output", side_effect=["i-123abc", "8.8.4.4", "vol-123abc"]))
            stack.enter_context(patch.object(aws, "verify_dns", side_effect=core.BootstrapError("AWS DNS checkpoint")))
            render = stack.enter_context(patch.object(aws, "render_config"))
            ansible = stack.enter_context(patch.object(aws, "configure_host"))
            with self.assertRaisesRegex(core.BootstrapError, "DNS checkpoint"):
                aws.apply(plan, self.runner, assume_yes=True, root=self.root)
        render.assert_not_called()
        ansible.assert_not_called()

    def test_managed_dns_reconciles_after_trust_before_resolver_and_services(self) -> None:
        plan = self.plan()
        settings = core.DnsConfig(
            "managed", True, core.CloudflareDnsConfig("example.com"), core.AdguardDnsConfig("https://dns.example.com", "operator", "test-password")
        )
        plan = replace(plan, config=replace(plan.config, network=replace(plan.config.network, dns=settings)))
        names = [
            "wait_ready",
            "initialize_storage",
            "verify_storage",
            "establish_ssh_trust",
            "reconcile_dns",
            "verify_dns",
            "render_config",
            "configure_host",
            "prepare_remote_repository",
            "deploy_services",
            "verify_services",
        ]
        order = Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(aws, "output", side_effect=["i-123abc", "8.8.4.4", "vol-123abc"]))
            stack.enter_context(patch.object(aws, "plan_infrastructure", return_value=[]))
            mocks = {name: stack.enter_context(patch.object(aws, name)) for name in names}
            for name, mock in mocks.items():
                order.attach_mock(mock, name)
            aws.complete_deployment(plan, self.runner, {}, self.root)
        calls = [call[0] for call in order.mock_calls]
        self.assertLess(calls.index("establish_ssh_trust"), calls.index("reconcile_dns"))
        self.assertLess(calls.index("reconcile_dns"), calls.index("verify_dns"))
        self.assertLess(calls.index("verify_dns"), calls.index("render_config"))
        self.assertEqual(mocks["reconcile_dns"].call_args.args[1], "8.8.4.4")
        self.assertEqual(mocks["verify_dns"].call_args.kwargs["wait_seconds"], 60)
