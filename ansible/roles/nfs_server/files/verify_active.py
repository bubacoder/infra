"""Fail if active NFS exports differ from the validated inventory."""

import ipaddress
import json
import re
import sys


def verify(inventory, output):
    expected = {}
    for item in inventory["exports"].values():
        for client in inventory["clients"]:
            key = (item["serverPath"], str(ipaddress.ip_network(client, strict=False)))
            expected[key] = "ro" if item["access"] == "read-only" else "rw"
    actual = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            raise ValueError("unrecognized active export")
        path = parts[0]
        for entry in parts[1:]:
            match = re.fullmatch(r"(\S+)\(([^()]*)\)", entry)
            if not match:
                raise ValueError("unrecognized active export")
            client, flags = match.groups()
            key = (path, str(ipaddress.ip_network(client, strict=False)))
            options = set(flags.split(","))
            if key in actual or not {"sync", "root_squash", "no_subtree_check"} <= options:
                raise ValueError("invalid active export")
            if ("ro" in options) == ("rw" in options):
                raise ValueError("invalid active access mode")
            actual[key] = "ro" if "ro" in options else "rw"
    if actual != expected:
        raise ValueError("active exports differ from inventory")


def verify_configuration(inventory, output):
    exports = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            raise ValueError("invalid export configuration")
        for client in parts[1:]:
            exports.append(f"{parts[0]} {client}")
    verify(inventory, "\n".join(exports))


def main():
    try:
        data = json.load(sys.stdin)
        if "configuration" in data:
            verify_configuration(data["inventory"], data["configuration"])
        else:
            verify(data["inventory"], data["active"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        print("Active NFS exports do not match the selected inventory", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
