Endlessh is an SSH tarpit that very slowly sends an endless, random SSH banner. It keeps SSH clients locked up for hours or even days at a time.
The purpose is to put your real SSH server on another port and then let the script kiddies get stuck in this tarpit instead of bothering a real server.

endlessh-go is a golang implementation of endlessh exporting Prometheus metrics, visualized by a Grafana dashboard.

Links:
- Source: [GitHub - shizunge/endlessh-go: A golang implementation of endlessh (SSH tarpit) exporting Prometheus metrics, visualized by a Grafana dashboard.](https://github.com/shizunge/endlessh-go/)
- C implementation: [GitHub - skeeto/endlessh: SSH tarpit that slowly sends an endless banner](https://github.com/skeeto/endlessh/)
- Developer's blogpost: [Endlessh: an SSH Tarpit](https://nullprogram.com/blog/2019/03/22/)

Setup Grafana dashboard:
- [GitHub - shizunge/endlessh-go: A golang implementation of endlessh (SSH tarpit) exporting Prometheus metrics, visualized by a Grafana dashboard.](https://github.com/shizunge/endlessh-go/?tab=readme-ov-file#dashboard)
- [Endlessh | Grafana Labs](https://grafana.com/grafana/dashboards/15156-endlessh/)
