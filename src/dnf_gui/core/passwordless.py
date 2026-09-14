"""Optional passwordless updates via a tightly-scoped sudoers drop-in.

Why sudoers instead of a polkit rule?
  The pkexec man page explicitly warns that ``command_line`` "do[es] not use
  this for any security checks, it is not secure", and pkexec performs no
  validation of the arguments passed to the program. Matching only on
  ``program`` (e.g. /usr/bin/dnf5) would therefore make *every* dnf
  invocation — install, remove, repo changes — passwordless. sudoers, in
  contrast, matches the exact argument vector in its privileged parser, so
  we can allow ``dnf upgrade`` while still requiring a password for
  ``dnf install`` / ``remove`` / repo edits.

Scopes:
  * ``updates`` (recommended) — passwordless ``dnf upgrade`` / ``dnf update``
    only. Daily updates stop prompting; installs, removals, autoremove,
    distro-sync, repo/COPR changes and firmware updates still ask.
  * ``full`` — passwordless for any dnf/dnf5 invocation from this app.
    Convenient, but any local process running as you could then install or
    remove system packages without a prompt. Offered for single-user
    desktops that accept the tradeoff.

Safety properties:
  * Per-user rule (``<you> ALL=(root) NOPASSWD: ...``), not ``%wheel`` —
    enabling it for yourself doesn't change anything for other accounts.
  * The rule file is validated with ``visudo -c`` *before* it is
    installed, and re-validated after install (with automatic rollback).
  * Nothing is installed by default — enabling requires one polkit/sudo
    authentication, after which updates run via ``sudo -n`` (non-
    interactive, never prompts). If the rule is missing or broken the app
    transparently falls back to ``pkexec``.
  * ``bash -c`` wrappers are deliberately *never* covered: allowing
    passwordless ``bash`` as root would be equivalent to passwordless root.
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import tempfile

SUDOERS_FILE = "/etc/sudoers.d/90-dnf-gui"
SCOPE_OFF = "off"
SCOPE_UPDATES = "updates"
SCOPE_FULL = "full"

# Absolute paths sudo will match literally. Fedora keeps everything under
# /usr/bin (/bin is a symlink, but sudoers compares the literal string, so
# list both spellings; harmless if one doesn't exist).
DNF_PATHS = ("/usr/bin/dnf", "/usr/bin/dnf5", "/bin/dnf", "/bin/dnf5")

# argv[1] verbs covered by the "updates" scope. Read-only verbs need no
# privilege at all; risky verbs (install, remove, autoremove, distro-sync,
# group, config-manager, copr, history undo, clean) stay behind a prompt.
UPDATE_VERBS = ("upgrade", "update")


def current_user() -> str:
    """Best-effort login name for the per-user sudoers rule."""
    for var in ("SUDO_USER", "LOGNAME", "USER"):
        val = os.environ.get(var)
        if val and val != "root":
            return val
    try:
        return getpass.getuser()
    except Exception:
        return ""


def _rule_commands(scope: str) -> list[str]:
    """Render the RHS command list for a sudoers rule line."""
    if scope == SCOPE_FULL:
        return [f"{path} *" for path in DNF_PATHS]
    # updates scope: only the upgrade verbs, any flags/packages after them
    cmds: list[str] = []
    for path in DNF_PATHS:
        for verb in UPDATE_VERBS:
            cmds.append(f"{path} {verb} *")
    return cmds


def build_rule_content(user: str, scope: str) -> str:
    """Build the full sudoers drop-in text (caller must validate+install)."""
    cmds = ", ".join(_rule_commands(scope))
    return (
        f"# DNF Package Manager — passwordless {scope} (scope={scope})\n"
        "# Managed by the app (Settings > Password prompts).\n"
        "# Delete this file to restore password prompts for everything.\n"
        f"{user} ALL=(root) NOPASSWD: {cmds}\n"
    )


def validate_content(content: str) -> tuple[bool, str]:
    """Syntax-check generated content with ``visudo -c`` (no root needed)."""
    visudo = shutil.which("visudo")
    if not visudo:
        return False, "visudo not found — cannot validate safely, aborting."
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sudoers", delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                [visudo, "-c", "-f", tmp_path],
                capture_output=True, text=True, timeout=15,
            )
            ok = result.returncode == 0
            msg = (result.stdout + result.stderr).strip() or "syntax OK"
            return ok, msg
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"validation failed: {e}"


def is_covered(argv: list[str], scope: str) -> bool:
    """True if ``argv`` (a pkexec-style command) may run via ``sudo -n``.

    Only literal ``[pkexec] <dnf-path> <verb> ...`` invocations match.
    ``bash -c`` wrappers never match — by design (see module docstring).
    """
    if scope not in (SCOPE_UPDATES, SCOPE_FULL):
        return False
    if not argv:
        return False
    rest = argv[1:] if argv[0] == "pkexec" else argv[:]
    if len(rest) < 2 or rest[0] == "sudo":
        return False
    program, verb = rest[0], rest[1]
    if program not in DNF_PATHS:
        return False
    if scope == SCOPE_FULL:
        return True
    return verb in UPDATE_VERBS


def maybe_passwordless(cmd: list[str], scope: str) -> list[str]:
    """Rewrite ``pkexec ...`` to ``sudo -n ...`` when covered by the rule."""
    if cmd and cmd[0] == "pkexec" and is_covered(cmd, scope):
        return ["sudo", "-n"] + cmd[1:]
    return cmd


def parse_sudo_list(output: str) -> str:
    """Infer our scope from ``sudo -n -l`` output. Returns a SCOPE_* string."""
    nopasswd_cmds: list[str] = []
    for line in output.splitlines():
        if "NOPASSWD:" in line:
            nopasswd_cmds.append(line.split("NOPASSWD:", 1)[1])
    blob = " ".join(nopasswd_cmds)
    if not blob or "dnf" not in blob:
        return SCOPE_OFF
    # Full scope shows up as a bare "<path> *" entry for a dnf binary.
    bare = [c.strip() for c in blob.split(",")]
    for entry in bare:
        # Strip any leading "(root) NOPASSWD:"-style prefix remnants on first item
        entry = re.sub(r"^\(.*\)\s*", "", entry)
        if re.fullmatch(r"(?:/usr)?/s?bin/dnf5?\s+\*", entry):
            return SCOPE_FULL
    if re.search(r"dnf5?\s+(upgrade|update)\b", blob):
        return SCOPE_UPDATES
    return SCOPE_OFF


def live_scope() -> str:
    """Best-effort detection of what's actually in effect (no root needed)."""
    sudo = shutil.which("sudo")
    if not sudo:
        return SCOPE_OFF
    try:
        result = subprocess.run(
            [sudo, "-n", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return SCOPE_OFF
        return parse_sudo_list(result.stdout)
    except (subprocess.TimeoutExpired, OSError):
        return SCOPE_OFF


def build_install_commands(content: str) -> list[str]:
    """One pkexec'd shell: install rule file, chmod 0440, visudo-check.

    The heredoc uses a quoted delimiter so rule text is never expanded.
    A failed post-install check removes the file again (fail closed).
    """
    script = (
        f"cat > {SUDOERS_FILE} <<'DNFGUI_EOF'\n"
        f"{content}"
        "DNFGUI_EOF\n"
        f"chmod 0440 {SUDOERS_FILE}\n"
        f"visudo -c -f {SUDOERS_FILE} || {{ rm -f {SUDOERS_FILE}; "
        'echo "visudo check FAILED — rule removed again"; exit 1; }\n'
        'echo "passwordless rule installed and validated"'
    )
    return ["pkexec", "bash", "-c", script]


def build_remove_commands() -> list[str]:
    """Remove the drop-in again (restores prompts everywhere)."""
    return ["pkexec", "bash", "-c", f"rm -f {SUDOERS_FILE} && echo removed"]
