Endlessh is an SSH tarpit that very slowly sends an endless, random SSH banner. It keeps SSH clients locked up for hours or even days at a time.
The purpose is to put your real SSH server on another port and then let the script kiddies get stuck in this tarpit instead of bothering a real server.

endlessh-go is a golang implementation of endlessh exporting Prometheus metrics, visualized by a Grafana dashboard.

## Metrics and Kubernetes discovery

Prometheus metrics are enabled explicitly on TCP 2112 and declared with Compose
`expose`; only the tarpit port 2222 is published. Konverter's LoadBalancer mode
therefore produces internal Service `endlessh:2112` and a separate published
Service for 2222. A configured LAN grant covers the tarpit backend, not metrics.

Prometheus in another namespace uses `endlessh.endlessh.svc:2112` and its own
caller-owned connection labels. The matching namespaces/workload identities and
metrics Service must exist; a repeated Compose network name does not grant
cross-namespace access. Do not publish metrics merely to bypass a missing policy.

The production command/storage/GeoIP settings are unchanged. Synthetic tests can
disable GeoIP and use stderr logging without persistent volumes, but those
choices do not migrate or validate the real application's configuration.

## Grafana dashboard

- [GitHub - shizunge/endlessh-go: A golang implementation of endlessh (SSH tarpit) exporting Prometheus metrics, visualized by a Grafana dashboard.](https://github.com/shizunge/endlessh-go/?tab=readme-ov-file#dashboard)
- [Endlessh | Grafana Labs](https://grafana.com/grafana/dashboards/15156-endlessh/)

## References

- Source: [GitHub - shizunge/endlessh-go: A golang implementation of endlessh (SSH tarpit) exporting Prometheus metrics, visualized by a Grafana dashboard.](https://github.com/shizunge/endlessh-go/)
- C implementation: [GitHub - skeeto/endlessh: SSH tarpit that slowly sends an endless banner](https://github.com/skeeto/endlessh/)
- Developer's blogpost: [Endlessh: an SSH Tarpit](https://nullprogram.com/blog/2019/03/22/)
