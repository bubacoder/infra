# NFS server role

Explicitly set `nfs_server_inventory_file` to the controller-side shared NFS
inventory. The role validates one snapshot before touching the host. It installs
the Debian NFS server and renders a dedicated exports file, restricted to the
inventory clients, with root squashing and explicit read-only/read-write access.
Each configured backing mount must already be mounted.

The `ansible/playbooks/nfs-server.yaml` playbook targets only the explicit
`nfs_servers` inventory group; provide the inventory file path as an Ansible
variable. The selected server must match the inventory's configured server
address or hostname.

The role deliberately refuses any other `/etc/exports.d/*.exports` file or an
active `/etc/exports` entry. It does not remove or adopt the existing manual
Kiwix export; migrating that export requires a separately reviewed procedure.
The generated systemd guard checks backing mounts on server startup. It cannot
prevent a later manual export reload or guarantee recovery from disk failure.

Applying or restarting the NFS server affects a live host and requires explicit
authorization. This role does not configure a firewall or encrypt NFS traffic.
