"""Explicit native LAPI and plugin projections; no live or secret reads."""

import copy
import hashlib
import re

import yaml

if __package__:
    from .traefik import TraefikError, dns_name, storage_quantity
else:
    from traefik import TraefikError, dns_name, storage_quantity

MANAGER = "infra-bootstrap-crowdsec"
NAME = "bootstrap-crowdsec"
PLUGIN = "crowdsec-bouncer-traefik-plugin"
MODULE = "github.com/maxlerebourg/" + PLUGIN
IMAGE = "crowdsecurity/crowdsec:v1.8.2@sha256:65b74942f7e7ed5c60fde4ac15fc4ba715904c398c8b16dd451f4907d90347d4"
FIELDS = {"enabled", "namespace", "storage_class", "storage_size", "plugin_image", "transport", "online_api", "resources"}


def settings(config):
    return config.get("k3s", {}).get("crowdsec", {"enabled": False})


def validate_profile(config):
    value = settings(config)
    roles = config["roles"]
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise TraefikError("k3s.crowdsec requires a boolean enabled field.")
    if not value["enabled"]:
        if set(value) != {"enabled"} or "k3s_crowdsec" in roles:
            raise TraefikError("Disabled CrowdSec requires only enabled: false and no role; disabling does not uninstall.")
        return
    if set(value) != FIELDS:
        raise TraefikError("Enabled k3s.crowdsec requires exactly the documented fields.")
    if any(name not in roles for name in ("k3s", "k3s_crowdsec", "k3s_traefik")) or not (
        roles.index("k3s") < roles.index("k3s_crowdsec") < roles.index("k3s_traefik")
    ):
        raise TraefikError("Select roles in order: k3s, k3s_crowdsec, k3s_traefik.")
    traefik_settings = config.get("k3s", {}).get("traefik")
    if not isinstance(traefik_settings, dict) or not traefik_settings.get("enabled"):
        raise TraefikError("CrowdSec integration requires managed Traefik.")
    namespace = value["namespace"]
    if not dns_name(namespace) or "." in namespace or namespace.startswith("kube-") or namespace == "default" or len(namespace) > 63:
        raise TraefikError("Select a dedicated CrowdSec namespace, not a system namespace.")
    if not dns_name(value["storage_class"]):
        raise TraefikError("Select an explicit CrowdSec storage_class.")
    storage_quantity(value["storage_size"])
    if not isinstance(value["plugin_image"], str) or not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}", value["plugin_image"]):
        raise TraefikError("plugin_image must be an explicit SHA256-pinned image containing the reviewed bundled plugin and stager.")
    if value["transport"] != "http-cluster":
        raise TraefikError("The initial profile requires explicit transport: http-cluster; TLS is not inferred.")
    if type(value["online_api"]) is not bool:
        raise TraefikError("Select online_api explicitly as a boolean; no community registration is inferred.")
    resources = value["resources"]
    if not isinstance(resources, dict) or set(resources) != {"requests", "limits"}:
        raise TraefikError("Select explicit CrowdSec resources.requests and limits.")
    quantities = {}
    for kind in ("requests", "limits"):
        group = resources[kind]
        if not isinstance(group, dict) or set(group) != {"cpu", "memory"}:
            raise TraefikError("Resource requests/limits require cpu and memory.")
        for name, quantity in group.items():
            pattern = r"[1-9][0-9]*m?" if name == "cpu" else r"[1-9][0-9]*(Mi|Gi)"
            if not isinstance(quantity, str) or not re.fullmatch(pattern, quantity):
                raise TraefikError("CPU requires positive integer cores/millicores; memory requires positive Mi/Gi.")
        quantities[kind] = {
            "cpu": int(group["cpu"][:-1]) if group["cpu"].endswith("m") else int(group["cpu"]) * 1000,
            "memory": int(group["memory"][:-2]) * (1024 if group["memory"].endswith("Gi") else 1),
        }
    if any(quantities["requests"][key] > quantities["limits"][key] for key in ("cpu", "memory")):
        raise TraefikError("CrowdSec resource requests must not exceed limits.")


