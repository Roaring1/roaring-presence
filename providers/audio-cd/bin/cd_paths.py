"""Small shared path helpers for the standalone audio-CD tools."""
from __future__ import annotations

import os
import shutil


def installed_program(name: str) -> str:
    """Resolve a companion command from PATH or standard user bin locations.

    ~/.local/bin is the canonical install target. ~/bin remains a migration
    fallback for existing installs, but neither directory must be in PATH.
    """
    found = shutil.which(name)
    if found:
        return found
    for directory in ("~/.local/bin", "~/bin"):
        candidate = os.path.expanduser(os.path.join(directory, name))
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return os.path.expanduser(os.path.join("~/.local/bin", name))
