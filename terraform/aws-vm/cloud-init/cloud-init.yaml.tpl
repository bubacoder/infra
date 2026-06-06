#cloud-config

# NOTE: Race condition between EBS volume attachment and cloud-init
# is handled inside mount-storage.sh (polls until device appears).

package_upgrade: true

packages:
  - git
  - unzip

write_files:
  - path: ${REPO_SETUP_SCRIPT}
    permissions: "0700"
    owner: root:root
    content: |
      ${indent(6, REPO_SETUP_SCRIPT_CONTENT)}
  - path: /usr/local/bin/mount-storage.sh
    permissions: "0755"
    owner: root:root
    content: |
      ${indent(6, MOUNT_STORAGE_SCRIPT_CONTENT)}

runcmd:
  - - bash
    - -euxo
    - pipefail
    - -c
    - |
      chown ${ADMIN_USER}:${ADMIN_USER} ${REPO_SETUP_SCRIPT}
      chmod 700 ${REPO_SETUP_SCRIPT}
      su ${ADMIN_USER} -c "${REPO_SETUP_SCRIPT} setup"
      /usr/local/bin/mount-storage.sh
      /home/${ADMIN_USER}/repos/${REPO_DIR}/ansible/bootstrap-ansible.sh

final_message: "System initialisation finished after $UPTIME seconds"
