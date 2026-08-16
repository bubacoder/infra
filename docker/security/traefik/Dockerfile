FROM alpine:3.24 AS crowdsec_plugin

# renovate: datasource=git-tags depName=maxlerebourg/crowdsec-bouncer-traefik-plugin
ARG CROWDSEC_PLUGIN_REF=v1.7.1
ARG CROWDSEC_PLUGIN_TAG_SHA=bc83e9d0924b9fefcaed5beea880ab18b9f58764

# hadolint ignore=DL3018
RUN apk add --no-cache git \
    && git clone --depth 1 --branch "$CROWDSEC_PLUGIN_REF" \
        https://github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin.git /plugin \
    && test "$(git -C /plugin rev-parse "$CROWDSEC_PLUGIN_REF")" = "$CROWDSEC_PLUGIN_TAG_SHA" \
    && test "$(git -C /plugin rev-parse 'HEAD^{commit}')" = "$(git -C /plugin rev-parse "${CROWDSEC_PLUGIN_REF}^{commit}")" \
    && rm -rf /plugin/.git

# Traefik binds privileged ports and accesses the root-owned Docker socket.
# kics-scan ignore-line
FROM traefik:v3.7.10

COPY --from=crowdsec_plugin /plugin /plugins-local/src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin
