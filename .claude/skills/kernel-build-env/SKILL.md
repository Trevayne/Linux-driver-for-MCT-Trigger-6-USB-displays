---
name: kernel-build-env
description: Set up kernel source trees and build tools without sudo (WSL/Ubuntu) to compile-test mct_t6 against kernels 6.1–7.x. Use before running tools/build-matrix.sh or building a UML kernel for tests/e2e.
---

# Kernel build environment without root

The WSL kernel's headers are a stub, so build against real upstream trees.

## 1. Tools (flex, bison, libelf, sparse) without sudo

```sh
P=<scratch>/prefix; mkdir -p <scratch>/debs $P && cd <scratch>/debs
apt-get download flex bison m4 libfl2 libfl-dev libelf-dev zlib1g-dev libzstd-dev libssl-dev sparse
for f in *.deb; do dpkg-deb -x "$f" $P; done
L=$P/usr/lib/x86_64-linux-gnu
# -dev symlinks point at runtime libs that live in /usr/lib, not the prefix:
for so in libelf.so.1 libzstd.so.1 libssl.so.3 libcrypto.so.3; do ln -sf /usr/lib/x86_64-linux-gnu/$so $L/$so; done
ln -sf /usr/lib/x86_64-linux-gnu/libz.so.1 $L/libz.so.1.3
ln -sf /usr/lib/x86_64-linux-gnu/libzstd.so.1 $L/libzstd.so.1.5.5
cat > <scratch>/buildenv.sh <<EOF
export PATH=$P/usr/bin:\$PATH BISON_PKGDATADIR=$P/usr/share/bison M4=$P/usr/bin/m4
export C_INCLUDE_PATH=$P/usr/include:$P/usr/include/x86_64-linux-gnu LIBRARY_PATH=$L
export HOSTCFLAGS="-I$P/usr/include -I$P/usr/include/x86_64-linux-gnu" HOSTLDFLAGS="-L$L"
EOF
```

Source `buildenv.sh` before every kernel `make`.

## 2. Trees

Current versions are listed at https://www.kernel.org/releases.json. The
supported matrix is 6.1 (Debian 12), 6.12 (Debian 13), 6.18 LTS, and latest
stable (Arch).

```sh
curl -sfLO https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.NNN.tar.xz && tar xf ...
cd linux-X && make x86_64_defconfig
./scripts/config -e DRM -m DRM_GUD -e USB -e DEBUG_FS -e DRM_FBDEV_EMULATION -d WERROR \
  -d DEBUG_INFO_BTF -e DEBUG_INFO_NONE -d MODULE_SIG -d SYSTEM_TRUSTED_KEYRING
make olddefconfig && make -j$(nproc) modules_prepare   # or a full build for Module.symvers
```

- `DRM_GUD=m` exists to pull in the hidden `DRM_GEM_SHMEM_HELPER` and
  `DRM_KMS_HELPER` symbols.
- A full build (~2 GB with DEBUG_INFO_NONE) gives `Module.symvers`, so modpost
  checks imports. Without it, check by hand: every `nm -u mct_t6.ko` symbol
  needs an `EXPORT_SYMBOL*` in the tree, and watch for `_NS` exports. The only
  expected misses are macro-generated `_dev_err/_dev_info/_dev_warn/param_ops_uint`.
- An in-tree build makes the tree unusable for `O=` builds. Use a separate
  extraction for UML.
- Disk is tight on this machine: check `df -h ~` before extracting more trees.

## 3. Compile test

```sh
. <scratch>/buildenv.sh
tools/build-matrix.sh <tree-6.1> <tree-6.12> <tree-6.18> <tree-latest>
```

The script copies `src/` to a temp dir (keeps the repo clean), builds with
`W=1`, sparse if it's on PATH, and the KUnit module
(`CONFIG_MCT_T6_KUNIT_TEST=m`), and fails on any diagnostic.
