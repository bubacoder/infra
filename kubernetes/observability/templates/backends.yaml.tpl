{{- range $component, $settings := dict "loki" .Values.loki "prometheus" .Values.prometheus "grafana" .Values.grafana }}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
  annotations:
    helm.sh/resource-policy: keep
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: {{ $settings.storage.class }}
  resources:
    requests:
      storage: {{ $settings.storage.size }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
spec:
  replicas: 1
  strategy: {type: Recreate}
  selector:
    matchLabels:
      app.kubernetes.io/instance: {{ $.Release.Name }}
      app.kubernetes.io/component: {{ $component }}
  template:
    metadata:
      labels:
        {{- include "obs.labels" $ | nindent 8 }}
        app.kubernetes.io/component: {{ $component }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configs.yaml.tpl") $ | sha256sum }}
    spec:
      automountServiceAccountToken: {{ eq $component "prometheus" }}
      {{- if eq $component "prometheus" }}
      serviceAccountName: {{ $.Release.Name }}-prometheus
      {{- end }}
      securityContext:
        runAsNonRoot: true
        runAsUser: {{ if eq $component "grafana" }}472{{ else if eq $component "loki" }}10001{{ else }}65534{{ end }}
        runAsGroup: {{ if eq $component "grafana" }}472{{ else if eq $component "loki" }}10001{{ else }}65534{{ end }}
        fsGroup: {{ if eq $component "grafana" }}472{{ else if eq $component "loki" }}10001{{ else }}65534{{ end }}
        fsGroupChangePolicy: OnRootMismatch
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: {{ $component }}
          image: {{ index $.Values.images $component }}
          securityContext:
            {{- include "obs.security" $ | nindent 12 }}
          resources:
            {{- toYaml $settings.resources | nindent 12 }}
          {{- if eq $component "loki" }}
          args: [-config.file=/config/loki.yaml, -target=all]
          ports: [{name: http, containerPort: 3100}]
          readinessProbe: {httpGet: {path: /ready, port: http}, initialDelaySeconds: 10}
          startupProbe: {httpGet: {path: /ready, port: http}, periodSeconds: 5, failureThreshold: 60}
          {{- else if eq $component "prometheus" }}
          args:
            - --config.file=/config/prometheus.yaml
            - --storage.tsdb.path=/data
            - --storage.tsdb.retention.time={{ $.Values.prometheus.retention }}
            - --storage.tsdb.retention.size={{ $.Values.prometheus.retentionSize }}
          ports: [{name: metrics, containerPort: 9090}]
          readinessProbe: {httpGet: {path: /-/ready, port: metrics}}
          startupProbe: {httpGet: {path: /-/ready, port: metrics}, periodSeconds: 5, failureThreshold: 60}
          {{- else }}
          env:
            - name: GF_SECURITY_ADMIN_PASSWORD__FILE
              value: /etc/grafana/admin/password
            - {name: GF_SECURITY_ADMIN_USER, value: admin}
          ports: [{name: http, containerPort: 3000}]
          readinessProbe: {httpGet: {path: /api/health, port: http}}
          startupProbe: {httpGet: {path: /api/health, port: http}, periodSeconds: 5, failureThreshold: 60}
          {{- end }}
          volumeMounts:
            - {name: data, mountPath: {{ if eq $component "grafana" }}/var/lib/grafana{{ else }}/data{{ end }}}
            - {name: tmp, mountPath: /tmp}
            {{- if eq $component "grafana" }}
            - {name: config, mountPath: /etc/grafana/grafana.ini, subPath: grafana.ini, readOnly: true}
            - {name: config, mountPath: /etc/grafana/provisioning/datasources/native.yaml, subPath: datasources.yaml, readOnly: true}
            - {name: config, mountPath: /etc/grafana/provisioning/dashboards/native.yaml, subPath: dashboards.yaml, readOnly: true}
            - {name: config, mountPath: /etc/grafana/dashboards/overview.json, subPath: overview.json, readOnly: true}
            - {name: admin, mountPath: /etc/grafana/admin, readOnly: true}
            {{- if $.Values.grafana.oidc.enabled }}
            - {name: oidc, mountPath: /etc/grafana/oidc, readOnly: true}
            {{- end }}
            {{- else }}
            - {name: config, mountPath: /config, readOnly: true}
            {{- end }}
      volumes:
        - name: data
          persistentVolumeClaim: {claimName: {{ $.Release.Name }}-{{ $component }}}
        - name: tmp
          emptyDir: {sizeLimit: 64Mi}
        - name: config
          configMap: {name: {{ $.Release.Name }}-{{ $component }}}
        {{- if eq $component "grafana" }}
        - name: admin
          secret: {secretName: {{ $.Values.grafana.adminSecret }}}
        {{- if $.Values.grafana.oidc.enabled }}
        - name: oidc
          secret: {secretName: {{ required "OIDC secret required" $.Values.grafana.oidc.secret }}}
        {{- end }}
        {{- end }}
{{- end }}
