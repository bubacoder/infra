
# Bootstrapping hosts with authentication

1. Copy public SSH key, e.g.:
   `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@192.168.1.50`
2. Run playbook with existing user (root or your user if configured)
3. Verify the connection with: `ansible all -m ping`
