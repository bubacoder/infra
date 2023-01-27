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

  location      = var.location
  resourcegroup = var.resourcegroup
  subnet_id     = module.base.subnet_id
  data_disk_id  = module.storage.data_disk_id

  depends_on = [
    module.base,
    module.storage
  ]
}

