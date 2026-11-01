Prometheus exporter for machine metrics, written in Go with pluggable metric collectors.

The Compose project/service/container name is `node-exporter`. The exporter
bundled with the Prometheus stack uses the same service/container name. Scrape
it as `node-exporter:9100` on a shared network; the Prometheus job label remains
`node_exporter` for dashboard/query compatibility. Existing deployments using
the old service name need an explicit migration of their old container; changing
the YAML alone does not rename a running container.

## References

- Home: [Monitoring Linux host metrics with the Node Exporter | Prometheus](https://prometheus.io/docs/guides/node-exporter/)
- Source: [GitHub - prometheus/node_exporter: Exporter for machine metrics](https://github.com/prometheus/node_exporter)
- Image: [prom/node-exporter - Docker Image](https://hub.docker.com/r/prom/node-exporter/)
