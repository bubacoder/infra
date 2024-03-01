#!/bin/bash
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
echo "${GIT_CREDENTIALS}" > ~/.git-credentials

mkdir ~/repos && cd ~/repos || exit
git clone "${REPO_URL}" "${REPO_DIR}"
cd "${REPO_DIR}" || exit
ls -la
