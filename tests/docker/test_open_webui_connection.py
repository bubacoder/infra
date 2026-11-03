"""Offline contract for Open WebUI's explicit caller-owned Ollama grant."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class OpenWebUIConnectionTests(unittest.TestCase):
    def test_kubernetes_overlay_selects_only_the_internal_ollama_endpoint(self):
        overlay = ROOT / "config-example/kubernetes/k3s/.env.open-webui"
        bindings = [line.strip() for line in overlay.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if bindings != ["OPEN_WEBUI_OLLAMA_BASE_URL=http://ollama.ollama.svc:11434"]:
            self.fail("Keep a sparse service-specific Kubernetes override with no copied normal environment")

    def test_supported_ollama_base_url_keeps_the_docker_route_selectable(self):
        project = yaml.safe_load((ROOT / "docker/ai/open-webui/open-webui.yaml").read_text())
        environment = project["services"]["open-webui"]["environment"]
        if "OLLAMA_API_BASE_URL" in environment:
            self.fail("Do not use the deprecated Ollama endpoint variable")
        if environment.get("OLLAMA_BASE_URL") != "${OPEN_WEBUI_OLLAMA_BASE_URL:-https://ollama.${MYDOMAIN}}":
            self.fail("Keep the declared Docker HTTPS route without /api and allow explicit Kubernetes selection")

    def test_ollama_connection_is_limited_to_the_exact_service_and_tcp_port(self):
        project = yaml.safe_load((ROOT / "docker/ai/open-webui/open-webui.yaml").read_text())
        labels = project["services"]["open-webui"]["labels"]
        connections = {key: value for key, value in labels.items() if key.startswith("konverter.connect.")}
        if connections != {"konverter.connect.ollama.service": "ollama/ollama", "konverter.connect.ollama.ports": "11434/tcp"}:
            self.fail("Grant only Open WebUI to the explicit Ollama workload on TCP 11434")


if __name__ == "__main__":
    unittest.main()
