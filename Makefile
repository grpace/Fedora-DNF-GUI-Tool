# ──────────────────────────────────────────────────────────────
# Fedora DNF GUI Tool — Makefile
# Author: Greg.Tech (https://greg.tech)
# License: GPL-3.0
# ──────────────────────────────────────────────────────────────

PREFIX ?= /opt/dnf-gui
BINDIR ?= /usr/local/bin
DESKTOPDIR ?= /usr/share/applications
ICONDIR ?= /usr/share/icons/hicolor/scalable/apps

PYTHON := python3
APP_NAME := dnf-gui

.PHONY: help install uninstall run dev deps check clean rpm

help: ## Show this help
	@echo ""
	@echo "  DNF Package Manager — Makefile"
	@echo "  ────────────────────────────────────────"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

deps: ## Install system dependencies (PyQt6)
	@echo "Installing dependencies..."
	@$(PYTHON) -c "import PyQt6" 2>/dev/null && echo "PyQt6 already installed" || \
		(sudo dnf install -y python3-pyqt6 2>/dev/null || pip3 install PyQt6)

run: ## Run the application (development mode)
	@PYTHONPATH=src:$$PYTHONPATH $(PYTHON) -m dnf_gui

dev: deps ## Install deps and run in development mode
	@PYTHONPATH=src:$$PYTHONPATH $(PYTHON) -m dnf_gui

install: ## Install system-wide (requires root)
	@echo "Installing to $(PREFIX)..."
	@mkdir -p $(PREFIX)
	@cp -r src/dnf_gui $(PREFIX)/
	@echo '#!/bin/bash' > $(BINDIR)/$(APP_NAME)
	@echo 'export PYTHONPATH="$(PREFIX):$${PYTHONPATH}"' >> $(BINDIR)/$(APP_NAME)
	@echo 'exec $(PYTHON) -m dnf_gui "$$@"' >> $(BINDIR)/$(APP_NAME)
	@chmod +x $(BINDIR)/$(APP_NAME)
	@mkdir -p $(ICONDIR)
	@cp assets/icons/app_icon.svg $(ICONDIR)/$(APP_NAME).svg 2>/dev/null || true
	@sed 's|Exec=.*|Exec=$(BINDIR)/$(APP_NAME)|' assets/dnf-gui.desktop > $(DESKTOPDIR)/$(APP_NAME).desktop
	@update-desktop-database $(DESKTOPDIR) 2>/dev/null || true
	@echo "✅ Installed! Run with: $(APP_NAME)"

uninstall: ## Uninstall (requires root)
	@echo "Uninstalling..."
	@rm -rf $(PREFIX)
	@rm -f $(BINDIR)/$(APP_NAME)
	@rm -f $(DESKTOPDIR)/$(APP_NAME).desktop
	@rm -f $(ICONDIR)/$(APP_NAME).svg
	@update-desktop-database $(DESKTOPDIR) 2>/dev/null || true
	@echo "✅ Uninstalled"

check: ## Run tests
	@PYTHONPATH=src:$$PYTHONPATH $(PYTHON) -m pytest tests/ -v

clean: ## Remove build artifacts
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .pytest_cache/

rpm: ## Build RPM package (requires rpmbuild)
	@echo "Building RPM..."
	@mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	@tar czf ~/rpmbuild/SOURCES/$(APP_NAME)-1.1.0.tar.gz \
		--transform 's,^,$(APP_NAME)-1.1.0/,' \
		src/ assets/ install.sh pyproject.toml requirements.txt LICENSE README.md
	@cp packaging/dnf-gui.spec ~/rpmbuild/SPECS/
	@rpmbuild -bb ~/rpmbuild/SPECS/$(APP_NAME).spec
	@echo "✅ RPM built in ~/rpmbuild/RPMS/"
