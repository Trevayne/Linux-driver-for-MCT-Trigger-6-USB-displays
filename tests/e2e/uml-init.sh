#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# PID 1 inside the UML test kernel (started by run.sh as init=).  The root
# filesystem is the host's, through hostfs, so host binaries just work.
#
# Parameters come from the kernel command line as environment variables:
#   T6_WORK  directory holding mct_t6.ko, mct_t6_test.ko, t6emu, t6drm
#   T6_OUT   output directory (one subdirectory per pass)
#
# Sequence:
#   1. KUnit: insmod mct_t6_test.ko (results land in dmesg as KTAP)
#   2. pass "fence":   t6emu reports frame completion; insmod mct_t6; t6drm
#   3. stop t6emu, which unplugs the device (driver disconnect path)
#   4. pass "nofence": t6emu --no-fence; the driver re-probes; t6drm again
#   5. stop t6emu, rmmod mct_t6, collect dmesg, power off
#
# Every step's outcome is appended to $T6_OUT/init.log; run.sh and
# verify.py read it.  Nothing here may hang forever: every wait is bounded.

export PATH=/usr/sbin:/usr/bin:/sbin:/bin
LOG=$T6_OUT/init.log

log() {
	echo "init: $*"
	echo "$*" >> "$LOG"
}

# Wait up to $1 seconds for the command in $2... to succeed.
wait_for() {
	n=$(($1 * 10))
	shift
	while [ $n -gt 0 ]; do
		"$@" 2>/dev/null && return 0
		sleep 0.1
		n=$((n - 1))
	done
	return 1
}

drm_card_bound() {
	for d in /sys/class/drm/card*/device/driver; do
		[ "$(basename "$(readlink "$d")")" = mct_t6 ] && return 0
	done
	return 1
}

drm_card_gone() {
	! drm_card_bound
}

emu_pid=
start_emu() {
	mkdir -p "$1"
	shift
	"$T6_WORK/t6emu" --outdir "$OUTDIR" "$@" > "$OUTDIR/t6emu.out" 2>&1 &
	emu_pid=$!
	log "t6emu started (pid $emu_pid) $*"
}

stop_emu() {
	[ -n "$emu_pid" ] || return 0
	kill -TERM "$emu_pid"
	n=100
	while kill -0 "$emu_pid" 2>/dev/null && [ $n -gt 0 ]; do
		sleep 0.1
		n=$((n - 1))
	done
	if kill -0 "$emu_pid" 2>/dev/null; then
		log "FAIL t6emu did not exit on SIGTERM"
		kill -KILL "$emu_pid"
	fi
	wait "$emu_pid"
	log "t6emu exited with status $?"
	emu_pid=
}

# One end-to-end pass: emulator, driver binding, client, stats.
run_pass() {
	name=$1
	shift
	OUTDIR=$T6_OUT/$name
	start_emu "$OUTDIR" "$@"
	if [ "$name" = fence ]; then
		insmod "$T6_WORK/mct_t6.ko" && log "insmod mct_t6 ok" ||
			log "FAIL insmod mct_t6"
	fi
	if wait_for 120 drm_card_bound; then
		log "$name: DRM device bound"
		timeout 900 "$T6_WORK/t6drm" --outdir "$OUTDIR" \
			--status "$OUTDIR/emu.status" > "$OUTDIR/t6drm.out" 2>&1
		rc=$?
		cat "$OUTDIR/t6drm.out"
		[ $rc -eq 0 ] && log "$name: t6drm ok" ||
			log "FAIL $name: t6drm exited with status $rc"
	else
		log "FAIL $name: no mct_t6 DRM device after 120 s"
	fi
	found=
	for f in /sys/kernel/debug/mct_t6-*/stats; do
		[ -e "$f" ] || continue
		found=1
		{ echo "# $f"; cat "$f"; } >> "$OUTDIR/stats.txt"
	done
	[ -n "$found" ] || log "FAIL $name: no debugfs stats file"
	stop_emu
	if wait_for 60 drm_card_gone; then
		log "$name: DRM device removed after unplug"
	else
		log "FAIL $name: DRM device still bound 60 s after unplug"
	fi
}

mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t debugfs debugfs /sys/kernel/debug
mkdir -p "$T6_OUT"
: > "$LOG"
log "booted $(uname -r), $(nproc) CPU(s)"

# KUnit runs the suite while the module loads.
if insmod "$T6_WORK/mct_t6_test.ko"; then
	log "kunit: module loaded"
	rmmod mct_t6_test
else
	log "FAIL kunit: insmod mct_t6_test.ko"
fi

run_pass fence
run_pass nofence --no-fence

if rmmod mct_t6; then
	log "rmmod mct_t6 ok"
else
	log "FAIL rmmod mct_t6"
fi

# Let delayed reports (kmemleak-style, workqueue watchdogs) surface.
sleep 2
dmesg > "$T6_OUT/dmesg.txt"
log "done"
sync
echo o > /proc/sysrq-trigger
sleep 10
