"""Non-secret, exact-match policy; exceptions require evidence and expiry."""

from datetime import UTC, date, datetime

from .common import read_json


def load_policy(path):
    value = read_json(path)
    if not isinstance(value, dict):
        raise TypeError("Scan policy must be an object")
    if value.get("version") != 1 or not isinstance(value.get("database_max_age_hours"), (int, float)):
        raise ValueError("Invalid scan policy version or database age")
    if not 0 < value["database_max_age_hours"] <= 720:
        raise ValueError("Database freshness limit must be between 0 and 720 hours")
    expected = value.get("expected_components", {})
    if not isinstance(expected, dict) or any(
        not isinstance(name, str) or not isinstance(options, list) or not options or any(not isinstance(o, str) or not o for o in options)
        for name, options in expected.items()
    ):
        raise ValueError("Expected components must map container names to nonempty alternative component names")
    if not isinstance(value.get("triage", []), list):
        raise TypeError("Policy triage must be a list")
    for rule in value.get("triage", []):
        required = ("container", "advisory", "component", "reason", "evidence", "expires")
        if not isinstance(rule, dict) or any(not isinstance(rule.get(k), str) or not rule[k].strip() for k in required):
            raise ValueError("Triage requires exact container/advisory/component, reason, evidence and expiry")
        date.fromisoformat(rule["expires"])
    return value


def exception_for(finding, container, policy):
    for rule in policy.get("triage", []):
        if (
            rule["container"] == container
            and rule["component"] == finding["component"]
            and rule["advisory"] in finding["aliases"]
            and date.fromisoformat(rule["expires"]) >= datetime.now(UTC).date()
        ):
            return rule
    return None
