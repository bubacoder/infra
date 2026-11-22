#!/bin/sh
# LAPI only. No log acquisition, plugin downloads or root access.
set -eu
umask 077
config=/etc/crowdsec/config.yaml

if [ "${CROWDSEC_ONLINE_API:-false}" = true ] && [ ! -s /data/online_api_credentials.yaml ]; then
    [ ! -e /data/online_api_credentials.pending ] || {
        echo "Interrupted community registration requires private recovery" >&2
        exit 1
    }
    # Remote registration is explicitly opt-in. Never print generated credentials.
    cscli -c "$config" capi register -f /data/online_api_credentials.pending >/dev/null
    mv /data/online_api_credentials.pending /data/online_api_credentials.yaml
fi

if [ ! -s /data/local_api_credentials.yaml ]; then
    cscli -c "$config" machines add bootstrap-local --auto \
        -f /data/local_api_credentials.yaml >/dev/null
fi
if [ ! -s /data/bouncer-key ]; then
    # Never recreate an existing identity whose key file was lost.
    cscli -c "$config" bouncers list -o json >/tmp/bouncers.json
    if yq -e '.[] | select(.name == "bootstrap-traefik")' /tmp/bouncers.json >/dev/null; then
        echo "Bouncer identity exists without its key; preserve data for recovery" >&2
        exit 1
    fi
    [ ! -e /data/bouncer-key.pending ] || {
        echo "Interrupted bouncer registration requires private recovery" >&2
        exit 1
    }
    cscli -c "$config" bouncers add bootstrap-traefik -o raw >/data/bouncer-key.pending
    [ -s /data/bouncer-key.pending ]
    mv /data/bouncer-key.pending /data/bouncer-key
fi
exec crowdsec -c "$config" -no-cs
