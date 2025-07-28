module "base" {
  source = "./modules/base"

  location      = var.location
  resourcegroup = var.resourcegroup
}

module "storage" {
  source = "./modules/storage"

  location      = var.location
  resourcegroup = var.resourcegroup

  disk_size_gb = var.storage_disk_size_gb

  depends_on = [
    module.base
  ]
}

module "vm" {
  source = "./modules/vm"

  location      = var.location
  resourcegroup = var.resourcegroup

  subnet_id    = module.base.subnet_id
  data_disk_id = module.storage.data_disk_id

  vm_name                = var.vm_name
  vm_domain_name_label   = var.vm_domain_name_label
  admin_user             = var.admin_user
  vm_size                = var.vm_size
  vm_ubuntu_server_offer = var.vm_ubuntu_server_offer
  vm_ubuntu_server_sku   = var.vm_ubuntu_server_sku
  admin_source_address   = var.admin_source_address
  git_credentials        = var.git_credentials
  repo_url               = var.repo_url
  repo_directory         = var.repo_directory

  depends_on = [
    module.base,
    module.storage
  ]
}
