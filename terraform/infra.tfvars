# --- Common ---

subscription_id = "00000000-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
location        = "westeurope"
resourcegroup   = "HomeInfra"

# --- Storage ---

storage_disk_size_gb = 100

# --- Virtual Machine ---

vm_name              = "nest"
vm_domain_name_label = "buba-nest"
admin_user           = "azureuser"
# Example sizes:
# - "Standard_D2s_v5" - 2 CPU, 8 GB RAM
# - "Standard_F8s_v2" - 8 CPU, 16 GB RAM
vm_size = "Standard_F8s_v2"
