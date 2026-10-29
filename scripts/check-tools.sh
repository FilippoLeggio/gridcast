#!/usr/bin/env bash
# Stampa la versione di ogni strumento richiesto da GridCast.
# Exit code 0 se c'è tutto, 1 se manca qualcosa.
set -uo pipefail

tools=(
  "docker|docker --version"
  "compose|docker compose version --short"
  "buildx|docker buildx version"
  "kubectl|kubectl version --client"
  "k3d|k3d version"
  "helm|helm version --short"
  "kubeseal|kubeseal --version"
  "argocd|argocd version --client --short"
  "kubeconform|kubeconform -v"
  "terraform|terraform version"
  "tflint|tflint --version"
  "ansible|ansible --version"
  "az|az version --query '\"azure-cli\"' -o tsv"
  "uv|uv --version"
  "pre-commit|pre-commit --version"
  "task|task --version"
  "gh|gh --version"
  "yq|yq --version"
  "jq|jq --version"
  "k6|k6 version"
  "hadolint|hadolint --version"
  "trivy|trivy --version"
  "gitleaks|gitleaks version"
)

missing=0
for entry in "${tools[@]}"; do
  name="${entry%%|*}"
  cmd="${entry#*|}"
  if out=$(eval "$cmd" 2>/dev/null | head -n1) && [[ -n "$out" ]]; then
    printf "%-12s %s\n" "$name" "$out"
  else
    printf "%-12s MANCANTE\n" "$name"
    missing=$((missing + 1))
  fi
done

echo
if [[ $missing -eq 0 ]]; then
  echo "Tutti gli strumenti sono installati."
else
  echo "Strumenti mancanti: $missing"
fi
[[ $missing -eq 0 ]]