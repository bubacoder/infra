"""Compare desired public resource fields without rejecting API-added defaults."""


def resource_subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and resource_subset(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(resource_subset(left, right) for left, right in zip(expected, actual, strict=True))
        )
    # Ansible wraps strings/integers with provenance tags; compare their values,
    # but never let Python's True == 1 hide a Kubernetes boolean mismatch.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    return expected == actual


class FilterModule:
    def filters(self):
        return {"bootstrap_resource_subset": resource_subset}
