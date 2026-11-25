apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-query
  labels:
    {{- include "obs.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
      app.kubernetes.io/component: query
  template:
    metadata:
      labels:
        {{- include "obs.labels" . | nindent 8 }}
        app.kubernetes.io/component: query
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configs.yaml.tpl") . | sha256sum }}
    spec:
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 101
        runAsGroup: 101
        fsGroup: 101
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: query
          image: {{ .Values.images.query }}
          command: [nginx]
          args: [-g, "daemon off;"]
          ports:
            - {name: http, containerPort: 8080}
            - {name: metrics, containerPort: 8081}
          readinessProbe: {httpGet: {path: /ready, port: http}}
          securityContext:
            {{- include "obs.security" . | nindent 12 }}
          resources:
            {{- toYaml .Values.query.resources | nindent 12 }}
          volumeMounts:
            - {name: config, mountPath: /etc/nginx/nginx.conf, subPath: nginx.conf, readOnly: true}
            - {name: tmp, mountPath: /tmp}
      volumes:
        - name: config
          configMap: {name: {{ .Release.Name }}-query}
        - name: tmp
          emptyDir: {sizeLimit: 32Mi}
