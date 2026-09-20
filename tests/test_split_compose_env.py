"""Tests for split-compose-env.py."""

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import yaml

MODULE_PATH = Path(__file__).parent.parent / "scripts/split-compose-env.py"
SPEC = importlib.util.spec_from_file_location("split_compose_env", MODULE_PATH)
split_compose_env = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load split-compose-env.py")
SPEC.loader.exec_module(split_compose_env)


class SplitEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.host = self.root / "host"
        self.stacks = self.root / "docker"
        self.host.mkdir()
        for service, content in {
            "alpha": "services:\n  alpha:\n    image: ${SHARED}\n    environment:\n      ONE: ${ALPHA_ONLY}\n      PATH: ${DERIVED}\n",
            "beta": "services:\n  beta:\n    image: ${SHARED}\n    environment:\n      PATH: ${DERIVED}\n      TWO: ${BETA_ONLY:-default}\n",
        }.items():
            directory = self.stacks / "category" / service
            directory.mkdir(parents=True)
            (directory / f"{service}.yaml").write_text(content)
        (self.host / ".env").write_text(
            "# Shared values\nSHARED=value\nROOT=/srv\nDERIVED=${ROOT}/data\nALPHA_ONLY=alpha\nBETA_ONLY=beta\nGPU_COMPOSE_SUFFIX=amdgpu\n"
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_splits_single_service_values_and_keeps_transitive_shared_values(self) -> None:
        split_compose_env.split_environment(self.host, self.stacks)
        main = (self.host / ".env").read_text()
        if "SHARED=value" not in main or "ROOT=/srv" not in main or "DERIVED=${ROOT}/data" not in main:
            self.fail("Shared values were not retained in the main environment")
        if "ALPHA_ONLY=alpha" in main or "BETA_ONLY=beta" in main:
            self.fail("Service-only values were retained in the main environment")
        if "# Operational settings not consumed by Docker Compose deployments" not in main:
            self.fail("Operational settings were not placed in their own section")
        if "GPU_COMPOSE_SUFFIX=amdgpu" not in main:
            self.fail("Operational value was removed")
        if "ALPHA_ONLY=alpha" not in (self.host / ".env.alpha").read_text():
            self.fail("Alpha value was not moved")
        if "BETA_ONLY=beta" not in (self.host / ".env.beta").read_text():
            self.fail("Beta value was not moved")

    def test_preserves_existing_service_override_without_duplicate_assignment(self) -> None:
        (self.host / ".env.alpha").write_text("ALPHA_ONLY=override\n")
        split_compose_env.split_environment(self.host, self.stacks)
        alpha = (self.host / ".env.alpha").read_text()
        if alpha.count("ALPHA_ONLY=") != 1 or "ALPHA_ONLY=override" not in alpha:
            self.fail("Existing service override was changed or duplicated")

    def test_creates_service_files_with_private_permissions(self) -> None:
        split_compose_env.split_environment(self.host, self.stacks)
        if (self.host / ".env.alpha").stat().st_mode & 0o777 != 0o600:
            self.fail("New service environment file is not private")

    def test_check_mode_does_not_modify_files(self) -> None:
        before = (self.host / ".env").read_text()
        split_compose_env.split_environment(self.host, self.stacks, write=False)
        if (self.host / ".env").read_text() != before or (self.host / ".env.alpha").exists():
            self.fail("Check mode modified environment files")


class RepositoryResolutionTests(unittest.TestCase):
    def test_example_environment_retains_each_service_effective_values(self) -> None:
        repository = MODULE_PATH.parent.parent
        with tempfile.TemporaryDirectory() as temporary:
            host = Path(temporary) / "myhost"
            host.mkdir()
            source = repository / "config-example/docker/myhost"
            (host / ".env").write_text((source / ".env").read_text())
            source_service_values = {
                env_file.name.removeprefix(".env."): {entry.name: entry.value for entry in split_compose_env.environment_entries(env_file)[0]}
                for env_file in source.glob(".env.*")
            }
            for env_file in source.glob(".env.*"):
                (host / env_file.name).write_text(env_file.read_text())
            split_compose_env.split_environment(host, repository / "docker")
            original_entries = split_compose_env.environment_entries(source / ".env")[0]
            original_main = {entry.name: entry.value for entry in original_entries}
            result_main = {entry.name: entry.value for entry in split_compose_env.environment_entries(host / ".env")[0]}
            variables_by_service: dict[str, set[str]] = defaultdict(set)
            consumers = split_compose_env.compose_consumers(repository / "docker")
            for variable, services in consumers.items():
                for service in services:
                    variables_by_service[service].add(variable)
            for service, variables in variables_by_service.items():
                before = original_main | source_service_values.get(service, {})
                after_service = host / f".env.{service}"
                after = result_main | (
                    {entry.name: entry.value for entry in split_compose_env.environment_entries(after_service)[0]} if after_service.exists() else {}
                )
                missing = variables & before.keys() - after.keys()
                if missing:
                    self.fail(f"{service} lost Compose values: {sorted(missing)}")
                changed = {variable for variable in variables & before.keys() if before[variable] != after[variable]}
                if changed:
                    self.fail(f"{service} changed Compose values: {sorted(changed)}")
            expanded = split_compose_env.expand_consumers(original_entries, consumers)
            missing_shared = {entry.name for entry in original_entries if len(expanded.get(entry.name, set())) > 1 and entry.name not in result_main}
            if missing_shared:
                self.fail(f"Shared values were moved out of the main environment: {sorted(missing_shared)}")

    @unittest.skipUnless(shutil.which("docker"), "Docker is not installed")
    def test_enabled_example_services_render_with_docker_compose(self) -> None:
        repository = MODULE_PATH.parent.parent
        source_config = repository / "config-example/docker"
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "docker"
            host_dir = config_dir / "myhost"
            host_dir.mkdir(parents=True)
            for source in [source_config / ".env", *(source_config / "myhost").glob(".env*")]:
                target = config_dir / source.name if source.parent == source_config else host_dir / source.name
                target.write_text(source.read_text().replace("xxx.xxx.xxx.xxx", "127.0.0.1"))

            service_config = yaml.safe_load((source_config / "myhost/services.yaml").read_text())
            main_values = {entry.name: entry.value for entry in split_compose_env.environment_entries(host_dir / ".env")[0]}
            gpu_suffix = main_values.get("GPU_COMPOSE_SUFFIX")
            enabled: list[tuple[str, str]] = []
            for category_config in service_config["services"]:
                category, services = next(iter(category_config.items()))
                enabled.extend((category, item["name"]) for item in services if item.get("state") == "up")

            for category, service in enabled:
                compose_file = repository / "docker" / category / service / f"{service}.yaml"
                if not compose_file.is_file():
                    continue
                command = [
                    "docker",
                    "compose",
                    "--env-file",
                    str(config_dir / ".env"),
                    "--env-file",
                    str(host_dir / ".env"),
                    "-f",
                    str(compose_file),
                ]
                service_env = host_dir / f".env.{service}"
                if service_env.is_file():
                    command.extend(("--env-file", str(service_env)))
                override = compose_file.parent / f"{service}-{gpu_suffix}.yaml"
                if gpu_suffix and override.is_file():
                    command.extend(("-f", str(override)))
                completed = subprocess.run(  # noqa: S603 -- Command is built from repository Compose paths.
                    command + ["config", "--quiet"], capture_output=True, text=True, check=False
                )
                if completed.returncode:
                    self.fail(f"{category}/{service} does not render:\n{completed.stderr}")


if __name__ == "__main__":
    unittest.main()
