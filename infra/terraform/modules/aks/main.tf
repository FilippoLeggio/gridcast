# AKS cluster on the Free control plane tier: you pay only for the nodes.

variable "name" {
  description = "Cluster name, also used as DNS prefix."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group of the cluster."
  type        = string
}

variable "subnet_id" {
  description = "Subnet for the nodes."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version (minor version, e.g. 1.34)."
  type        = string
}

variable "node_vm_size" {
  description = "VM size of the nodes."
  type        = string
  default     = "Standard_B2s_v2"
}

variable "node_count" {
  description = "Number of nodes."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.name
  kubernetes_version  = var.kubernetes_version
  sku_tier            = "Free"

  # Lets pods authenticate to Azure services without stored credentials (workload identity).
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  default_node_pool {
    name           = "system"
    vm_size        = var.node_vm_size
    node_count     = var.node_count
    vnet_subnet_id = var.subnet_id
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    # Overlay: pods get addresses from a private range outside the virtual network.
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    # Cilium enforces the NetworkPolicies of the chart, as kube-router does on k3s.
    network_data_plane = "cilium"
    network_policy     = "cilium"
    load_balancer_sku  = "standard"
  }

  tags = var.tags
}

output "kube_config" {
  description = "Admin kubeconfig attributes, used to configure the Kubernetes providers."
  value       = azurerm_kubernetes_cluster.this.kube_config[0]
  sensitive   = true
}

output "oidc_issuer_url" {
  description = "OIDC issuer of the cluster, for workload identity."
  value       = azurerm_kubernetes_cluster.this.oidc_issuer_url
}
