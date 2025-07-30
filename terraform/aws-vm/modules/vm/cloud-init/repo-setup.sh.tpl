#!/bin/bash
set -e

function setup() {
    # Create repo directories
    mkdir -p ~/repos
    
    # Get Git credentials from Secrets Manager
    echo "Getting Git credentials from Secrets Manager..."
    GIT_CREDENTIALS=$(aws secretsmanager get-secret-value --region ${REGION} --secret-id ${GIT_CREDENTIALS_SECRET_ID} --query 'SecretString' --output text | jq -r '."git-credentials"')
    
    if [ -z "$GIT_CREDENTIALS" ]; then
        echo "Failed to retrieve Git credentials!"
        exit 1
    fi
    
    # Configure Git
    echo "Configuring Git..."
    mkdir -p ~/.git
    echo "$GIT_CREDENTIALS" > ~/.git-credentials
    chmod 600 ~/.git-credentials
    git config --global credential.helper 'store --file ~/.git-credentials'
    git config --global credential.helper cache
    
    # Clone repository
    echo "Cloning repository..."
    cd ~/repos
    git clone ${REPO_URL} ${REPO_DIR}
    
    echo "Repository setup completed successfully!"
}

# Main
if [[ $1 == "setup" ]]; then
    setup
else
    echo "Usage: $0 setup"
    exit 1
fi