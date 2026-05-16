#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail

# HACK Do not let cloud-init start this script automatically with root user.
# shellcheck disable=SC2193 # $${1:-} is a Terraform escape that renders to bash default-expansion
if [ "$${1:-}" != "setup" ]; then
  echo "First parameter must be 'setup'. Exiting."
  exit 1
fi

echo "Setting up git credentials for $(whoami)..."
git config --global credential.helper store
touch ~/.git-credentials
chmod 600 ~/.git-credentials

# Install AWS CLI v2 if not already installed
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI v2..."
    ARCH=$(uname -m)
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$${ARCH}.zip" -o /tmp/awscliv2.zip
    cd /tmp && unzip -q awscliv2.zip && sudo ./aws/install && cd -
    rm -rf /tmp/awscliv2.zip /tmp/aws
fi

# Fetch git credentials from AWS Secrets Manager using the instance IAM role
# (no login step required — credentials are provided automatically by the instance profile)
echo "Fetching git credentials from Secrets Manager..."
GIT_CREDS=$(aws secretsmanager get-secret-value \
    --region "${AWS_REGION}" \
    --secret-id "${GIT_CREDENTIALS_SECRET_ARN}" \
    --query "SecretString" \
    --output text)

# Validate that credentials were retrieved
if [ -z "$GIT_CREDS" ]; then
    echo "Error: Failed to retrieve git credentials from Secrets Manager"
    exit 1
fi

# Validate credentials format before writing
if ! echo "$GIT_CREDS" | grep -q "://"; then
    echo "Error: Invalid git credentials format (expected '://' in string)"
    exit 1
fi

# Save credentials
printf '%s\n' "$GIT_CREDS" > ~/.git-credentials

# Clone the repository
mkdir -p ~/repos && cd ~/repos || exit
[ -d "${REPO_DIR}" ] || git clone "${REPO_URL}" "${REPO_DIR}"
cd "${REPO_DIR}" || exit
ls -la
