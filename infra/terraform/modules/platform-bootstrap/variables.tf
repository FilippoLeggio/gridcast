variable "environment" {
  description = "Environment name: selects bootstrap/<environment>.yaml in the GitOps repository."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "gitops_raw_url" {
  description = "Raw content URL of the GitOps repository, main branch."
  type        = string
  default     = "https://raw.githubusercontent.com/FilippoLeggio/gridcast-gitops/main"
}

variable "argocd_chart_version" {
  description = "Version of the argo-cd Helm chart."
  type        = string
}

variable "sealed_secrets_keys_yaml" {
  description = "Backed-up Sealed Secrets keys (kubectl get secret -o yaml output). Empty on a brand new environment."
  type        = string
  default     = ""
  sensitive   = true
}
