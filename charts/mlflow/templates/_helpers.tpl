{{- define "mlflow.labels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: mlflow
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{/* S3 credentials from the existing secret, in the variables every S3 client reads. */}}
{{- define "mlflow.s3Env" -}}
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.s3.credentialsSecret }}
      key: access-key
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.s3.credentialsSecret }}
      key: secret-key
- name: AWS_DEFAULT_REGION
  value: us-east-1
{{- end }}
