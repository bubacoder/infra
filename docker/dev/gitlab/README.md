GitLab Community Edition docker image based on the Omnibus package

Visit the GitLab URL, and sign in with the username root and the password from the following command:  
`docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password`

Register the runner (`gitlab-runner` service): https://docs.gitlab.com/runner/register/index.html#docker

---

Upgrade Path:
GitLab requires stopping at intermediate versions (x.2, x.5, x.8, x.11) during upgrades.
Background migrations must complete before proceeding to the next version.
Example: 17.11 -> 18.2 -> 18.5 -> 18.8 (cannot skip intermediate stops)

PostgreSQL: GitLab 18+ requires PostgreSQL 16.5+. Version 14 is no longer supported.
For single-node Linux package installs, run: sudo gitlab-ctl pg-upgrade -V 16
For HA/Geo/external DB setups, upgrade PostgreSQL manually before upgrading GitLab.

Check pending migrations before upgrading:
docker exec -it gitlab gitlab-psql -c "SELECT job_class_name, table_name FROM batched_background_migrations WHERE status NOT IN(3, 6);"

Upgrade path calculator: https://gitlab-com.gitlab.io/support/toolbox/upgrade-path/
Upgrade docs: https://docs.gitlab.com/update/versions/gitlab_18_changes/

---

Links:
- Home: https://about.gitlab.com/install/ce-or-ee/
- Image: https://hub.docker.com/r/gitlab/gitlab-ce/
- Docker install instructions: https://docs.gitlab.com/ee/install/docker.html
