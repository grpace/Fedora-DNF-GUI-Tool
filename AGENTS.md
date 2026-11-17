# DNF Package Manager (Fedora DNF GUI Tool)

PyQt6 + Kirigami (QML) desktop app that replaces KDE Discover as the updater on Fedora KDE. Every action runs the real `dnf`/`dnf5` and `flatpak` commands and streams their output. It ships as a noarch RPM attached to GitHub releases, and installed copies update themselves from those releases. The repo is public (`grpace/Fedora-DNF-GUI-Tool`, default branch `master`).

## Stack
- Python 3.12+ (the RPM requires `python3 >= 3.12`), PyQt6 6.6+, KDE Kirigami 6 + Kirigami Addons (FormCard) + `org.kde.desktop` style, all from Fedora packages (the spec requires them by `qt6qml(...)` provides). pip's PyQt6 bundles its own Qt and can't load the system Kirigami, so there is no pip install path.
- pytest and ruff are dev tools that are not declared anywhere. There is no ruff config, so ruff's default rules apply.
- `uv.lock` and `.venv/` are local and gitignored. The `.venv` has no pytest, so run the commands below with the system `python3`.

## Commands
- `QT_QPA_PLATFORM=offscreen pytest`: full suite (pytest config is in `pyproject.toml`, `pythonpath = src`). No network, root or real config needed.
- `ruff check src tests scripts`: lint.
- `python3 scripts/check_contrast.py`: WCAG AA contrast of the colors the QML adds (pills, secondary text) against Breeze Light/Dark. Exits non-zero on failure.
- `PYTHONPATH=src python3 scripts/screenshots.py OUT --demo [--strict] [--theme light|dark]`: renders every page offscreen with sample data (`scripts/demo_data.py`); `--strict` fails on any QML warning. Without `--demo` it shows this system's real data (read-only).
- `PYTHONPATH=src python3 -m dnf_gui`: run from source. On a real system it calls dnf, GitHub and possibly pkexec.
- `./build-rpm.sh`: builds the RPM from the version in `packaging/dnf-gui.spec`. The rpmbuild tree goes in `~/.cache/rpmbuild/dnf-gui` (override with `RPMBUILD_TOPDIR`) and the release copy goes to `dist/DNF-Package-Manager-vX.Y.Z.rpm` (gitignored).
- `appstreamcli validate --no-net packaging/dnf-gui.metainfo.xml` and `desktop-file-validate assets/dnf-gui.desktop`: metadata checks.

## Where Things Live
- `src/dnf_gui/core/`: dnf/flatpak backends, security, passwordless sudoers, Discover takeover, release upgrades, self-updater and QThread workers. Keep it UI-free.
- `src/dnf_gui/ui/controllers/`: the QML-facing Python. `AppController` (root, exposed as `App`), `OperationRunner` (every command: passwordless swap, sudo→pkexec retry, cancel, output), `Prompts` (async confirmations, one at a time), and page controllers. `ui/qml/`: Kirigami pages. `ui/window.py` loads `Main.qml`.
- Colors come from `Kirigami.Theme`. The few the app derives (pills, secondary text blend) must match `check_contrast.py`'s `PILL_MIX`/`SECONDARY_MIX`.
- `packaging/`: RPM spec and AppStream metainfo. `assets/dnf-gui.desktop` is shared by the spec and `install.sh`.
- `RELEASING.md`: the release checklist. Follow it rather than improvising.

## Conventions
- Run commands as argument lists, never through a shell with interpolated input. Privileged actions go through `pkexec`, or `sudo -n` when the passwordless rule is installed.
- The passwordless sudoers rule matches exact argv. `UPDATE_ARGVS` in `core/passwordless.py` must stay in sync with `DNFBackend.build_upgrade_command` and `security.build_security_update_command`. If you change an upgrade command's flags, update both and their tests, or passwordless updates silently fall back to a password prompt. Never add wildcards or `bash -c` to the rule.
- Prefer `dnf5` and keep `dnf` (dnf4) output parsing working. The backend handles both formats.
- User-facing strings use Title Case for buttons and headings.

## Gotchas
- The version lives in five places: `pyproject.toml`, `src/dnf_gui/__init__.py` (the sidebar and self-updater read it), the `Version:` and `%changelog` in `packaging/dnf-gui.spec`, a `<release>` in the metainfo, and `CHANGELOG.md`. If you miss `__init__.py`, installed copies keep offering the same update.
- rpmbuild runs outside the project dir because the spaces in this checkout's path break `%install`. Don't move `TOPDIR` back into the repo.
- The self-updater (`core/updater.py`) downloads the `.rpm` asset of the latest GitHub release and verifies it against the SHA-256 digest GitHub computed on upload. Never rename, replace or re-upload a published asset. Ship a new version instead.
- `tests/conftest.py` stubs the update-check, self-update and reminder workers, and sets a temporary `XDG_CONFIG_HOME`. New code that starts network or dnf work from `AppController` needs a stub there, or tests hit the network or abort with "QThread: Destroyed while thread is still running". Use the single session `QApplication`; don't create another one. Answer prompts with `tests.conftest.answer(controller, "yes", ...)`.
- Confirmations are async (`prompts.confirm(title, text, on_yes, ...)`); never block a slot waiting for an answer. Destructive prompts pass `destructive=True` (default No).
- QML: role or property names `id`, `enabled`, `action`, `icon`, `text` clash with QtQuick/QQC2 properties ("Cannot override FINAL property"); read such roles through `required property var model`. Every controller class declares its own `changed = pyqtSignal()` (PyQt needs the notify signal in the same class). Pages are created by `Main.qml` inside a hidden holder, because Kirigami's ColumnView hands a removed page back to its original parent. `ui/i18n.py` supplies `i18n*()` for Kirigami Addons (no KI18n under PyQt). `console.log` is filtered on Fedora; QML errors from `Qt.createComponent` reach the Qt message handler, not `engine.warnings`, so tests install a message handler.

## Before Calling a Change Done
Run pytest (it includes an offscreen QML smoke test), ruff and the contrast check. For UI changes, run `scripts/screenshots.py --demo --strict` and look at the affected pages in light and dark, then launch the app for real. For packaging changes, also run `./build-rpm.sh` and `rpm -qlp` the result.

## Git
- Conventional commits (`fix:`, `feat(ui):`, `docs:`, `build:`). Release commits are `Release vX.Y.Z`.
- Add changes to `CHANGELOG.md` (Keep a Changelog format).
- Never commit `dist/`, `*.rpm`, `uv.lock` or `.venv/`.

## Ask First
- Tagging, pushing tags, or creating or editing GitHub releases and their assets. A release reaches every installed copy through the self-updater.
- Running anything with `sudo`/`pkexec`, `install.sh`, or the app's actions against the real system (upgrades, sudoers, Discover takeover).
- Changes to the security model: the sudoers scopes, the updater's host or digest checks, or pkexec usage.
