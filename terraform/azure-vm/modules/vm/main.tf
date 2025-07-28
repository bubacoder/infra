# Generate random text for a unique storage account name
resource "random_id" "random_id" {
  keepers = {
    # Generate a new ID only when a new resource group is defined
    resource_group = var.resourcegroup
  }

  byte_length = 8
}

# Create storage account for boot diagnostics
resource "azurerm_storage_account" "vm_storage_account" {
  name                = "diag${random_id.random_id.hex}"
  location            = var.location
  resource_group_name = var.resourcegroup

  account_tier               = "Standard"
  account_replication_type   = "LRS"
  min_tls_version            = "TLS1_2"
  https_traffic_only_enabled = true
}

# Create public IPs
resource "azurerm_public_ip" "vm" {
  name                = "${var.vm_name}_PublicIP"
  location            = var.location
  resource_group_name = var.resourcegroup

  domain_name_label = var.vm_domain_name_label
  allocation_method = "Static"
  sku               = "Standard"
}

# Create Network Security Group and rule
resource "azurerm_network_security_group" "vm_nsg" {
  name                = "${var.vm_name}_NetworkSecurityGroup"
  location            = var.location
  resource_group_name = var.resourcegroup

  security_rule {
    name                       = "SSH"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "HTTPS"
    priority                   = 1010
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }
}

# Create network interface
resource "azurerm_network_interface" "vm_nic" {
  name                = "${var.vm_name}_NIC"
  location            = var.location
  resource_group_name = var.resourcegroup

  ip_configuration {
    name                          = "${var.vm_name}_NIC_configuration"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm.id
  }
}

# Connect the security group to the network interface
resource "azurerm_network_interface_security_group_association" "vm" {
  network_interface_id      = azurerm_network_interface.vm_nic.id
  network_security_group_id = azurerm_network_security_group.vm_nsg.id
}

# Create an SSH key
# Note: ssh-ed25519 SSH key is not supported. Only RSA SSH keys are supported by Azure
resource "tls_private_key" "vm_ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Create virtual machine
resource "azurerm_linux_virtual_machine" "vm" {
  name                = var.vm_name
  location            = var.location
  resource_group_name = var.resourcegroup

  network_interface_ids = [azurerm_network_interface.vm_nic.id]
  size                  = var.vm_size

  os_disk {
    name                 = "${var.vm_name}_OsDisk"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = var.vm_ubuntu_server_offer
    sku       = var.vm_ubuntu_server_sku
    version   = "latest"
  }

  computer_name                   = var.vm_name
  admin_username                  = var.admin_user
  disable_password_authentication = true

  custom_data = data.cloudinit_config.vm_config.rendered

  admin_ssh_key {
    username   = var.admin_user
    public_key = tls_private_key.vm_ssh.public_key_openssh
  }

  boot_diagnostics {
    storage_account_uri = azurerm_storage_account.vm_storage_account.primary_blob_endpoint
  }

  # Add system-assigned managed identity to the VM
  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_virtual_machine_data_disk_attachment" "vm_data" {
  managed_disk_id    = var.data_disk_id
  virtual_machine_id = azurerm_linux_virtual_machine.vm.id
  lun                = "10"
  caching            = "ReadWrite"
}

data "azurerm_client_config" "current" {}

# Enable Key Vault access to the VM's managed identity
resource "azurerm_key_vault_access_policy" "vm" {
  key_vault_id = var.key_vault_id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_virtual_machine.vm.identity[0].principal_id

  secret_permissions = [
    "Get",
    "List"
  ]
}
