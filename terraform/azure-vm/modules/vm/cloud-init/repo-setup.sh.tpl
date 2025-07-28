#!/usr/bin/env bash
set -euo pipefail

# HACK Do not let cloud-init start this script automatically with root user.
if [ "$1" != "setup" ]; then
  echo "First parameter must be 'setup'. Exiting."
  exit 1
fi

echo "Setting up git credentials for $(whoami)..."
git config --global credential.helper store
touch ~/.git-credentials
chmod 600 ~/.git-credentials

# Install Azure CLI if not already installed
if ! command -v az &> /dev/null; then
    echo "Installing Azure CLI..."
    curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/microsoft.gpg > /dev/null
    echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/azure-cli.list
    sudo apt update && sudo apt install -y azure-cli
fi

# Login using the VM's managed identity
echo "Logging in to Azure using managed identity..."
az login --identity --allow-no-subscriptions

# Fetch git credentials from Key Vault
echo "Fetching git credentials from Azure Key Vault..."
GIT_CREDS=$(az keyvault secret show --id "${GIT_CREDENTIALS_SECRET_ID}" --query "value" -o tsv)

# Validate that credentials were retrieved
if [ -z "$GIT_CREDS" ]; then
    echo "Error: Failed to retrieve git credentials from Key Vault"
    exit 1
fi

# Validate credentials format before writing
if ! echo "$GIT_CREDS" | grep -q "://"; then
    echo "Error: Invalid git credentials format"
    exit 1
fi

# Save credentials
echo "$GIT_CREDS" > ~/.git-credentials

# Clone the repository
mkdir -p ~/repos && cd ~/repos || exit
git clone "${REPO_URL}" "${REPO_DIR}"
cd "${REPO_DIR}" || exit
ls -la
