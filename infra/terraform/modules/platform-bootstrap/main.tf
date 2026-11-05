# Bootstrap a Kubernetes cluster up to the point where Argo CD manages everything else:
# Sealed Secrets keys first, then Argo CD, then the root Application from the GitOps repository.

data "http" "argocd_values" {
  url = "${var.gitops_raw_url}/bootstrap/argocd-values.yaml"
}

data "http" "root_application" {
  url = "${var.gitops_raw_url}/bootstrap/${var.environment}.yaml"
}

locals {
  sealing_keys = var.sealed_secrets_keys_yaml == "" ? [] : yamldecode(var.sealed_secrets_keys_yaml).items

  # Key contents stay sensitive; only their names are used to drive for_each.
  sealing_keys_by_name = { for key in local.sealing_keys : key.metadata.name => key }
  sealing_key_names    = nonsensitive(toset([for key in local.sealing_keys : key.metadata.name]))
}

# Restored before the controller starts, so the SealedSecrets in Git stay decryptable.
resource "kubernetes_secret_v1" "sealing_key" {
  for_each = local.sealing_key_names

  metadata {
    name      = each.key
    namespace = "kube-system"
    labels    = local.sealing_keys_by_name[each.key].metadata.labels
  }
  type = local.sealing_keys_by_name[each.key].type
  # Values in the backup are already base64-encoded.
  binary_data = local.sealing_keys_by_name[each.key].data
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  values           = [data.http.argocd_values.response_body]
  wait             = true

  depends_on = [kubernetes_secret_v1.sealing_key]
}

# From here on, Argo CD installs the platform and the applications from Git.
resource "kubectl_manifest" "root_application" {
  yaml_body = data.http.root_application.response_body

  depends_on = [helm_release.argocd]
}
