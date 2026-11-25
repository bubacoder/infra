{{- range $component := list "prometheus" "fluent-bit" "reader" }}
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
automountServiceAccountToken: false
{{- end }}
{{- range $component := list "prometheus" "fluent-bit" }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ $.Release.Namespace }}-{{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
rules:
  - apiGroups: [""]
    resources: [pods, namespaces{{ if eq $component "prometheus" }}, nodes{{ end }}]
    verbs: [get, list, watch]
  {{- if eq $component "prometheus" }}
  - apiGroups: [""]
    resources: [nodes/metrics]
    verbs: [get]
  {{- end }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ $.Release.Namespace }}-{{ $.Release.Name }}-{{ $component }}
  labels:
    {{- include "obs.labels" $ | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ $.Release.Namespace }}-{{ $.Release.Name }}-{{ $component }}
subjects:
  - kind: ServiceAccount
    name: {{ $.Release.Name }}-{{ $component }}
    namespace: {{ $.Release.Namespace }}
{{- end }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ .Release.Name }}-reader
rules:
  - apiGroups: [""]
    resources: [services/proxy]
    resourceNames: ["http:{{ .Release.Name }}-query:8080"]
    verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ .Release.Name }}-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ .Release.Name }}-reader
subjects:
  - kind: ServiceAccount
    name: {{ .Release.Name }}-reader
    namespace: {{ .Release.Namespace }}