def plugin_definition(canonical, value):
    """Only this reviewed canonical plugin shape may cross the adapter boundary."""
    expected = {
        "Enabled": '{{env "CROWDSEC_ENABLED"}}',
        "CrowdsecLapiKey": '{{env "CROWDSEC_BOUNCER_API_KEY"}}',
        "CrowdsecLapiHost": "crowdsec:8080",
        "CrowdsecMode": "stream",
        "UpdateIntervalSeconds": 60,
        "StreamStartupBlock": True,
        "UpdateMaxFailure": 0,
    }
    if canonical != {"plugin": {PLUGIN: expected}}:
        raise TraefikError("Canonical CrowdSec plugin changed; explicitly review the adapter instead of dropping settings.")
    result = copy.deepcopy(expected)
    result["Enabled"] = True
    result.pop("CrowdsecLapiKey")
    result["CrowdsecLapiKeyFile"] = "/etc/traefik/crowdsec/bouncer-key"
    result["CrowdsecLapiHost"] = f"{NAME}.{value['namespace']}.svc:8080"
    result["CrowdsecLapiScheme"] = "http"
    result["HTTPTimeoutSeconds"] = 5
    return {"plugin": {PLUGIN: result}}


def add_plugin_values(values, value):
    """Local registration only: no Traefik plugin-registry startup downloads."""
    values["additionalArguments"] += [
        f"--experimental.localplugins.{PLUGIN}.modulename={MODULE}",
        "--experimental.abortonpluginfailure=false",
    ]
    values["deployment"]["additionalVolumes"] = [
        {"name": "crowdsec-plugin", "emptyDir": {"sizeLimit": "128Mi"}},
        {
            "name": "crowdsec-key",
            "secret": {
                "secretName": "bootstrap-traefik-cloudflare",
                # Missing key is a middleware error, not a Pod mount error.
                "optional": True,
                "items": [{"key": "bouncer-key", "path": "bouncer-key"}],
                "defaultMode": 0o440,
            },
        },
    ]
    values["additionalVolumeMounts"] = [
        {"name": "crowdsec-plugin", "mountPath": "/plugins-local", "readOnly": True},
        {"name": "crowdsec-key", "mountPath": "/etc/traefik/crowdsec", "readOnly": True},
    ]
    values["deployment"]["initContainers"] = [
        {
            "name": "crowdsec-plugin",
            "image": value["plugin_image"],
            "imagePullPolicy": "IfNotPresent",
            "command": ["/bin/sh", "/stage.sh"],
            # Timeout also exits successfully; it is not an init startup failure.
            "args": ["/plugin", "/output"],
            "securityContext": {
                "runAsUser": 65532,
                "runAsGroup": 65532,
                "runAsNonRoot": True,
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            },
            "resources": {"requests": {"cpu": "10m", "memory": "16Mi"}, "limits": {"cpu": "100m", "memory": "128Mi"}},
            "volumeMounts": [{"name": "crowdsec-plugin", "mountPath": "/output"}],
        }
    ]


