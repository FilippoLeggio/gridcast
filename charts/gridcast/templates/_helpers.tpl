{{/* Standard labels, applied to every resource of the release. */}}
{{- define "gridcast.labels" -}}
app.kubernetes.io/name: gridcast
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{/* Full image reference for a component. Fails the install if no tag is given. */}}
{{- define "gridcast.image" -}}
{{ .root.Values.image.registry }}/gridcast-{{ .component }}:{{ required "image.tag is required" .root.Values.image.tag }}
{{- end }}

{{/* Secret created by CloudNativePG with the application credentials and URI. */}}
{{- define "gridcast.dbSecret" -}}
{{ .Release.Name }}-db-app
{{- end }}
