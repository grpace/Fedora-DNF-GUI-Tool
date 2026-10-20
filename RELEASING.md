# Release Checklist

Use this checklist when preparing a new release of DNF Package Manager.

## Pre-Release

- [ ] Run the tests: `QT_QPA_PLATFORM=offscreen pytest`
- [ ] Lint: `ruff check src tests scripts`
- [ ] Contrast check: `PYTHONPATH=src python3 scripts/check_contrast.py`
- [ ] Launch the app (`PYTHONPATH=src python3 -m dnf_gui`) and click through every page in light and dark mode
- [ ] Update the version in every location below
- [ ] Move the `CHANGELOG.md` entries under a dated `## [X.Y.Z]` heading
- [ ] Validate metadata: `appstreamcli validate --no-net packaging/dnf-gui.metainfo.xml` and `desktop-file-validate assets/dnf-gui.desktop`
- [ ] Refresh `docs/screenshots/` if the UI changed (`updates-dark.png`, `packages-search-light.png`, `settings-discover-dark.png`) and re-read `docs/switching-from-discover.md` against the Settings page
- [ ] Commit: `Release vX.Y.Z`

## Version Locations

| File | Location |
|------|----------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/dnf_gui/__init__.py` | `__version__ = "X.Y.Z"` (the sidebar and self-updater read this) |
| `packaging/dnf-gui.spec` | `Version:` and a new `%changelog` entry |
| `packaging/dnf-gui.metainfo.xml` | New `<release>` entry |
| `CHANGELOG.md` | New version heading |

## Build & Package

- [ ] Build the RPM: `./build-rpm.sh` (writes `dist/DNF-Package-Manager-vX.Y.Z.rpm`)
- [ ] Inspect it: `rpm -qlp dist/DNF-Package-Manager-vX.Y.Z.rpm`
- [ ] Test install and removal: `sudo dnf install ./dist/DNF-Package-Manager-vX.Y.Z.rpm`, then `sudo dnf remove dnf-gui`
- [ ] Test the source install: `sudo ./install.sh`, then `sudo ./install.sh remove`

## Tag & Publish

- [ ] Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"` and `git push origin vX.Y.Z`
- [ ] Create the GitHub release from the tag:
  - Paste the release notes from `CHANGELOG.md`
  - Attach `dist/DNF-Package-Manager-vX.Y.Z.rpm`. The in-app updater looks for a `.rpm` asset and verifies it against the SHA-256 digest GitHub computes on upload, so don't rename or re-upload the file after publishing.
