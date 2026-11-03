"""Offline contracts for explicit UniFi/MongoDB Kubernetes preparation."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class UniFiMongoDBTests(unittest.TestCase):
    def setUp(self):
        self.unifi = yaml.safe_load((ROOT / "docker/infra/unifi-network-application/unifi-network-application.yaml").read_text())["services"][
            "unifi-network-application"
        ]
        self.database = yaml.safe_load((ROOT / "docker/database/mongodb/mongodb.yaml").read_text())["services"]["mongodb"]

    def test_database_host_can_be_selected_without_changing_docker_default(self):
        if self.unifi["environment"]["MONGO_HOST"] != "${UNIFI_MONGO_HOST:-mongodb}":
            self.fail("Preserve Docker DNS by default and allow explicit qualified Kubernetes DNS")
        if self.unifi["environment"]["MONGO_PORT"] != 27017 or self.unifi["environment"]["MONGO_AUTHSOURCE"] != "admin":
            self.fail("Do not silently change MongoDB port or authentication source")

    def test_transport_reference_is_selectable_without_creating_tls_policy(self):
        labels = self.unifi["labels"]
        if (
            labels["traefik.http.services.unifi-network-application.loadbalancer.serversTransport"]
            != "${UNIFI_TRAEFIK_SERVERS_TRANSPORT:-insecureTransport@file}"
        ):
            self.fail("Keep the Docker transport default while permitting an explicit bootstrap-owned reference")
        if labels["konverter.connect.mongodb.service"] != "mongodb/mongodb" or labels["konverter.connect.mongodb.ports"] != "27017/tcp":
            self.fail("Keep caller trust limited to MongoDB TCP 27017")

    def test_database_has_explicit_internal_exposure_and_unchanged_publication(self):
        if self.database.get("expose") != ["27017"] or self.database["ports"] != ["27017:27017"]:
            self.fail("Add internal discovery without removing or remapping the existing Docker publication")

    def test_all_existing_unifi_device_ports_remain_explicit(self):
        expected = ["8443:8443", "3478:3478/udp", "10001:10001/udp", "8080:8080", "8843:8843", "8880:8880", "6789:6789", "5514:5514/udp"]
        if self.unifi["ports"] != expected:
            self.fail("Do not drop device/admin protocols or infer new discovery behavior")


if __name__ == "__main__":
    unittest.main()
