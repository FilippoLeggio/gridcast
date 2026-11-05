# Remote state location: storage account created by envs/shared.
resource_group_name  = "rg-gridcast-shared"
storage_account_name = "<from-shared-output>"
container_name       = "tfstate"
key                  = "azure-prod.tfstate"
