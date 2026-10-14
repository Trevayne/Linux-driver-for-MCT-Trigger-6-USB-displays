/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Copyright (C) 2026 Gareth Palmer
 *
 * Kernel API differences between the supported kernels (6.1 .. 7.x).
 *
 * The driver is built out of tree (DKMS) against whatever kernel a distro
 * ships, from Debian 12 (6.1) to Arch (latest).  Every version-dependent
 * construct lives here so the rest of the code reads like ordinary in-tree
 * DRM code.  Each version below was checked against that release's headers.
 */
#ifndef T6_COMPAT_H
#define T6_COMPAT_H

#include <linux/hrtimer.h>
#include <linux/version.h>

#include <drm/drm_edid.h>
#include <drm/drm_drv.h>
#include <drm/drm_gem_shmem_helper.h>

/* --- Atomic modesetting ------------------------------------------------- */

/*
 * 7.2 renamed struct drm_atomic_state to struct drm_atomic_commit, without a
 * compatibility alias.  Map the old name onto the new one so the driver can
 * use the name every other kernel version knows.
 */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(7, 2, 0)
#define drm_atomic_state drm_atomic_commit
#endif

/* --- fbdev emulation ---------------------------------------------------- */

/*
 * The fbdev (console) client was set up with drm_fbdev_generic_setup()
 * (6.1-6.10, header moved in 6.2), drm_fbdev_shmem_setup() (6.11, 6.12) and
 * since 6.13 with drm_client_setup() plus a driver ops macro (header moved
 * in 6.14).
 */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 13, 0)
#include <drm/drm_fbdev_shmem.h>
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 14, 0)
#include <drm/clients/drm_client_setup.h>
#else
#include <drm/drm_client_setup.h>
#endif
#define T6_FBDEV_DRIVER_OPS DRM_FBDEV_SHMEM_DRIVER_OPS,
static inline void t6_fbdev_setup(struct drm_device *drm)
{
	drm_client_setup(drm, NULL);
}
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(6, 11, 0)
#include <drm/drm_fbdev_shmem.h>
#define T6_FBDEV_DRIVER_OPS
static inline void t6_fbdev_setup(struct drm_device *drm)
{
	drm_fbdev_shmem_setup(drm, 0);
}
#else
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 2, 0)
#include <drm/drm_fbdev_generic.h>
#else
#include <drm/drm_fb_helper.h>
#endif
#define T6_FBDEV_DRIVER_OPS
static inline void t6_fbdev_setup(struct drm_device *drm)
{
	drm_fbdev_generic_setup(drm, 0);
}
#endif

/* --- struct drm_driver -------------------------------------------------- */

/* The .date field was removed in 6.14. */
#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 14, 0)
#define T6_DRIVER_DATE .date = "20261014",
#else
#define T6_DRIVER_DATE
#endif

/*
 * dma-buf import needs the USB host controller as DMA device.  6.16 added
 * drm_dev_set_dma_dev(); before that, drivers wrapped gem_prime_import (as
 * the in-tree gud driver did).
 */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 16, 0)
#define T6_HAVE_DRM_DMA_DEV 1
#endif

/* The connector .mode_valid hook takes a const mode since 6.15. */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 15, 0)
#define T6_CONNECTOR_MODE const struct drm_display_mode
#else
#define T6_CONNECTOR_MODE struct drm_display_mode
#endif

/* struct usb_driver gained a .shutdown hook in 6.11. */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 11, 0)
#define T6_HAVE_USB_SHUTDOWN 1
#endif

/* --- EDID --------------------------------------------------------------- */

/*
 * Before 6.3, drm_edid_connector_update() also added the EDID modes; since
 * then that is a separate drm_edid_connector_add_modes() call.
 */
static inline int t6_edid_connector_update(struct drm_connector *connector,
					   const struct drm_edid *drm_edid)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 3, 0)
	drm_edid_connector_update(connector, drm_edid);
	return drm_edid_connector_add_modes(connector);
#else
	return drm_edid_connector_update(connector, drm_edid);
#endif
}

/* --- hrtimer ------------------------------------------------------------ */

static inline void t6_hrtimer_setup(struct hrtimer *timer,
				    enum hrtimer_restart (*fn)(struct hrtimer *))
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 13, 0)
	hrtimer_setup(timer, fn, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
#else
	hrtimer_init(timer, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
	timer->function = fn;
#endif
}

#endif /* T6_COMPAT_H */
