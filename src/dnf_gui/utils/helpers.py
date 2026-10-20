"""Utility functions for the DNF GUI application."""


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
