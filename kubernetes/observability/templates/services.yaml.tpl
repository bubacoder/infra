{{- range $component, $port := dict "loki" 3100 "prometheus" 9090 "grafana" 3000 "query" 8080 }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/instance: {{ $.Release.Name }}
    app.kubernetes.io/component: {{ $component }}
  ports:
    - {name: http, port: {{ $port }}, targetPort: {{ $port }}}
{{- end }}
