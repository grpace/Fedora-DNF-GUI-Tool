"""Utility functions for the DNF GUI application."""

import os
import subprocess


def is_root() -> bool:
    """Check if the application is running as root."""
    return os.geteuid() == 0


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def check_dnf_available() -> bool:
    """Check if DNF is available on the system."""
    try:
        result = subprocess.run(
            ["dnf", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_fedora_version() -> str:
    """Get the Fedora version string."""
    try:
        with open("/etc/fedora-release", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Unknown"
