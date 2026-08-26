terraform {
  required_version = "= 1.12.3"

  backend "azurerm" {}

  required_providers {
    azapi = {
      source  = "Azure/azapi"
      version = "= 2.12.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.56.0"
    }
  }
}

provider "azurerm" {
  resource_provider_registrations = "none"
  features {}
}

provider "azurerm" {
  alias                           = "foundry"
  subscription_id                 = var.foundry_subscription_id
  resource_provider_registrations = "none"
  features {}
}

# This alias reads an optional existing Application Insights component, which
# may be in a different subscription from the APIM resource group.
provider "azurerm" {
  alias                           = "telemetry"
  subscription_id                 = var.existing_app_insights_resource_id == "" ? null : split("/", var.existing_app_insights_resource_id)[2]
  resource_provider_registrations = "none"
  features {}
}

provider "azapi" {}
