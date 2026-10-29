"""Deployment identity and managed artifact paths, without filesystem mutation."""

import stat
from dataclasses import dataclass
from pathlib import Path


class BootstrapPathError(ValueError):
    """An operator-safe deployment layout error."""


@dataclass(frozen=True)
class BootstrapPaths:
    """Keep the deployment identity separate from its managed state directory."""

    deployment: Path

    @property
    def state(self) -> Path:
        """Return the managed state root."""
        return self.deployment / "state"

    @property
    def generated(self) -> Path:
        """Return the generated native input directory."""
        return self.state / "generated"

    @property
    def plans(self) -> Path:
        """Return the reviewed native plan directory."""
        return self.state / "plans"

    @property
    def backups(self) -> Path:
        """Return the private controller access backup directory."""
        return self.state / "backups"

    def check_state(self) -> None:
        """Validate existing state without creating it or changing permissions."""
        state = self.state
        if state.is_symlink() or (state.exists() and (not state.is_dir() or stat.S_IMODE(state.stat().st_mode) & 0o077)):
            raise BootstrapPathError("Bootstrap state/ must be a nonsymlinked private directory (0700).")

    def plan(self, target: str, kind: str) -> Path:
        """Return the saved plan for a validated provider and operation kind."""
        if kind == "apply":
            name = "aws.tfplan"
        elif target == "proxmox":
            name = "proxmox-destroy-plan.json"
        else:
            name = "destroy.tfplan"
        return self.plans / name
