#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# Compile-test the driver (and its KUnit module) against several kernel trees
# with extra warnings (W=1) and, if installed, the sparse static checker.
#
#   tools/build-matrix.sh <kernel-tree-or-headers> [...]
#
# Each tree must be configured and prepared (`make modules_prepare`).  The
# sources are copied to a temporary directory so the checkout stays clean.
# Exits non-zero if any build fails or emits a diagnostic.
set -eu

[ $# -ge 1 ] || { echo "usage: $0 <kdir> [<kdir> ...]" >&2; exit 2; }

repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

check=
command -v sparse >/dev/null 2>&1 && check=C=2

status=0
for kdir in "$@"; do
	version=$(make -s -C "$kdir" kernelversion 2>/dev/null || echo "?")
	src="$work/$(basename "$kdir")"
	cp -r "$repo/src" "$src"

	# Trees without Module.symvers (prepared, not built) can't resolve
	# symbols; let modpost warn instead of fail in that case.
	modpost=
	[ -f "$kdir/Module.symvers" ] || modpost=KBUILD_MODPOST_WARN=1

	# Distro kernels (Ubuntu, for one) build with CONFIG_FRAME_WARN=1024;
	# our trees may allow more, so enforce the stricter limit here.
	log="$work/build.log"
	if make -C "$kdir" M="$src" W=1 $check $modpost \
		KCFLAGS=-Wframe-larger-than=1024 \
		CONFIG_MCT_T6_KUNIT_TEST=m modules >"$log" 2>&1; then
		diags=$(grep -E 'warning|error' "$log" |
			grep -vE 'modpost: .* undefined!|unresolved symbol|Module.symvers|You may get|KBUILD_MODPOST_WARN' || true)
	else
		diags="build failed"
	fi

	if [ -n "$diags" ]; then
		echo "FAIL $version ($kdir)"
		grep -E 'warning|error' "$log" | head -40
		status=1
	else
		echo "ok   $version ($kdir)"
	fi
done
exit $status
