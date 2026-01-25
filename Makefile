.PHONY: all submodules micro_init build_firmware clean_frozen_py rebuild_mpy_cross bump_version release
SHELL := /bin/bash

# Detect Python command
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
ifeq ($(PYTHON),)
$(error Python is not installed. Please install Python 3)
endif

# Default value for FW_TYPE
FW_TYPE ?= normal
# Check that FW_TYPE is either normal or minimal
ifneq ($(FW_TYPE),normal)
ifneq ($(FW_TYPE),minimal)
$(error FW_TYPE must be either 'normal' or 'minimal')
endif
endif

all: build_firmware

build_firmware: dist/firmware_$(FW_TYPE).bin

build_and_deploy: build_firmware deploy

# init own submopdules before micropython init
submodules:
	git submodule update --init
	pushd micropython/ports/esp32 && \
	git submodule update --init 'user-cmodules/ucrypto' &&\
	popd
	pushd micropython && \
	git submodule update --init --depth 1 && \
	popd


set_environ.sh:
	@cp set_environ.example set_environ.sh

micro_init: micro_init.stamp
	@echo "micro_init has been completed!"

micro_init.stamp: submodules set_environ.sh
	FW_TYPE=$(FW_TYPE) source ./set_environ.sh && \
	pushd micropython && \
	ci_esp32_idf_setup && \
	ci_esp32_build_common && \
	popd
	touch micro_init.stamp

dist/firmware_$(FW_TYPE).bin: micro_init
	@echo "Building firmware type: $(FW_TYPE)"
	git rev-parse --short HEAD > frozen_fs/BUILD
	PYTHONPATH=libs/freezefs $(PYTHON) -m freezefs ./frozen_fs frozen_firmware/modules/frozen_fs.py --target "/readonly_fs"  --compress
	FW_TYPE=$(FW_TYPE) source ./set_environ.sh && \
	pushd micropython && \
	ci_esp32_idf_setup && \
	ci_esp32_build_common && \
	make ${MAKEOPTS} -C ports/esp32 && \
	popd && \
	cp micropython/ports/esp32/build-$$BOARD-$$BOARD_VARIANT/firmware.bin dist/firmware_$(FW_TYPE).bin

deploy: 
	FW_TYPE=$(FW_TYPE) source ./set_environ.sh
	@if [ -z "$$PORT" ]; then \
		esptool --chip esp32s3 -b 460800 --before=default-reset --after=hard-reset write-flash --flash-size detect 0x0 dist/firmware_$(FW_TYPE).bin; \
	else \
		esptool --chip esp32s3 -p $$PORT -b 460800 --before=default-reset --after=hard-reset write-flash --flash-size detect 0x0 dist/firmware_$(FW_TYPE).bin; \
	fi

repl_with_firmware_dir:
	@echo "Starting REPL with firmware directory mounted..."
	FW_TYPE=$(FW_TYPE) source ./set_environ.sh
	@if [ -z "$$PORT" ]; then \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 u0 mount -l firmware; \
	else \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 connect $$PORT mount -l firmware; \
	fi

dev_exec:
	@echo "Executing command with firmware directory mounted..."
	@if [ -z "$(CMD)" ]; then \
		echo "Error: No command specified"; \
		echo "Usage: make dev_exec CMD='<command>'"; \
		echo "Example: make dev_exec CMD='load_app(\"badge.option_screen\", \"OptionScreen\", with_espnow=True, with_sta=True)'"; \
		exit 1; \
	fi
	FW_TYPE=$(FW_TYPE) source ./set_environ.sh
	@if [ -z "$$PORT" ]; then \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 u0 mount -l firmware exec '$(CMD)'; \
	else \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 connect $$PORT mount -l firmware exec '$(CMD)'; \
	fi

         
clean_frozen_py:
	rm -rf ports/esp32/build-ESP32_GENERIC_S3-DEVKITW2/frozen_mpy

rebuild_mpy_cross:
	pushd micropython/mpy-cross && \
	make clean && \
	make && \
	popd

clean: 
	rm -fr micropython/ports/esp32/build-ESP32_GENERIC_S3-DEVKITW2

# Version bumping (BUMP_TYPE can be: major, minor, patch)
BUMP_TYPE ?=
bump_version:
	@if [ -z "$(BUMP_TYPE)" ]; then \
		echo "Error: BUMP_TYPE not specified"; \
		echo ""; \
		echo "Usage: make bump_version BUMP_TYPE=<level>"; \
		echo ""; \
		echo "Bump levels:"; \
		echo "  patch  - Bug fixes (e.g., v0.0.1 → v0.0.2)"; \
		echo "  minor  - New features (e.g., v0.1.0 → v0.2.0)"; \
		echo "  major  - Breaking changes (e.g., v1.0.0 → v2.0.0)"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make bump_version BUMP_TYPE=patch"; \
		echo "  make bump_version BUMP_TYPE=minor"; \
		echo "  make bump_version BUMP_TYPE=major"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Bumping $(BUMP_TYPE) version..."
	@./scripts/bump_version.sh $(BUMP_TYPE)
	@NEW_VERSION=$$(cat frozen_fs/VERSION) && \
	echo "Committing version $$NEW_VERSION..." && \
	git add frozen_fs/VERSION && \
	git commit -m "Release $$NEW_VERSION" && \
	echo "Creating tag: $$NEW_VERSION" && \
	git tag -a "$$NEW_VERSION" -m "Release $$NEW_VERSION" && \
	echo "✅ Version bumped and tagged: $$NEW_VERSION"

# Release process: bump version, commit, tag, and build firmware
# Usage: make release BUMP_TYPE=<level>
# Note: Tags are LOCAL until you push. Use 'git push origin main --tags' to publish.
release: bump_version
	@echo "=== Starting Release Build ==="
	@NEW_VERSION=$$(cat frozen_fs/VERSION) && \
	echo "Building firmware for $$NEW_VERSION..." && \
	$(MAKE) clean && \
	$(MAKE) build_firmware FW_TYPE=normal && \
	echo "" && \
	echo "=== Release Complete ===" && \
	echo "Version: $$NEW_VERSION" && \
	echo "Artifacts:" && \
	ls -lh dist/ && \
	echo "" && \
	echo "To publish this release to GitHub:" && \
	echo "  git push origin main --tags" && \
	echo "" && \
	echo "To undo this release (if testing):" && \
	echo "  git tag -d $$NEW_VERSION" && \
	echo "  git reset --hard HEAD~1"

clear_hw_test_status:
	@echo "Removing .hw_tested_in_build from badge..."
	@if [ -z "$$PORT" ]; then \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 u0 rm :/.hw_tested_in_build; \
	else \
		$(PYTHON) micropython/tools/mpremote/mpremote.py baud 460800 connect $$PORT rm :/.hw_tested_in_build; \
	fi