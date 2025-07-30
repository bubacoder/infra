module "base" {
  source = "./modules/base"

  region      = var.region
  environment = var.environment
}

module "storage" {
  source = "./modules/storage"

  region      = var.region
  environment = var.environment

  disk_size_gb = var.storage_disk_size_gb

  depends_on = [
    module.base
  ]
}

module "secrets" {
  source = "./modules/secrets"

  region      = var.region
  environment = var.environment

  secrets_manager_name = local.secrets_manager_name
  git_credentials     = var.git_credentials

  depends_on = [
    module.base
  ]
}

module "vm" {
  source = "./modules/vm"

  region      = var.region
  environment = var.environment

  subnet_id    = module.base.subnet_id
  ebs_volume_id = module.storage.ebs_volume_id

  vm_name                 = var.vm_name
  vm_domain_name          = var.vm_domain_name
  admin_user              = var.admin_user
  instance_type           = var.instance_type
  ami_id                  = var.ami_id
  admin_source_address    = var.admin_source_address
  secrets_manager_arn     = module.secrets.secrets_manager_arn
  git_credentials_secret_id = module.secrets.git_credentials_secret_id
  repo_url                = var.repo_url
  repo_directory          = var.repo_directory
}