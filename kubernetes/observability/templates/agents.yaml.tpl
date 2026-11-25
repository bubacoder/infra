{{- range $component, $settings := dict "fluent-bit" .Values.collector "node-exporter" .Values.nodeExporter }}
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
spec:
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
      nodeSelector: {kubernetes.io/os: linux}
      tolerations:
        - {key: node-role.kubernetes.io/control-plane, operator: Exists, effect: NoSchedule}
        - {key: node-role.kubernetes.io/master, operator: Exists, effect: NoSchedule}
      automountServiceAccountToken: {{ eq $component "fluent-bit" }}
      {{- if eq $component "fluent-bit" }}
      serviceAccountName: {{ $.Release.Name }}-fluent-bit
      {{- end }}
      securityContext:
        runAsUser: {{ if eq $component "fluent-bit" }}0{{ else }}65534{{ end }}
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: {{ $component }}
          image: {{ if eq $component "fluent-bit" }}{{ $.Values.images.fluentBit }}{{ else }}{{ $.Values.images.nodeExporter }}{{ end }}
          securityContext:
            {{- include "obs.security" $ | nindent 12 }}
          resources:
            {{- toYaml $settings.resources | nindent 12 }}
          {{- if eq $component "fluent-bit" }}
          args: [-c, /config/fluent-bit.conf]
          ports: [{name: metrics, containerPort: 2020}]
          readinessProbe: {httpGet: {path: /api/v1/health, port: metrics}}
          volumeMounts:
            - {name: config, mountPath: /config, readOnly: true}
            - {name: containers, mountPath: /var/log/containers, readOnly: true}
            - {name: pods, mountPath: /var/log/pods, readOnly: true}
            - {name: state, mountPath: /state}
          {{- else }}
          args: [--path.procfs=/host/proc, --path.sysfs=/host/sys, --path.rootfs=/host/root]
          ports: [{name: metrics, containerPort: 9100}]
          readinessProbe: {httpGet: {path: /metrics, port: metrics}}
          volumeMounts:
            - {name: proc, mountPath: /host/proc, readOnly: true}
            - {name: sys, mountPath: /host/sys, readOnly: true}
            - {name: root, mountPath: /host/root, readOnly: true, mountPropagation: HostToContainer}
          {{- end }}
      volumes:
        {{- if eq $component "fluent-bit" }}
        - name: config
          configMap: {name: {{ $.Release.Name }}-fluent-bit}
        - name: containers
          hostPath: {path: /var/log/containers, type: Directory}
        - name: pods
          hostPath: {path: /var/log/pods, type: Directory}
        - name: state
          hostPath: {path: {{ $.Values.collector.statePath }}, type: DirectoryOrCreate}
        {{- else }}
        - name: proc
          hostPath: {path: /proc, type: Directory}
        - name: sys
          hostPath: {path: /sys, type: Directory}
        - name: root
          hostPath: {path: /, type: Directory}
        {{- end }}
{{- end }}
