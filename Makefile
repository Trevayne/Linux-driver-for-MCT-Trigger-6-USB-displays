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

KDIR    ?= /lib/modules/$(shell uname -r)/build
PYTHON  ?= python3
SRC     := $(CURDIR)/src

.PHONY: all modules check install clean
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
