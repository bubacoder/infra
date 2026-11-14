Prometheus is a systems and service monitoring system. It collects metrics from configured targets at given intervals, evaluates rule expressions, displays the results, and can trigger alerts if some condition is observed to be true.

## Docker and Kubernetes scrape configuration

Docker retains `config/prometheus.yaml` and the `endlessh:2112` target by default.
`PROMETHEUS_CONFIG_FILE` explicitly selects another file under `/etc/prometheus`.
For Konverter, supply
`--env PROMETHEUS_CONFIG_FILE=prometheus.kubernetes.yaml` to select the tracked
Kubernetes variant. It changes only the Endlessh scrape target to
`endlessh.endlessh.svc:2112`; other jobs and labels remain unchanged. Tests enforce
that these two configurations differ only by this reviewed target.

Convert Endlessh separately into namespace `endlessh` so its internal metrics
Service exists. The caller-owned labels grant only this Prometheus workload
TCP 2112 access in that namespace. Neither network membership alone nor the
labels create the remote Service or rewrite application configuration.

This prepares discovery, not a full stack migration: cAdvisor still requires
explicit handling of its unsupported device mapping and Docker-specific host
paths; node-exporter uses host PID/root mounts. Do not treat partial conversion
or a rollout as collector compatibility. Storage, admission, metrics readiness
and a successful Prometheus scrape require separate functional validation.
No existing Docker or Kubernetes workload is redeployed by these source changes.

## References

- Home: [Prometheus - Monitoring system & time series database](https://prometheus.io/)
- Image: [prom/prometheus - Docker Image](https://hub.docker.com/r/prom/prometheus)
- Introduction: [Overview | Prometheus](https://prometheus.io/docs/introduction/overview/)

Recommended collectors:
- [prom/node-exporter - Docker Image](https://hub.docker.com/r/prom/node-exporter/)
- [GitHub - google/cadvisor: Analyzes resource usage and performance characteristics of running containers.](https://github.com/google/cadvisor/)
- [GitHub - shizunge/endlessh-go: A golang implementation of endlessh (SSH tarpit) exporting Prometheus metrics, visualized by a Grafana dashboard.](https://github.com/shizunge/endlessh-go/)
