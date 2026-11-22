# NFS client role

Install `nfs-common` on an explicitly selected Debian-family Kubernetes node.
The role does not mount shares or change node firewall settings. Kubernetes
kubelet mounts explicitly configured PVs when workloads need them.

Applying this role changes the selected host and requires separate authorization.
