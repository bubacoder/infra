Endlessh is an SSH tarpit that very slowly sends an endless, random SSH banner. It keeps SSH clients locked up for hours or even days at a time.
The purpose is to put your real SSH server on another port and then let the script kiddies get stuck in this tarpit instead of bothering a real server.

endlessh-go is a golang implementation of endlessh exporting Prometheus metrics, visualized by a Grafana dashboard.

Links:
- Source: https://github.com/shizunge/endlessh-go/
- C implementation: https://github.com/skeeto/endlessh/
- Developer's blogpost: https://nullprogram.com/blog/2019/03/22/

Setup Grafana dashboard:
- https://github.com/shizunge/endlessh-go/?tab=readme-ov-file#dashboard
- https://grafana.com/grafana/dashboards/15156-endlessh/
