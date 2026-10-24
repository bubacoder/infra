"""Offline safety checks for the CrowdSec host enforcement configuration."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class CrowdSecEnforcementTests(unittest.TestCase):
    def test_database_uses_wal(self):
        compose = yaml.safe_load((ROOT / "docker/security/crowdsec/crowdsec.yaml").read_text())
        if compose["services"]["crowdsec"]["environment"].get("USE_WAL") != "true":
            self.fail("The local SQLite database should use WAL")

    def test_stream_mode_has_explicit_fail_closed_settings(self):
        middleware = yaml.safe_load((ROOT / "docker/security/traefik/config/dynamic/middlewares.yml").read_text())
        plugin = middleware["http"]["middlewares"]["crowdsec-bouncer"]["plugin"]["crowdsec-bouncer-traefik-plugin"]
        expected = {"CrowdsecMode": "stream", "UpdateIntervalSeconds": 60, "UpdateMaxFailure": 0, "StreamStartupBlock": True}
        for key, value in expected.items():
            if plugin.get(key) != value:
                self.fail(f"Unexpected CrowdSec stream setting: {key}")

    def test_local_api_host_port_is_loopback_only(self):
        compose = yaml.safe_load((ROOT / "docker/security/crowdsec/crowdsec.yaml").read_text())
        if compose["services"]["crowdsec"]["ports"] != ["127.0.0.1:7080:8080/tcp"]:
            self.fail("Only the local firewall bouncer needs the published LAPI port")

    def test_colony_enables_bouncer_for_host_and_docker_ipv4_ipv6(self):
        inventory = yaml.safe_load((ROOT / "ansible/inventory/inventory.yaml").read_text())
        colony = inventory["debian"]["hosts"]["colony"]
        if not colony["debian_base_install_crowdsec_bouncer"]:
            self.fail("Colony firewall enforcement must be enabled")
        if colony["debian_base_crowdsec_local_api_url"] != "http://127.0.0.1:7080/":
            self.fail("Colony must use its local CrowdSec API")
        if colony["debian_base_crowdsec_iptables_chains"] != ["INPUT", "DOCKER-USER"]:
            self.fail("Both host and Docker ingress must be protected")
        template = (ROOT / "ansible/roles/debian_base/templates/crowdsec-firewall-bouncer.yaml.local.j2").read_text()
        if "disable_ipv6: false" not in template or "iptables_chains:" not in template:
            self.fail("The managed configuration must enable dual-stack enforcement")

    def test_credentials_are_validated_before_install_and_never_logged(self):
        tasks = yaml.safe_load((ROOT / "ansible/roles/debian_base/tasks/50-crowdsec.yaml").read_text())
        credential_check = next(t for t in tasks if t["name"] == "Validate CrowdSec bouncer credentials")
        install = next(t for t in tasks if "ansible.builtin.apt" in t)
        configure = next(t for t in tasks if "ansible.builtin.template" in t)
        if tasks.index(credential_check) >= tasks.index(install):
            self.fail("Credentials must be validated before installing the service")
        if not credential_check["no_log"] or not configure["no_log"] or configure["diff"]:
            self.fail("Credential tasks must suppress logs and diffs")
        if configure["ansible.builtin.template"]["mode"] != "0600":
            self.fail("The rendered credential file must be private")
        if install["ansible.builtin.apt"]["policy_rc_d"] != 101:
            self.fail("Package installation must not prematurely start enforcement")

    def test_targeted_playbook_does_not_apply_other_host_roles(self):
        plays = yaml.safe_load((ROOT / "ansible/playbooks/crowdsec.yaml").read_text())
        if len(plays) != 1 or "roles" in plays[0]:
            self.fail("The targeted playbook must not apply complete host roles")
        role = plays[0]["tasks"][0]["ansible.builtin.import_role"]
        if role != {"name": "debian_base", "tasks_from": "50-crowdsec.yaml"}:
            self.fail("Only the firewall bouncer tasks should run")

    def test_docker_enforcement_is_deferred_until_explicit_activation(self):
        tasks = yaml.safe_load((ROOT / "ansible/roles/debian_base/tasks/main.yaml").read_text())
        configure = next(t for t in tasks if t.get("ansible.builtin.import_tasks") == "50-crowdsec.yaml")
        if "'DOCKER-USER' not in debian_base_crowdsec_iptables_chains | default(['INPUT'])" not in configure["when"]:
            self.fail("Base provisioning must not activate enforcement before Docker and the LAPI exist")

    def test_first_start_reloads_systemd_and_checks_dependencies_before_install(self):
        tasks = yaml.safe_load((ROOT / "ansible/roles/debian_base/tasks/50-crowdsec.yaml").read_text())
        install = next(t for t in tasks if "ansible.builtin.apt" in t)
        docker = next(t for t in tasks if t["name"] == "Check Docker enforcement prerequisites")
        health = next(t for t in tasks if "ansible.builtin.uri" in t)
        start = next(t for t in tasks if t["name"] == "Enable service crowdsec-firewall-bouncer")
        service = start.get("ansible.builtin.systemd_service", {})
        if not service.get("daemon_reload") or service.get("state") != "started":
            self.fail("The first service start must reload the newly written systemd drop-in")
        if tasks.index(docker) >= tasks.index(install) or tasks.index(health) >= tasks.index(install):
            self.fail("Missing prerequisites must be detected before installing or changing the bouncer")
        if health["ansible.builtin.uri"]["status_code"] != 200 or not health.get("until"):
            self.fail("Activation must wait for a healthy LAPI")
        if "ansible_facts.services['docker.service'].state == 'running'" not in docker["block"][1]["ansible.builtin.assert"]["that"]:
            self.fail("Docker must already be installed and running")
        chain = docker["block"][2]
        if chain["ansible.builtin.command"]["argv"] != ["iptables", "--wait", "-S", "DOCKER-USER"] or chain["changed_when"]:
            self.fail("Activation must verify Docker's IPv4 chain without changing firewall rules")


if __name__ == "__main__":
    unittest.main()
