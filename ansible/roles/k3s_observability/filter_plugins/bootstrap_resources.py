"""Reuse the existing value-aware public-resource verifier."""

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "k3s_crowdsec/filter_plugins/bootstrap_resources.py"
SPEC = importlib.util.spec_from_file_location("infra_public_resource_subset", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FilterModule = MODULE.FilterModule
