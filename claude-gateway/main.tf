terraform {
  required_version = "= 1.12.3"
  # Intentionally separate local state; never initialize against the core backend.
  backend "local" {
    path = "claude-gateway.tfstate"
  }
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.56.0"
    }
  }
}

provider "azurerm" {
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  features {}
}

provider "azurerm" {
  alias                           = "foundry"
  subscription_id                 = split("/", var.foundry_resource_id)[2]
  resource_provider_registrations = "none"
  features {}
}

resource "azurerm_resource_group" "gateway" {
  name     = var.resource_group_name
  location = var.location
  tags     = { purpose = "claude-gateway-poc" }
}

resource "azurerm_network_security_group" "gateway" {
  name                = "claude-gateway-poc"
  location            = azurerm_resource_group.gateway.location
  resource_group_name = azurerm_resource_group.gateway.name

  security_rule {
    name                       = "private-client-tls"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8443"
    source_address_prefixes    = var.client_cidrs
    destination_address_prefix = "*"
  }
  security_rule {
    name                       = "private-management-ssh"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.management_cidrs
    destination_address_prefix = "*"
  }
  security_rule {
    name                       = "deny-other-inbound"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "gateway" {
  name                = "claude-gateway-poc"
  location            = azurerm_resource_group.gateway.location
  resource_group_name = azurerm_resource_group.gateway.name
  ip_configuration {
    name                          = "private"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface_security_group_association" "gateway" {
  network_interface_id      = azurerm_network_interface.gateway.id
  network_security_group_id = azurerm_network_security_group.gateway.id
}

resource "azurerm_linux_virtual_machine" "gateway" {
  name                            = "claude-gateway-poc"
  resource_group_name             = azurerm_resource_group.gateway.name
  location                        = azurerm_resource_group.gateway.location
  size                            = "Standard_B2s"
  admin_username                  = "gatewayadmin"
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.gateway.id]
  secure_boot_enabled             = true
  vtpm_enabled                    = true
  identity {
    type = "SystemAssigned"
  }
  admin_ssh_key {
    username   = "gatewayadmin"
    public_key = var.ssh_public_key
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 64
  }
  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
  depends_on = [azurerm_network_interface_security_group_association.gateway]
}

resource "azurerm_role_assignment" "foundry" {
  provider                         = azurerm.foundry
  scope                            = var.foundry_resource_id
  role_definition_id               = "/subscriptions/${split("/", var.foundry_resource_id)[2]}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
  principal_id                     = azurerm_linux_virtual_machine.gateway.identity[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

output "private_ip" {
  value = azurerm_network_interface.gateway.private_ip_address
}
output "managed_identity_principal_id" {
  value = azurerm_linux_virtual_machine.gateway.identity[0].principal_id
}
output "foundry_resource_name" {
  value = split("/", var.foundry_resource_id)[8]
}
