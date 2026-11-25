apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Release.Name }}-default-deny
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Release.Name }}-dns
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: kube-system}
          podSelector:
            matchLabels: {k8s-app: kube-dns}
      ports:
        - {protocol: UDP, port: 53}
        - {protocol: TCP, port: 53}
{{- range $component, $sources := dict "loki" (list "fluent-bit" "query") "prometheus" (list "grafana" "prometheus") "query" (list "grafana") "fluent-bit" (list "prometheus") "node-exporter" (list "prometheus") }}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ $.Release.Name }}-to-{{ $component }}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ $.Release.Name }}
      app.kubernetes.io/component: {{ $component }}
  policyTypes: [Ingress]
  ingress:
    - from:
        {{- range $source := $sources }}
        - podSelector:
            matchLabels:
              app.kubernetes.io/instance: {{ $.Release.Name }}
              app.kubernetes.io/component: {{ $source }}
        {{- end }}
      ports:
        - protocol: TCP
          port: {{ if eq $component "loki" }}3100{{ else if eq $component "prometheus" }}9090{{ else if eq $component "query" }}8080{{ else if eq $component "fluent-bit" }}2020{{ else }}9100{{ end }}
{{- end }}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Release.Name }}-query-metrics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
      app.kubernetes.io/component: query
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels: {app.kubernetes.io/component: prometheus}
      ports: [{protocol: TCP, port: 8081}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ .Release.Name }}-internal-egress
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/instance: {{ .Release.Name }}
      ports:
        - {protocol: TCP, port: 3100}
        - {protocol: TCP, port: 9090}
        - {protocol: TCP, port: 8080}
        - {protocol: TCP, port: 8081}
        - {protocol: TCP, port: 2020}
        - {protocol: TCP, port: 9100}
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: {{ .Release.Name }}-api-access
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
    matchExpressions:
      - key: app.kubernetes.io/component
        operator: In
        values: [prometheus, fluent-bit]
  egress:
    - toEntities: [kube-apiserver]
      toPorts:
        - ports:
            - {port: "443", protocol: TCP}
            - {port: "6443", protocol: TCP}
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: {{ .Release.Name }}-kubelet-access
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
      app.kubernetes.io/component: prometheus
  egress:
    - toEntities: [host, remote-node]
      toPorts:
        - ports:
            - {port: "10250", protocol: TCP}
{{- if .Values.grafana.oidc.enabled }}
---
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: {{ .Release.Name }}-oidc
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
      app.kubernetes.io/component: grafana
  egress:
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
      toPorts:
        - ports:
            - {port: "53", protocol: ANY}
          rules:
            dns:
              - matchName: {{ .Values.grafana.oidc.host | quote }}
    - toFQDNs:
        - matchName: {{ .Values.grafana.oidc.host | quote }}
      toPorts:
        - ports:
            - {port: "443", protocol: TCP}
{{- end }}
