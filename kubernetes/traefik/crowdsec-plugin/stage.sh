#!/bin/sh
# A fresh Pod emptyDir is the only output. Never publish a partial plugin.
# An already-started init container must not make local ingress unavailable.
set -u
umask 022
source=${1:-/plugin}
output=${2:-/output}
destination="$output/src/github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin"
staging="$output/.staging"

unavailable() {
    echo "CrowdSec plugin unavailable; protected routers must remain disabled" >&2
    exit 0
}

# There is deliberately no network operation or retry loop here.
[ -f "$source/go.mod" ] && [ -f "$source/.traefik.yml" ] &&
    [ -f "$source/bouncer.go" ] && [ -d "$source/vendor" ] || unavailable
[ ! -e "$destination" ] || exit 0
mkdir -p "$output/src/github.com/maxlerebourg" || unavailable
# A prior interrupted copy may exist, but was never on Traefik's module path.
# Refuse it instead of publishing it or deleting ambiguous data.
[ ! -e "$staging" ] || unavailable
mkdir "$staging" || unavailable
timeout 20 cp -R "$source/." "$staging/" || unavailable
timeout 20 chmod -R a+rX "$staging" || unavailable
mv "$staging" "$destination" || unavailable
echo "CrowdSec plugin staged"
