"""Offline projections for the opt-in bundled-Traefik adapter, never live state."""

import copy
import ipaddress
import re

import yaml

NAMESPACE = "kube-system"
MANAGER = "infra-bootstrap-traefik"
CONFIGMAP = "bootstrap-traefik-dynamic"
PVC = "bootstrap-traefik-acme"
CLOUDFLARE_RESOURCE = "bootstrap-traefik-cloudflare"
FIELDS = {"enabled", "domain", "admin_cidr", "middlewares", "acme_environment", "storage_class", "storage_size"}


class TraefikError(Exception):
    """Field-only errors suitable for private-input diagnostics."""


def dns_name(value):
    return (
        isinstance(value, str)
        and len(value) <= 253
        and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in value.split("."))
    )


def storage_quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*(?:Mi|Gi)", value):
        raise TraefikError("storage_size must be a positive integer Mi/Gi quantity; PVC resizing/migration is not automatic.")
    number = int(value[:-2]) * (1 << (20 if value.endswith("Mi") else 30))
    if number > (1 << 63) - 1:
        raise TraefikError("storage_size exceeds Kubernetes quantity bounds.")
    for exponent, suffix in ((60, "Ei"), (50, "Pi"), (40, "Ti"), (30, "Gi"), (20, "Mi")):
        if number % (1 << exponent) == 0:
            return str(number // (1 << exponent)) + suffix
    raise TraefikError("storage_size cannot be represented exactly.")


def selected_policy(root, names):
    directory = root / "docker/security/traefik/config/dynamic"
    try:
        policy = yaml.safe_load((directory / "middlewares.yml").read_text())
        tls_text = (directory / "tls.yml").read_text()
        tls = yaml.safe_load(tls_text)
        catalog = policy["http"]["middlewares"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        raise TraefikError("Shared Traefik dynamic sources are unavailable or invalid.") from None
    if not isinstance(catalog, dict):
        raise TraefikError("Shared middleware catalog must be a mapping.")
    selected, active = {}, set()

    def visit(name):
        if not isinstance(name, str) or name not in catalog or name in active:
            raise TraefikError("Selected middleware dependencies must exist and have no cycles.")
        if name in selected:
            return
        definition = catalog[name]
        if not isinstance(definition, dict) or len(definition) != 1 or set(definition) - {"chain", "headers", "redirectScheme", "ipAllowList"}:
            raise TraefikError("Selected middleware requires unsupported auth/plugin configuration; dependencies are never silently omitted.")
        active.add(name)
        chain = definition.get("chain", {})
        if not isinstance(chain, dict):
            raise TraefikError("Shared middleware chains require a mapping.")
        children = chain.get("middlewares", [])
        if not isinstance(children, list):
            raise TraefikError("Shared middleware chains require ordered name lists.")
        for child in children:
            visit(child)
        active.remove(name)
        selected[name] = copy.deepcopy(definition)

    for name in names:
        visit(name)
    text = yaml.safe_dump(selected)
    permitted = r'\{\{\s*env\s+"LOCAL_ACCESS_ADMIN_CIDR"\s*\}\}'
    if "{{" in re.sub(permitted, "", text):
        raise TraefikError("Selected middleware has an unsupported environment/template dependency.")
    try:
        generated = tls["tls"]["stores"]["default"]["defaultGeneratedCert"]
        if generated["resolver"] != "letsencrypt":
            raise TraefikError("Shared TLS policy must use the letsencrypt resolver.")
        shape = (set(tls), set(tls["tls"]), set(tls["tls"]["stores"]), set(tls["tls"]["stores"]["default"]), set(generated), set(generated["domain"]))
        if shape != ({"tls"}, {"stores"}, {"default"}, {"defaultGeneratedCert"}, {"resolver", "domain"}, {"main", "sans"}):
            raise TraefikError("Shared TLS file contains settings outside the supported default-generated certificate profile.")
    except (KeyError, TypeError):
        raise TraefikError("Shared default-generated certificate policy is required.") from None
    if "{{" in re.sub(r'\{\{\s*env\s+"MYDOMAIN"\s*\}\}', "", tls_text):
        raise TraefikError("Shared TLS policy has an unsupported template dependency.")
    dynamic = {"http": {"middlewares": selected}}
    if "tls" in policy:
        if not isinstance(policy["tls"], dict) or set(policy["tls"]) - {"options"}:
            raise TraefikError("Shared middleware TLS policy may define options only; stores belong to the canonical TLS file.")
        dynamic["tls"] = copy.deepcopy(policy["tls"])
    return {"middlewares.yaml": yaml.safe_dump(dynamic, sort_keys=False), "tls.yaml": tls_text}


def validate_profile(config, root):
    settings = config.get("k3s", {}).get("traefik", {"enabled": False})
    role = "k3s_traefik" in config["roles"]
    if not isinstance(settings, dict) or type(settings.get("enabled")) is not bool:
        raise TraefikError("k3s.traefik requires a boolean enabled field.")
    if not settings["enabled"]:
        if set(settings) != {"enabled"} or role:
            raise TraefikError("Disabled Traefik settings require only enabled: false and no k3s_traefik role; disabling does not uninstall it.")
        return
    if set(settings) != FIELDS or not role or "k3s" not in config["roles"] or config["roles"].index("k3s") > config["roles"].index("k3s_traefik"):
        raise TraefikError("Enabled Traefik requires all documented settings and ordered roles k3s, k3s_traefik.")
    domain = settings["domain"]
    if not dns_name(domain) or "." not in domain or not domain.rsplit(".", 1)[1][0].isalpha():
        raise TraefikError("k3s.traefik.domain requires a fully qualified lowercase DNS name.")
    try:
        network = ipaddress.ip_network(settings["admin_cidr"], strict=True)
    except (ValueError, TypeError):
        network = None
    if not isinstance(settings["admin_cidr"], str) or network is None or network.prefixlen == 0:
        raise TraefikError("k3s.traefik.admin_cidr requires an explicit canonical CIDR, never an all-addresses range.")
    if settings["acme_environment"] not in ("staging", "production"):
        raise TraefikError("Select k3s.traefik.acme_environment explicitly: staging or production.")
    if not dns_name(settings["storage_class"]):
        raise TraefikError("Select an explicit existing storage_class for the ACME PVC.")
    storage_quantity(settings["storage_size"])
    email = config["host"].get("acme_email", "")
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise TraefikError("Enabled Traefik requires host.acme_email.")
    names = settings["middlewares"]
    if not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names) or len(set(names)) != len(names):
        raise TraefikError("Select a nonempty list of unique shared middleware names.")
    selected_policy(root, names)


def manifests(config, root):
    settings = config.get("k3s", {}).get("traefik", {})
    if not settings.get("enabled"):
        return {}
    staging = settings["acme_environment"] == "staging"
    labels = {"app.kubernetes.io/managed-by": MANAGER, "infra.bootstrap/deployment": config["vm"]["name"]}

    def resource(kind, name, **fields):
        return {
            "apiVersion": "helm.cattle.io/v1" if kind == "HelmChartConfig" else "v1",
            "kind": kind,
            "metadata": {"name": name, "namespace": NAMESPACE, "labels": labels.copy()},
            **fields,
        }

    values = {
        "deployment": {"replicas": 1},
        "updateStrategy": {"type": "Recreate", "rollingUpdate": None},
        "podSecurityContext": {
            "runAsUser": 65532,
            "runAsGroup": 65532,
            "runAsNonRoot": True,
            "fsGroup": 65532,
            "fsGroupChangePolicy": "OnRootMismatch",
        },
        "persistence": {"enabled": True, "existingClaim": PVC, "path": "/data"},
        "providers": {"kubernetesCRD": {"enabled": True, "allowCrossNamespace": False}, "file": {"enabled": False}},
        "additionalArguments": ["--providers.file.directory=/etc/traefik/bootstrap-dynamic", "--providers.file.watch=true"],
        "volumes": [{"name": CONFIGMAP, "type": "configMap", "mountPath": "/etc/traefik/bootstrap-dynamic"}],
        "env": [
            {"name": "MYDOMAIN", "value": settings["domain"]},
            {"name": "LOCAL_ACCESS_ADMIN_CIDR", "value": settings["admin_cidr"]},
            {"name": "CLOUDFLARE_DNS_API_TOKEN", "valueFrom": {"secretKeyRef": {"name": CLOUDFLARE_RESOURCE, "key": "token"}}},
        ],
        "certificatesResolvers": {
            "letsencrypt": {
                "acme": {
                    "email": config["host"]["acme_email"],
                    "storage": "/data/acme-staging.json" if staging else "/data/acme.json",
                    "caServer": "https://acme-staging-v02.api.letsencrypt.org/directory"
                    if staging
                    else "https://acme-v02.api.letsencrypt.org/directory",
                    # Match Compose: split-horizon LAN DNS can hide the public
                    # SOA and make lego discover the TLD instead of our zone.
                    "dnsChallenge": {"provider": "cloudflare", "resolvers": ["1.1.1.1:53", "8.8.8.8:53"]},
                }
            }
        },
    }
    objects = {
        "configmap": resource("ConfigMap", CONFIGMAP, data=selected_policy(root, settings["middlewares"])),
        "pvc": resource(
            "PersistentVolumeClaim",
            PVC,
            spec={
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": settings["storage_class"],
                "resources": {"requests": {"storage": storage_quantity(settings["storage_size"])}},
            },
        ),
        "helmchartconfig": resource("HelmChartConfig", "traefik", spec={"valuesContent": yaml.safe_dump(values, sort_keys=False)}),
    }
    return {"k3s-traefik-" + name + ".yaml": yaml.safe_dump(obj, sort_keys=False) for name, obj in objects.items()}
