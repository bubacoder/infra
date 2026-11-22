"""Validate a shared NFS inventory and return one immutable JSON snapshot."""

import ipaddress
import json
import os
import re
import sys

import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("invalid or duplicate mapping key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def clean_path(value):
    return (
        isinstance(value, str)
        and value.startswith("/")
        and value != "/"
        and os.path.normpath(value) == value
        and re.fullmatch(r"/[A-Za-z0-9_./-]+", value) is not None
    )


def under(path, root):
    return path == root or path.startswith(root + "/")


def validate(data):  # noqa: PLR0912 -- each inventory boundary fails closed
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "server", "clients", "dataRoots", "backingMounts", "exports"}
        or type(data["version"]) is not int
        or data["version"] != 1
    ):
        raise ValueError("invalid inventory fields or version")
    server = data["server"]
    if not isinstance(server, str):
        raise TypeError("invalid server")
    try:
        ipaddress.ip_address(server)
    except ValueError:
        if len(server) > 253 or not all(len(label) <= 63 and re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", label) for label in server.split(".")):
            raise ValueError("invalid server") from None
    for field in ("clients", "dataRoots", "backingMounts"):
        values = data[field]
        if not isinstance(values, list) or not values or any(not isinstance(x, str) for x in values):
            raise ValueError("invalid inventory list")
        if len(set(values)) != len(values):
            raise ValueError("duplicate inventory entry")
    for client in data["clients"]:
        if "/" in client and "." in client.split("/", 1)[1]:
            raise ValueError("dotted masks are not supported")
        ipaddress.ip_network(client, strict=False)
    for root in data["dataRoots"] + data["backingMounts"]:
        if not clean_path(root):
            raise ValueError("invalid inventory path")
    exports = data["exports"]
    if not isinstance(exports, dict) or not exports:
        raise ValueError("exports required")
    sources, paths = set(), set()
    for name, item in exports.items():
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", name) or len(name) > 63:
            raise ValueError("invalid export name")
        if not isinstance(item, dict) or set(item) != {"source", "serverPath", "access", "capacity"}:
            raise ValueError("invalid export fields")
        source, dest = item["source"], item["serverPath"]
        if not clean_path(source) or not clean_path(dest):
            raise ValueError("invalid export path")
        if not any(under(source, root) for root in data["dataRoots"]):
            raise ValueError("source outside data roots")
        if not any(under(dest, root) for root in data["backingMounts"]):
            raise ValueError("export outside backing mounts")
        if source in sources or dest in paths:
            raise ValueError("duplicate export path")
        sources.add(source)
        paths.add(dest)
        if item["access"] not in ("read-only", "read-write"):
            raise ValueError("invalid access")
        size = item["capacity"]
        if not isinstance(size, str) or not re.fullmatch(r"[1-9][0-9]*(Ki|Mi|Gi|Ti|Pi|Ei)?", size):
            raise ValueError("capacity must be a positive integer quantity")
        unit = size[-2:] if size[-2:] in ("Ki", "Mi", "Gi", "Ti", "Pi", "Ei") else ""
        multiplier = 1024 ** (("Ki", "Mi", "Gi", "Ti", "Pi", "Ei").index(unit) + 1) if unit else 1
        if int(size[:-2] if unit else size) * multiplier > 2**63 - 1:
            raise ValueError("capacity too large")
    return data


def main():
    if len(sys.argv) != 2:
        print("Invalid NFS inventory", file=sys.stderr)
        return 1
    try:
        with open(sys.argv[1], encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=UniqueLoader)  # noqa: S506 -- SafeLoader subclass
        print(json.dumps(validate(data), sort_keys=True))
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        print("Invalid NFS inventory", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
