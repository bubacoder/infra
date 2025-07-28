output "key_vault_id" {
  description = "The ID of the Key Vault"
  value       = azurerm_key_vault.kv.id
}

output "key_vault_uri" {
  description = "The URI of the Key Vault"
  value       = azurerm_key_vault.kv.vault_uri
}

output "git_credentials_secret_id" {
  description = "The ID of the git credentials secret"
  value       = azurerm_key_vault_secret.git_credentials.id
}
