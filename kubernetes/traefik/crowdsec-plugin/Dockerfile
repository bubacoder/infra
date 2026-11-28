FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf AS source
# renovate: datasource=git-tags depName=maxlerebourg/crowdsec-bouncer-traefik-plugin
ARG CROWDSEC_PLUGIN_REF=v1.8.2
ARG CROWDSEC_PLUGIN_TAG_SHA=b0431e2e530cadd629583288909b462c8a6e9669
# hadolint ignore=DL3018
RUN apk add --no-cache git \
    && git clone --depth 1 --branch "$CROWDSEC_PLUGIN_REF" \
      https://github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin.git /plugin \
    && test "$(git -C /plugin rev-parse 'HEAD^{commit}')" = "$CROWDSEC_PLUGIN_TAG_SHA" \
    && rm -rf /plugin/.git

FROM alpine:3.24@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf
COPY --from=source /plugin /plugin
COPY stage.sh /stage.sh
USER 65532:65532
ENTRYPOINT ["/bin/sh", "/stage.sh"]
