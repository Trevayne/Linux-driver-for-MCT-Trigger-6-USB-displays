# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# Out-of-tree build of the mct_t6 DRM driver.
#
#   make                 build mct_t6.ko against the running kernel
#   make KDIR=<path>     build against another kernel tree/headers
#   make check           host unit tests (needs python3 with Pillow + numpy)
#   make install         install the module (normally done by DKMS instead)
#   make clean
#
# Releases (see tools/release.sh):
#   make version                   print the version (from dkms.conf)
#   make release-check             check dkms.conf, PKGBUILD and docs agree
#   make release RELEASE=x.y.z     bump the version, commit and tag vx.y.z
#                                  (no push; pushing the tag starts CI)
#   make dist                      source tarball of HEAD: mct-t6-<version>.tar.gz

KDIR    ?= /lib/modules/$(shell uname -r)/build
PYTHON  ?= python3
SRC     := $(CURDIR)/src
VERSION := $(shell sed -n 's/^PACKAGE_VERSION="\(.*\)"$$/\1/p' dkms.conf)

.PHONY: all modules check install clean version release-check release dist
all: modules

modules:
	$(MAKE) -C $(KDIR) M=$(SRC) modules

check:
	$(MAKE) -C tests/host check PYTHON="$(PYTHON)"

install:
	$(MAKE) -C $(KDIR) M=$(SRC) modules_install

clean:
	$(MAKE) -C $(KDIR) M=$(SRC) clean 2>/dev/null || true
	$(MAKE) -C tests/host clean
	rm -f mct-t6-*.tar.gz

version:
	@echo $(VERSION)

release-check:
	tools/release.sh check

release:
	@test -n "$(RELEASE)" || { echo "usage: make release RELEASE=x.y.z" >&2; exit 2; }
	tools/release.sh tag $(RELEASE)

dist:
	git archive --format=tar.gz --prefix=mct-t6-$(VERSION)/ \
		-o mct-t6-$(VERSION).tar.gz HEAD
