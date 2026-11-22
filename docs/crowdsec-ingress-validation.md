# CrowdSec ingress validation

Use the [role guide](../ansible/roles/k3s_crowdsec/README.md) to configure the
opt-in LAPI and Traefik integration and to run the bounded update. The role
verifies owned resources, configuration, bound storage, controller rollout,
plugin and key presence, and certificate hostname and validity. These checks do
not substitute for request-level enforcement.

## Request-level checks

Run the isolated tests in `tests/bootstrap/test_publicaccess_runtime.py` where
Docker and the pinned images are available. They exercise plugin and credential
failure, decision enforcement, LAPI outage and recovery, and persistent
identity. Local access should remain available when a protected route fails.
The test pins Traefik **3.7.17**; its results do not establish equivalent
behavior for a deployment using 3.7.13 or another image.

For live acceptance, separately authorize a synthetic route and owned test
client. Verify a trusted TLS response, expected security headers, a temporary
ban producing HTTP 403, an unbanned client remaining accessible, and recovery
after removing the exact test decision. Check that an untrusted namespace
cannot reach LAPI and that forwarded-header spoofing does not bypass the ban.
Verify that existing application routes remain unchanged. Do not ban a
production client as part of this test.

## Limits

- Application-log acquisition remains deferred; manual or community decisions
  do not provide application-specific local detection coverage.
- Real external-client IP preservation, external denial and upstream proxy
  trust require separate tests through the actual internet-facing path.
- Isolated tests do not establish live LAPI failure behavior.
- Stream-mode failure detection uses a 60-second interval and five-second
  request timeout, not instantaneous outage detection.
- Persistent local storage and a preloaded image are not HA or tested recovery.
  Replacement nodes need image preloading; external backup/restore remains
  unverified.
