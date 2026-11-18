"""Where the app finds the programs it runs.

Only system directories, never ``$PATH``: Fedora puts ``~/.local/bin``
first in ``$PATH``, and that directory is writable by the user, so a
planted ``dnf`` there would be what pkexec runs as root once the user types
their password.
"""

from __future__ import annotations

import os

SYSTEM_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


def find_system_binary(*names: str) -> str | None:
    """The first of ``names`` installed in a system directory, else None."""
    for name in names:
        for directory in SYSTEM_DIRS:
            path = os.path.join(directory, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


def system_binary(*names: str) -> str:
    """Like :func:`find_system_binary`, falling back to ``/usr/bin/<first>``
    (an absolute path that fails cleanly if the program isn't installed)."""
    return find_system_binary(*names) or os.path.join("/usr/bin", names[0])
