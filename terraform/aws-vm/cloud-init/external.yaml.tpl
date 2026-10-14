#cloud-config
# No repository credentials or service secrets belong in EC2 user data.
hostname: ${HOSTNAME}
preserve_hostname: false
manage_etc_hosts: true
users:
  - default
  - name: ${ADMIN_USER}
    groups: [sudo]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    ssh_authorized_keys:
      - ${jsonencode(SSH_PUBLIC_KEY)}
packages:
  - curl
  - nvme-cli
  - snapd
write_files:
  - path: /etc/systemd/system/docker.service.d/storage.conf
    permissions: "0644"
    owner: root:root
    content: |
      [Unit]
      RequiresMountsFor=/storage
      [Service]
      ExecStartPre=/usr/bin/mountpoint -q /storage
  - path: /usr/local/bin/mount-storage.sh
    permissions: "0755"
    owner: root:root
    content: |
      ${indent(6, MOUNT_STORAGE_SCRIPT_CONTENT)}
runcmd:
  - - bash
    - -ec
    - |
      snap list amazon-ssm-agent >/dev/null 2>&1 || snap install amazon-ssm-agent --classic
      snap start --enable amazon-ssm-agent
      bash /usr/local/bin/mount-storage.sh --defer-initialization
final_message: "External bootstrap prerequisites finished after $UPTIME seconds"
