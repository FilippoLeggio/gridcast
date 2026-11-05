# Production on AKS: network and cluster. Bootstrap, budget and backups come in the next step.

terraform {
  required_version = ">= 1.9"
  # Remote state in the shared storage account; settings in backend.hcl.
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

locals {
  name = "gridcast-prod"
  tags = {
    project     = "gridcast"
    environment = "prod"
    owner       = "filippo"
  }
}

resource "azurerm_resource_group" "prod" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "network" {
  source = "../../modules/azure-network"

  name                = local.name
  location            = azurerm_resource_group.prod.location
  resource_group_name = azurerm_resource_group.prod.name
  tags                = local.tags
}

module "aks" {
  source = "../../modules/aks"

  name                = "aks-${local.name}"
  location            = azurerm_resource_group.prod.location
  resource_group_name = azurerm_resource_group.prod.name
  subnet_id           = module.network.aks_subnet_id
  kubernetes_version  = "1.37.2"
  tags                = local.tags
}
