#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# Prepare a Fedora session (typically a live USB) to build, test and debug
# mct_t6 on real hardware.  Safe to re-run.  Run as your normal user; it uses
# sudo for dnf only.  It does NOT load the driver.
#
# A live USB keeps installed packages in RAM, so this must be re-run after
# every boot.
set -euo pipefail

kver=$(uname -r)
say() { printf '\n== %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

say "Kernel $kver"

# --- Packages ----------------------------------------------------------------

# Required to build the module and run the host tests.
required=(gcc make elfutils-libelf-devel git libasan libubsan python3-pillow python3-numpy)
# Useful for bring-up and debugging; failures are not fatal.
optional=(usbutils drm-utils wireshark-cli sparse mokutil)

say "Installing build tools"
sudo dnf install -y "${required[@]}"
for p in "${optional[@]}"; do
	sudo dnf install -y "$p" >/dev/null 2>&1 || warn "optional package $p not installed"
done

# --- Headers for the *running* kernel ----------------------------------------

# The live image runs the kernel it was released with; the "fedora" repo
# keeps that version's kernel-devel, but "updates" only has newer ones, so ask
# for the exact version.  Fall back to Fedora's build system (koji).
say "Installing kernel-devel-$kver"
if [ ! -e "/lib/modules/$kver/build/Makefile" ]; then
	if ! sudo dnf install -y "kernel-devel-$kver"; then
		ver=${kver%%-*}
		rel=${kver#*-}; rel=${rel%.*}
		arch=${kver##*.}
		url="https://kojipkgs.fedoraproject.org/packages/kernel/$ver/$rel/$arch/kernel-devel-$kver.rpm"
		warn "dnf has no kernel-devel-$kver; trying $url"
		sudo dnf install -y "$url"
	fi
fi
[ -e "/lib/modules/$kver/build/Makefile" ] || { echo "kernel headers still missing" >&2; exit 1; }

# --- Build and unit-test ------------------------------------------------------

repo=$(cd "$(dirname "$0")/.." && pwd)
say "Building the module"
make -C "$repo"
say "Host unit tests"
make -C "$repo" check

# --- Things that would stop the module loading ------------------------------

say "Pre-flight checks"
if command -v mokutil >/dev/null && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
	cat <<'EOF'
Secure Boot is ENABLED: the kernel will refuse the unsigned module
("Key was rejected by service").  For testing, the simplest fix is to
disable Secure Boot in the firmware setup and boot the live USB again.
(Signing with an enrolled MOK also works, but needs a reboot into the MOK
manager, and the key must be kept somewhere that survives a live session.)
EOF
else
	echo "Secure Boot: not enforcing (or mokutil unavailable)"
fi

if lsusb -d 0711: 2>/dev/null | grep -q .; then
	echo "Trigger 6 present:"
	lsusb -d 0711:
	echo "USB topology (480M = USB 2.0, 5000M+ = SuperSpeed):"
	lsusb -t
else
	warn "no 0711:xxxx device found: is the dock plugged in?"
fi

cat <<EOF

Ready.  Next (see docs/TESTING.md "Hardware bring-up checklist"):
  sudo insmod $repo/src/mct_t6.ko && sudo dmesg | grep -i mct_t6
EOF
