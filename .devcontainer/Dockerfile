### Setup Ansible

ARG BASE_IMAGE=debian:trixie-slim
# hadolint ignore=DL3006
FROM ${BASE_IMAGE} AS dev-ansible

WORKDIR /tmp/ansible-bootstrap-container

COPY bootstrap-ansible.sh ansible.cfg requirements.yml ./

# Set cache for APT packages - https://docs.docker.com/reference/dockerfile/#run---mounttypecache
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache,sharing=locked \
    ./bootstrap-ansible.sh

# Copy Ansible directory
COPY . .

### Setup debian_base role

FROM dev-ansible AS dev-base

ARG ADMIN_USER=admin

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/root/.cache,sharing=locked \
    mkdir -p inventory/host_vars/local-debian/ && \
    LOCAL_CONFIG=inventory/host_vars/local-debian/local.yaml && \
    echo admin_user: "${ADMIN_USER}" > "$LOCAL_CONFIG" && \
    echo configure_hosts_file: false >> "$LOCAL_CONFIG" && \
    echo configure_ssh_key: false >> "$LOCAL_CONFIG" && \
    ./apply-adhoc.sh local-debian debian_base && \
    rm -rf .fact_cache

### Setup additional roles (Linuxbrew installation is per-user)

FROM dev-base AS dev-final

# Note: An ARG instruction goes out of scope at the end of the build stage where it was defined.
#   To use an arg in multiple stages, each stage must include the ARG instruction.
ARG ADMIN_USER=admin

USER ${ADMIN_USER}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    ./apply-adhoc.sh local-debian markosamuli.linuxbrew,debian_developer

WORKDIR /home/${ADMIN_USER}
