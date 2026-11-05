# Shared foundation, applied once with local state: the storage that holds the remote state
# of every other Azure environment. Its own state holds no secrets: keep it safe, not secret.

terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
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
  tags = {
    project     = "gridcast"
    environment = "shared"
    owner       = "filippo"
  }
}

resource "azurerm_resource_group" "shared" {
  name     = "rg-gridcast-shared"
  location = var.location
  tags     = local.tags
}

# Storage account names are global across Azure: a random suffix avoids collisions.
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "stgridcasttf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.shared.name
  location                        = azurerm_resource_group.shared.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true
  lifecycle {
    prevent_destroy = true
  }

  blob_properties {
    # Recover a state overwritten or deleted by mistake.
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
  }

  tags = local.tags
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"
  lifecycle {
    prevent_destroy = true
  }
}

output "tfstate_storage_account" {
  description = "Storage account for remote state: copy it into envs/*/backend.hcl."
  value       = azurerm_storage_account.tfstate.name
}