def canonical_resources(resources):
    result = copy.deepcopy(resources)
    for group in result.values():
        cpu = group["cpu"]
        if cpu.endswith("m") and int(cpu[:-1]) % 1000 == 0:
            group["cpu"] = str(int(cpu[:-1]) // 1000)
        memory = group["memory"]
        if memory.endswith("Mi") and int(memory[:-2]) % 1024 == 0:
            group["memory"] = f"{int(memory[:-2]) // 1024}Gi"
    return result


def manifests(config, root):
    value = settings(config)
    if not value.get("enabled"):
        return {}
    namespace = value["namespace"]
    labels = {"app.kubernetes.io/managed-by": MANAGER, "infra.bootstrap/deployment": config["vm"]["name"]}
    pod_labels = {"app.kubernetes.io/name": NAME}

    def resource(kind, name=NAME, api="v1", **fields):
        return {
            "apiVersion": api,
            "kind": kind,
            "metadata": {"name": name, **({} if kind == "Namespace" else {"namespace": namespace}), "labels": labels.copy()},
            **fields,
        }

    engine = {
        "common": {"daemonize": False, "log_media": "stdout", "log_level": "info"},
        "config_paths": {
            "config_dir": "/etc/crowdsec",
            "data_dir": "/data",
            "simulation_path": "/etc/crowdsec/simulation.yaml",
            "hub_dir": "/etc/crowdsec/hub",
            "index_path": "/etc/crowdsec/hub-index.json",
        },
        "cscli": {"output": "human", "color": "never"},
        "db_config": {
            "type": "sqlite",
            "db_path": "/data/crowdsec.db",
            "use_wal": True,
            "flush": {"max_items": 5000, "max_age": "7d"},
        },
        "api": {
            "client": {"credentials_path": "/data/local_api_credentials.yaml"},
            "server": {"listen_uri": "0.0.0.0:8080", "profiles_path": "/etc/crowdsec/profiles.yaml", "trusted_ips": ["127.0.0.1", "::1"]},
        },
        "prometheus": {"enabled": False},
    }
    if value["online_api"]:
        engine["api"]["server"]["online_client"] = {
            "credentials_path": "/data/online_api_credentials.yaml",
            "sharing": False,
        }
    cm = resource(
        "ConfigMap",
        data={
            "config.yaml": yaml.safe_dump(engine, sort_keys=False),
            "simulation.yaml": "simulation: false\n",
            # No installed acquisition/scenario items in this LAPI-only profile.
            # The upstream image's registry index is root-only; do not grant
            # runtime root or pretend that image-bundled items are installed.
            "hub-index.json": "{}\n",
            "profiles.yaml": (root / "kubernetes/crowdsec/profiles.yaml").read_text(),
            "start.sh": (root / "kubernetes/crowdsec/start.sh").read_text(),
        },
    )
    pod = {
        "automountServiceAccountToken": False,
        "securityContext": {
            "runAsUser": 65532,
            "runAsGroup": 65532,
            "runAsNonRoot": True,
            "fsGroup": 65532,
            "fsGroupChangePolicy": "OnRootMismatch",
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        "containers": [
            {
                "name": "crowdsec",
                "image": IMAGE,
                "command": ["/bin/sh", "/etc/crowdsec/start.sh"],
                "env": [{"name": "CROWDSEC_ONLINE_API", "value": str(value["online_api"]).lower()}],
                "resources": canonical_resources(value["resources"]),
                "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                "ports": [{"name": "lapi", "containerPort": 8080}],
                "volumeMounts": [
                    {"name": "config", "mountPath": "/etc/crowdsec", "readOnly": True},
                    {"name": "data", "mountPath": "/data"},
                    {"name": "tmp", "mountPath": "/tmp"},  # noqa: S108 -- private Pod emptyDir, not a controller path
                ],
                "startupProbe": {"httpGet": {"path": "/health", "port": "lapi"}, "periodSeconds": 5, "failureThreshold": 60},
                "readinessProbe": {"httpGet": {"path": "/health", "port": "lapi"}, "periodSeconds": 5},
                "livenessProbe": {"httpGet": {"path": "/health", "port": "lapi"}, "periodSeconds": 10},
            }
        ],
        "volumes": [
            {"name": "config", "configMap": {"name": NAME}},
            {"name": "data", "persistentVolumeClaim": {"claimName": NAME}},
            {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}},
        ],
    }
    # Config changes replace the Pod; the persistent DB/identity survive.
    objects = {
        "namespace": resource("Namespace", name=namespace),
        "configmap": cm,
        "pvc": resource(
            "PersistentVolumeClaim",
            spec={
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": value["storage_class"],
                "resources": {"requests": {"storage": storage_quantity(value["storage_size"])}},
            },
        ),
        "service": resource(
            "Service", spec={"type": "ClusterIP", "selector": pod_labels, "ports": [{"name": "lapi", "port": 8080, "targetPort": "lapi"}]}
        ),
        "networkpolicy": resource(
            "NetworkPolicy",
            api="networking.k8s.io/v1",
            spec={
                "podSelector": {"matchLabels": pod_labels},
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
                                "podSelector": {"matchLabels": {"app.kubernetes.io/name": "traefik"}},
                            }
                        ],
                        "ports": [{"port": 8080, "protocol": "TCP"}],
                    }
                ],
            },
        ),
        "deployment": resource(
            "Deployment",
            api="apps/v1",
            spec={
                "replicas": 1,
                "strategy": {"type": "Recreate"},
                "selector": {"matchLabels": pod_labels},
                "template": {
                    "metadata": {
                        "labels": pod_labels,
                        "annotations": {"infra.bootstrap/config-sha256": hashlib.sha256(yaml.safe_dump(cm["data"]).encode()).hexdigest()},
                    },
                    "spec": pod,
                },
            },
        ),
    }
    return {"k3s-crowdsec-" + name + ".yaml": yaml.safe_dump(obj, sort_keys=False) for name, obj in objects.items()}
