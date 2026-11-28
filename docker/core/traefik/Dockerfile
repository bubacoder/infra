FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS crowdsec_plugin

# renovate: datasource=git-tags depName=maxlerebourg/crowdsec-bouncer-traefik-plugin
ARG CROWDSEC_PLUGIN_REF=v1.8.2
ARG CROWDSEC_PLUGIN_TAG_SHA=b0431e2e530cadd629583288909b462c8a6e9669

# hadolint ignore=DL3018
RUN apk add --no-cache git \
    && git clone --depth 1 --branch "$CROWDSEC_PLUGIN_REF" \
        https://github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin.git /plugin \
    && test "$(git -C /plugin rev-parse 'HEAD^{commit}')" = "$CROWDSEC_PLUGIN_TAG_SHA" \
    && rm -rf /plugin/.git

# Traefik binds privileged ports and accesses the root-owned Docker socket.
# kics-scan ignore-line
FROM traefik:v3.7.19@sha256:a6c0194dda77bcb804824580f36fa7edc56e315b1acfe933366c8b52844a78a4

COPY --from=crowdsec_plugin /plugin /plugins-local/src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin
