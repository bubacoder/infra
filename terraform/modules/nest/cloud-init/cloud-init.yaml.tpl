#cloud-config

# HACK There is a race condition between volume attaching and cloud-init script -> Handled by mount-storage.sh
#mounts:
# - [ /dev/sdc1, /storage, "ext4", "discard,errors=remount-ro", "0", "1" ]

package_upgrade: true

packages:
  - git

runcmd:
  # Run git repository setup with the admin user
  - chown ${ADMIN_USER}:${ADMIN_USER} ${REPO_SETUP_SCRIPT}
  - chmod 700 ${REPO_SETUP_SCRIPT}
  - su ${ADMIN_USER} -c "${REPO_SETUP_SCRIPT} setup"
  # Bootstrap ansible with root user
  - /home/${ADMIN_USER}/repos/${REPO_DIR}/ansible/bootstrap-ansible.sh

final_message: "System initialisation finished after $UPTIME seconds"
