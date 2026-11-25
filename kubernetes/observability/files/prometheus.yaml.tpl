global:
  scrape_interval: 30s
  evaluation_interval: 30s
  external_labels:
    cluster: {{ .Values.cluster }}
rule_files: [/config/rules.yaml]
scrape_configs:
  - job_name: observability
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [{{ .Release.Namespace }}]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]
        regex: prometheus|query|fluent-bit|node-exporter
        action: keep
      - source_labels: [__meta_kubernetes_pod_container_port_name]
        regex: metrics
        action: keep
      - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]
        target_label: component
      - source_labels: [__meta_kubernetes_pod_node_name]
        target_label: node
      - source_labels: [component]
        regex: fluent-bit
        target_label: __metrics_path__
        replacement: /api/v1/metrics/prometheus
  {{ range $name, $path := dict "kubelet" "/metrics" "kubelet-cadvisor" "/metrics/cadvisor" }}
  - job_name: {{ $name }}
    scheme: https
    metrics_path: {{ $path }}
    authorization:
      credentials_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - source_labels: [__meta_kubernetes_node_name]
        target_label: node
  {{ end }}
  {{ with .Values.prometheus.extraScrapeConfigs }}
  {{ toYaml . | nindent 2 }}
  {{ end }}
