---
name: kernel-api-compat
description: How to handle and verify Linux kernel API differences for mct_t6 (src/t6_compat.h). Use when a build fails on one kernel version, when adding a new kernel API call, or when a new kernel release comes out.
---

# Kernel API compatibility

All version-dependent code lives in `src/t6_compat.h`. Use `LINUX_VERSION_CODE`,
not `__has_include`: sparse 0.6.4 can't parse the latter.

## Find the exact release an API changed in

Don't guess. Fetch the header for each release from kernel.org and grep:

```sh
get(){ curl -sfL "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/$1?h=$2"; }
for v in v6.12 v6.13 v6.14; do echo "$v $(get include/linux/hrtimer.h $v | grep -c 'void hrtimer_setup(')"; done
```

Also compare the in-tree `drivers/gpu/drm/gud` (USB display, closest
relative), `udl` and `vkms` across versions: they show the idiomatic usage for
each era.

## Known cutoffs (all verified this way)

| Change | Version | Handling |
|---|---|---|
| `drm_edid_connector_update()` stops adding modes; `drm_edid_connector_add_modes()` added | 6.3 | `t6_edid_connector_update()` |
| `drm_fbdev_generic_setup()` header `drm_fbdev_generic.h` | 6.2 | fbdev block |
| `drm_fbdev_shmem_setup()` | 6.11 | fbdev block |
| `drm_client_setup()` + `DRM_FBDEV_SHMEM_DRIVER_OPS` (`drm/drm_client_setup.h`) | 6.13 | fbdev block |
| `drm_client_setup.h` moved to `drm/clients/` | 6.14 | fbdev block |
| `usb_driver.shutdown` | 6.11 | `T6_HAVE_USB_SHUTDOWN` |
| `hrtimer_setup()` (`hrtimer_init()` later removed) | 6.13 | `t6_hrtimer_setup()` |
| `drm_driver.date` removed | 6.14 | `T6_DRIVER_DATE` |
| connector `.mode_valid` takes a const mode | 6.15 | `T6_CONNECTOR_MODE` |
| `drm_dev_set_dma_dev()`; `DRM_GEM_SHMEM_DRIVER_OPS` sets `gem_prime_import` | 6.16 | `T6_HAVE_DRM_DMA_DEV`; older kernels wrap `gem_prime_import` like gud did |
| `<linux/unaligned.h>` (was `<asm/unaligned.h>`) | 6.12 | `t6_types.h` |
| `struct drm_atomic_state` renamed to `struct drm_atomic_commit`, no alias | 7.2 | `#define drm_atomic_state drm_atomic_commit` |
| `KUNIT_EXPECT_MEMEQ` | 6.2 | avoided: use `memcmp` |
| `drm_warn_ratelimited` | does not exist | use `dev_warn_ratelimited` |

## When a new kernel is released

1. Download and prepare it (see the `kernel-build-env` skill), then run
   `tools/build-matrix.sh` on it.
2. For each failure, find the commit and the release with the fetch-and-grep
   loop above. Add a shim to `t6_compat.h` with a comment naming the version,
   and add a row to the table above.
3. Re-run the full matrix: a shim must not break older kernels.
