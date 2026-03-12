# Release Checklist

Use this checklist when preparing a new release of Fedora DNF GUI Tool.

## Pre-Release

- [ ] Install test deps: `pip install pytest` (or `dnf install python3-pytest`)
- [ ] Run tests: `PYTHONPATH=src pytest tests/ -v`
- [ ] Test the app: `PYTHONPATH=src python3 -m dnf_gui` — verify all pages and features work
- [ ] Update version in all locations (see below)
- [ ] Update `CHANGELOG.md` with new version and changes
- [ ] Update `dnf-gui.spec` changelog section
- [ ] Commit all changes with message: `Release vX.Y.Z`

## Version Locations

Update the version number in these files:

| File | Location |
|------|----------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/dnf_gui/__init__.py` | `__version__ = "X.Y.Z"` |
| `src/dnf_gui/app.py` | `__version__` (if present) |
| `src/dnf_gui/ui/sidebar.py` | `version_label` text |
| `packaging/dnf-gui.spec` | `Version:` and `%changelog` |
| `README.md` | Version badge (optional) |

## Build & Package

- [ ] Build RPM: `./build-rpm.sh`
- [ ] Verify RPM: `rpm -qlp ~/rpmbuild/RPMS/noarch/dnf-gui-*.rpm`
- [ ] Test install: `sudo dnf install ~/rpmbuild/RPMS/noarch/dnf-gui-*.rpm`
- [ ] Test uninstall: `sudo dnf remove dnf-gui`
- [ ] Test `install.sh`: `sudo ./install.sh` then `sudo ./install.sh remove`

## Git Tag & Release

- [ ] Create tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Create GitHub release with:
  - Release notes from CHANGELOG
  - Attach `dist/DNF-Package-Manager-vX.Y.Z.rpm` (user-friendly filename)
  - Attach source tarball if desired

## Post-Release

- [ ] Bump version to next dev (e.g. `1.2.0-dev`) if using dev versions
- [ ] Announce on Fedora forums / Reddit / etc. (optional)
