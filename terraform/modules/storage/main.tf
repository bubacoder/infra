### Permanent storage

# Configure:
# cfdisk /dev/sdc
# mkfs.ext4 /dev/sdc1
resource "azurerm_managed_disk" "data" {
  name                = "nest_DataDisk"
  location            = var.location
  resource_group_name = var.resourcegroup

  storage_account_type = "Standard_LRS"
  create_option        = "Empty"
  disk_size_gb         = 10

  lifecycle {
    prevent_destroy = true
  }
}
