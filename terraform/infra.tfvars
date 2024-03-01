# --- Common ---

location      = "westeurope"
resourcegroup = "HomeInfra"

# --- Storage ---

storage_disk_size_gb = 10

# --- Virtual Machine ---

vm_name              = "nest"
vm_domain_name_label = "buba-nest"
admin_user           = "azureuser"
vm_size              = "Standard_D2s_v5" # 2 CPU, 8 GB RAM
#vm_size              = "Standard_F8s_v2" # 8 CPU, 16 GB RAM
