{{- if has .Release.Namespace .Values.collector.namespaces }}
{{- fail "Do not collect the backend/collector namespace: diagnostic feedback is excluded" }}
{{- end }}
{{- if .Values.grafana.oidc.enabled }}
{{- if or (not (hasPrefix "https://" .Values.grafana.oidc.authBaseUrl)) (ne (urlParse .Values.grafana.oidc.authBaseUrl).hostname .Values.grafana.oidc.host) }}
{{- fail "OIDC requires an explicit HTTPS authBaseUrl and matching host for private egress" }}
{{- end }}
{{- end }}
{{- range $component, $files := dict "loki" (list "loki.yaml") "prometheus" (list "prometheus.yaml" "rules.yaml") "grafana" (list "grafana.ini") "fluent-bit" (list "fluent-bit.conf" "normalize.lua") "query" (list "nginx.conf") }}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
data:
  {{- range $file := $files }}
  {{ $file }}: |
    {{- if or (eq $file "normalize.lua") (eq $file "rules.yaml") }}
    {{- $.Files.Get (printf "files/%s" $file) | nindent 4 }}
    {{- else }}
    {{- $suffix := ternary ".tpl" "" (or (eq $file "loki.yaml") (eq $file "prometheus.yaml")) }}
    {{- tpl ($.Files.Get (printf "files/%s%s" $file $suffix)) $ | nindent 4 }}
    {{- end }}
  {{- end }}
  {{- if eq $component "grafana" }}
  datasources.yaml: |
    apiVersion: 1
    datasources:
      - name: Native Prometheus
        uid: native-prometheus
        type: prometheus
        access: proxy
        url: http://{{ $.Release.Name }}-prometheus:9090
        isDefault: true
        editable: false
      - name: Native Loki
        uid: native-loki
        type: loki
        access: proxy
        url: http://{{ $.Release.Name }}-query:8080
        editable: false
        jsonData:
          maxLines: 100
  dashboards.yaml: |
    apiVersion: 1
    providers:
      - name: native
        options:
          path: /etc/grafana/dashboards
        disableDeletion: true
        editable: false
  overview.json: |
    {"uid":"native-overview","title":"Native observability","schemaVersion":39,
     "time":{"from":"now-1h","to":"now"},"panels":[
       {"id":1,"type":"timeseries","title":"Scrape health","gridPos":{"h":8,"w":12,"x":0,"y":0},
        "datasource":{"type":"prometheus","uid":"native-prometheus"},
        "targets":[{"expr":"up{job=\"observability\"}","refId":"A"}]},
       {"id":2,"type":"logs","title":"Recent application logs","gridPos":{"h":12,"w":24,"x":0,"y":8},
        "datasource":{"type":"loki","uid":"native-loki"},
        "targets":[{"expr":"{cluster=\"{{ $.Values.cluster }}\"}","refId":"A"}]}]}
  {{- end }}
{{- end }}
