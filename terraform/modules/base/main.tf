# Resource group
resource "azurerm_resource_group" "rg" {
  name     = var.resourcegroup
  location = var.location
}

# Create virtual network
resource "azurerm_virtual_network" "nest_network" {
  name                = "nest_Vnet"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name

  address_space = ["10.0.0.0/16"]
}

# Create subnet
resource "azurerm_subnet" "nest_subnet" {
  name                = "nest_Subnet"
  resource_group_name = azurerm_resource_group.rg.name

  virtual_network_name = azurerm_virtual_network.nest_network.name
  address_prefixes     = ["10.0.1.0/24"]
}
