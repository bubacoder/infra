### VM

locals {
  #vm_name = "${var.prefix}-vm"
  vm_name = "nest"
}

# Generate random text for a unique storage account name
resource "random_id" "random_id" {
  keepers = {
    # Generate a new ID only when a new resource group is defined
    resource_group = var.resourcegroup
  }

  byte_length = 8
}

# Create storage account for boot diagnostics
resource "azurerm_storage_account" "nest_storage_account" {
  name                     = "diag${random_id.random_id.hex}"
  location                 = var.location
  resource_group_name      = var.resourcegroup

  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

# Create public IPs
resource "azurerm_public_ip" "nest" {
  name                = "${local.vm_name}_PublicIP"
  location            = var.location
  resource_group_name = var.resourcegroup

  domain_name_label   = "buba-${local.vm_name}"
  allocation_method   = "Dynamic"
}

# Create Network Security Group and rule
resource "azurerm_network_security_group" "nest_nsg" {
  name                = "${local.vm_name}_NetworkSecurityGroup"
  location            = var.location
  resource_group_name = var.resourcegroup

  # Admin

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
    name                       = "Portainer web UI"
    priority                   = 1010
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "9000"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Jellyfin web UI"
    priority                   = 1020
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8096"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Syncthing web UI"
    priority                   = 1030
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8384"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Transmission web UI"
    priority                   = 1040
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "9091"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Filebrowser web UI"
    priority                   = 1050
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8080"
    source_address_prefix      = var.admin_source_address
    destination_address_prefix = "*"
  }

  # Public

  security_rule {
    name                       = "Transmission peer TCP port"
    priority                   = 2000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "51413"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Transmission peer UDP port"
    priority                   = 2010
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "51413"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Syncthing peer TCP port"
    priority                   = 2020
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Syncthing peer UDP port - 22000"
    priority                   = 2030
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "22000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Syncthing peer UDP port - 21027"
    priority                   = 2040
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "21027"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Create network interface
resource "azurerm_network_interface" "nest_nic" {
  name                = "${local.vm_name}_NIC"
  location            = var.location
  resource_group_name = var.resourcegroup

  ip_configuration {
    name                          = "${local.vm_name}_NIC_configuration"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.nest.id
  }
}

# Connect the security group to the network interface
resource "azurerm_network_interface_security_group_association" "nest" {
  network_interface_id      = azurerm_network_interface.nest_nic.id
  network_security_group_id = azurerm_network_security_group.nest_nsg.id
}

# Create (and display) an SSH key
resource "tls_private_key" "nest_ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Create virtual machine
resource "azurerm_linux_virtual_machine" "nest" {
  name                  = "${local.vm_name}"
  location              = var.location
  resource_group_name   = var.resourcegroup

  network_interface_ids = [azurerm_network_interface.nest_nic.id]
  size                  = var.vm_size

  os_disk {
    name                 = "${local.vm_name}_OsDisk"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = var.vm_ubuntu_server_offer
    sku       = var.vm_ubuntu_server_sku
    version   = "latest"
  }

  computer_name                   = "${local.vm_name}"
  admin_username                  = "azureuser"
  disable_password_authentication = true

  custom_data = data.cloudinit_config.nest_config.rendered

  admin_ssh_key {
    username   = "azureuser"
    public_key = tls_private_key.nest_ssh.public_key_openssh
  }

  boot_diagnostics {
    storage_account_uri = azurerm_storage_account.nest_storage_account.primary_blob_endpoint
  }
}

resource "azurerm_virtual_machine_data_disk_attachment" "nest_data" {
  managed_disk_id    = var.data_disk_id
  virtual_machine_id = azurerm_linux_virtual_machine.nest.id
  lun                = "10"
  caching            = "ReadWrite"
}
