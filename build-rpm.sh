#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Fedora DNF GUI Tool — RPM Build Script
# Author: Greg.Tech (https://greg.tech)
# License: GPL-3.0
#
# Usage: ./build-rpm.sh
# Output: ~/rpmbuild/RPMS/noarch/dnf-gui-*.noarch.rpm
#         dist/DNF-Package-Manager-X.Y.Z.rpm (release-ready, user-friendly name)
# ──────────────────────────────────────────────────────────────

set -e

APP_NAME="dnf-gui"
RELEASE_NAME="DNF-Package-Manager"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC_FILE="${SCRIPT_DIR}/packaging/dnf-gui.spec"

# Extract version from spec file
VERSION=$(grep -E '^Version:' "$SPEC_FILE" | awk '{print $2}')

echo "Building ${APP_NAME} v${VERSION}..."
mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

tar czf ~/rpmbuild/SOURCES/${APP_NAME}-${VERSION}.tar.gz \
    --transform "s,^,${APP_NAME}-${VERSION}/," \
    -C "$SCRIPT_DIR" \
    src/ assets/ install.sh pyproject.toml requirements.txt LICENSE README.md CHANGELOG.md RELEASING.md

cp "$SPEC_FILE" ~/rpmbuild/SPECS/
rpmbuild -bb ~/rpmbuild/SPECS/dnf-gui.spec

# Find the built RPM (handles .fc43, .fc40, etc.)
BUILT_RPM=$(ls ~/rpmbuild/RPMS/noarch/${APP_NAME}-${VERSION}-*.noarch.rpm 2>/dev/null | head -1)
if [ -n "$BUILT_RPM" ]; then
    mkdir -p "${SCRIPT_DIR}/dist"
    RELEASE_RPM="${SCRIPT_DIR}/dist/${RELEASE_NAME}-${VERSION}.rpm"
    cp "$BUILT_RPM" "$RELEASE_RPM"
    echo ""
    echo "✅ RPM built:"
    echo "   $BUILT_RPM"
    echo "   $RELEASE_RPM  (for GitHub release)"
else
    echo ""
    echo "✅ RPM built in ~/rpmbuild/RPMS/noarch/"
    ls ~/rpmbuild/RPMS/noarch/${APP_NAME}-*.noarch.rpm 2>/dev/null || true
fi
