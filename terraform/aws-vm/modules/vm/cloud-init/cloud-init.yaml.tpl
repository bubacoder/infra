#cloud-config

package_upgrade: true

packages:
  - git
  - awscli

runcmd:
  # Run git repository setup with the admin user
  - chown ${ADMIN_USER}:${ADMIN_USER} ${REPO_SETUP_SCRIPT}
  - chmod 700 ${REPO_SETUP_SCRIPT}
  - su ${ADMIN_USER} -c "${REPO_SETUP_SCRIPT} setup"
  # Bootstrap ansible with root user
  - /home/${ADMIN_USER}/repos/${REPO_DIR}/ansible/bootstrap-ansible.sh

final_message: "System initialisation finished after $UPTIME seconds"