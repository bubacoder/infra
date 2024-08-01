ARG BASE_IMAGE=debian:bookworm-slim
FROM ${BASE_IMAGE}

WORKDIR /tmp/ansible-bootstrap-container

### Setup Ansible

COPY bootstrap-ansible.sh ansible.cfg requirements.yml ./

# Set cache for APT packages - https://docs.docker.com/reference/dockerfile/#run---mounttypecache
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache,sharing=locked \
    ./bootstrap-ansible.sh

# Copy Ansible directory
COPY . .

### Setup debian-base role

ARG ADMIN_USER=admin
# Alternative to hardcoded passwd: use adduser with --disabled-password
ARG ADMIN_PASSWORD=InItIal_PswD

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache,sharing=locked \
    mkdir -p inventory/host_vars/local-debian/ && \
    LOCAL_CONFIG=inventory/host_vars/local-debian/local.yaml && \
    echo admin_user: ${ADMIN_USER} > $LOCAL_CONFIG && \
    echo admin_password: ${ADMIN_PASSWORD} >> $LOCAL_CONFIG && \
    echo configure_hosts_file: false >> $LOCAL_CONFIG && \
    echo configure_ssh_key: false >> $LOCAL_CONFIG && \
    ./apply-adhoc.sh local-debian debian-base && \
    rm -rf .fact_cache

### Setup additional roles (Linuxbrew installation is per-user)

USER ${ADMIN_USER}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,uid=1000,gid=1000,target=/home/${ADMIN_USER}/.cache,sharing=locked \
    ./apply-adhoc.sh local-debian markosamuli.linuxbrew,debian-developer

WORKDIR /home/${ADMIN_USER}
