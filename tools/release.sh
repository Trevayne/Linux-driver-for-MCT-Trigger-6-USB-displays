#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# Version and release helper.  dkms.conf's PACKAGE_VERSION is the single
# source of truth; the Arch PKGBUILD and the install commands in the docs
# must agree with it.
#
#   tools/release.sh version          print the current version
#   tools/release.sh check [<tag>]    check every file agrees on the version
#                                     (and, if given, that <tag> is v<version>)
#   tools/release.sh bump <x.y.z>     rewrite the version in every file
#   tools/release.sh tag <x.y.z>      bump, commit "Release v<x.y.z>" and create
#                                     the annotated tag v<x.y.z>.  Does not push.
#
# Normally run through the Makefile: `make version`, `make release-check`,
# `make release RELEASE=x.y.z`.
set -eu

repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"

DKMS=dkms.conf
PKGBUILD=packaging/arch/PKGBUILD
DOCS="README.md docs/INSTALL.md"

die() { echo "release: $*" >&2; exit 1; }

current() {
	sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "$DKMS"
}

valid() {
	echo "$1" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'
}

# Escape dots for use in a sed/grep regex.
re() {
	printf '%s' "$1" | sed 's/\./\\./g'
}

check() {
	ver=$(current)
	[ -n "$ver" ] || die "no PACKAGE_VERSION in $DKMS"
	valid "$ver" || die "$DKMS version '$ver' is not x.y.z"
	status=0

	pkgver=$(sed -n 's/^pkgver=//p' "$PKGBUILD")
	if [ "$pkgver" != "$ver" ]; then
		echo "$PKGBUILD: pkgver=$pkgver, expected $ver" >&2
		status=1
	fi

	# Every mct-t6-<ver> / mct-t6/<ver> in the docs must be the current one.
	for f in $DOCS; do
		stale=$(grep -nEo 'mct-t6[-/][0-9]+\.[0-9]+\.[0-9]+' "$f" |
			grep -vE "[-/]$(re "$ver")\$" || true)
		if [ -n "$stale" ]; then
			echo "$f: stale version references (expected $ver):" >&2
			echo "$stale" | sed 's/^/  /' >&2
			status=1
		fi
	done

	if [ $# -ge 1 ] && [ "$1" != "v$ver" ]; then
		echo "tag $1 does not match $DKMS version $ver (expected v$ver)" >&2
		status=1
	fi

	[ $status -eq 0 ] || die "version check failed"
	echo "version $ver: consistent"
}

bump() {
	new=$1
	valid "$new" || die "'$new' is not a version of the form x.y.z"
	old=$(current)
	[ -n "$old" ] || die "no PACKAGE_VERSION in $DKMS"

	sed -i "s/^PACKAGE_VERSION=\".*\"$/PACKAGE_VERSION=\"$new\"/" "$DKMS"
	sed -i -e "s/^pkgver=.*/pkgver=$new/" -e "s/^pkgrel=.*/pkgrel=1/" \
		"$PKGBUILD"
	for f in $DOCS; do
		sed -i -E "s#mct-t6([-/])$(re "$old")#mct-t6\\1$new#g" "$f"
	done
	echo "version $old -> $new"
}

tag() {
	new=$1
	valid "$new" || die "'$new' is not a version of the form x.y.z"
	git rev-parse --git-dir >/dev/null 2>&1 || die "not a git checkout"
	[ -z "$(git status --porcelain)" ] ||
		die "working tree has uncommitted changes; commit or stash them first"
	! git rev-parse -q --verify "refs/tags/v$new" >/dev/null ||
		die "tag v$new already exists"

	old=$(current)
	if [ "$old" != "$new" ]; then
		# Refuse to go backwards.
		highest=$(printf '%s\n%s\n' "$old" "$new" | sort -V | tail -n1)
		[ "$highest" = "$new" ] || die "$new is older than the current $old"
		bump "$new"
		check
		git add "$DKMS" "$PKGBUILD" $DOCS
		git commit -q -m "Release v$new"
	else
		check
	fi

	git tag -a "v$new" -m "mct_t6 v$new"
	branch=$(git symbolic-ref --short -q HEAD || echo HEAD)
	echo "tagged v$new on $branch ($(git rev-parse --short HEAD))"
	echo "push it to start the release build:"
	echo "  git push --atomic origin $branch v$new"
}

cmd=${1:-}
[ $# -gt 0 ] && shift
case $cmd in
version) current ;;
check) check "$@" ;;
bump) [ $# -eq 1 ] || die "usage: $0 bump <x.y.z>"; bump "$1" ;;
tag) [ $# -eq 1 ] || die "usage: $0 tag <x.y.z>"; tag "$1" ;;
*) sed -n '5,17s/^# \{0,1\}//p' "$0" >&2; exit 2 ;;
esac
