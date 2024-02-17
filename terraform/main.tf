module "base" {
  source = "./modules/base"

  location      = var.location
  resourcegroup = var.resourcegroup
}

module "storage" {
  source = "./modules/storage"

  location      = var.location
  resourcegroup = var.resourcegroup

  depends_on = [
    module.base
  ]
}

module "nest" {
  source = "./modules/nest"

  location             = var.location
  resourcegroup        = var.resourcegroup
  admin_source_address = var.admin_source_address
  subnet_id            = module.base.subnet_id
  data_disk_id         = module.storage.data_disk_id
  admin_user           = var.admin_user
  git_credentials      = var.git_credentials
  repo_url             = var.repo_url
  repo_directory       = var.repo_directory

  depends_on = [
    module.base,
    module.storage
  ]
}
