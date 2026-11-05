output "argocd_namespace" {
  description = "Namespace where Argo CD runs."
  value       = helm_release.argocd.namespace
}
