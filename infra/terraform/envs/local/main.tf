# Local k3d cluster: bootstrap only, the cluster itself is created by k3d (task dev-up).

terraform {
  required_version = ">= 1.9"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.38"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.1"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

locals {
  kubeconfig = pathexpand("~/.kube/config")
  context    = "k3d-gridcast-dev"
}

provider "kubernetes" {
  config_path    = local.kubeconfig
  config_context = local.context
}

provider "helm" {
  kubernetes = {
    config_path    = local.kubeconfig
    config_context = local.context
  }
}

provider "kubectl" {
  config_path      = local.kubeconfig
  config_context   = local.context
  load_config_file = true
}

variable "sealed_secrets_keys_yaml" {
  description = "Backed-up Sealed Secrets keys, passed through TF_VAR_sealed_secrets_keys_yaml."
  type        = string
  default     = ""
  sensitive   = true
}

module "platform" {
  source = "../../modules/platform-bootstrap"

  environment              = "dev"
  argocd_chart_version     = "10.13.1"
  sealed_secrets_keys_yaml = var.sealed_secrets_keys_yaml
}
