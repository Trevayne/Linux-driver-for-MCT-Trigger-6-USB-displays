// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (C) 2026 Gareth Palmer
 *
 * Hardware cursor.
 *
 * The Trigger 6 composites an ARGB cursor over its scanout, as MCT's
 * Windows and Linux drivers use.  Exposing it as a DRM cursor plane means
 * pointer motion costs one small control transfer instead of re-encoding
 * and sending part of a frame, which is what keeps the pointer smooth over
 * a USB 2.0 link.
 *
 * Shape upload: an 8-byte header (type, width, height, pitch) followed by
 * the ARGB8888 pixels, written in chunks of at most 4 KiB with wValue the
 * shape slot (0-9) and wIndex the byte offset of each chunk.
 *
 * The chip draws the shown slot straight from its buffer, so a 64x64 upload
 * (five writes, ~10 ms) into the visible slot shows half old, half new
 * shape.  New shapes therefore go into the other of two slots, which is
 * then shown with a single state request.
 */
#include <linux/slab.h>

#include <drm/drm_atomic.h>
#include <drm/drm_atomic_helper.h>
#include <drm/drm_damage_helper.h>
#include <drm/drm_drv.h>
#include <drm/drm_fourcc.h>
#include <drm/drm_framebuffer.h>
#include <drm/drm_gem_atomic_helper.h>
#include <drm/drm_gem_framebuffer_helper.h>
#include <drm/drm_print.h>

#include "t6_compat.h"
#include "t6_drv.h"

static const u32 t6_cursor_formats[] = {
	DRM_FORMAT_ARGB8888,
};

static const u64 t6_cursor_modifiers[] = {
	DRM_FORMAT_MOD_LINEAR,
	DRM_FORMAT_MOD_INVALID,
};

static u8 t6_req(const struct t6_head *head, u8 head0, u8 head1)
{
	return head->index ? head1 : head0;
}

static int t6_cursor_check(struct drm_plane *plane,
			   struct drm_atomic_state *state)
{
	struct drm_plane_state *new = drm_atomic_get_new_plane_state(state,
								      plane);
	struct drm_crtc_state *crtc_state = NULL;
	int ret;

	if (new->crtc)
		crtc_state = drm_atomic_get_new_crtc_state(state, new->crtc);

	ret = drm_atomic_helper_check_plane_state(new, crtc_state,
						  DRM_PLANE_NO_SCALING,
						  DRM_PLANE_NO_SCALING,
						  true, true);
	if (ret || !new->visible)
		return ret;

	if (new->src_w >> 16 > T6_CURSOR_MAX_SIZE ||
	    new->src_h >> 16 > T6_CURSOR_MAX_SIZE)
		return -EINVAL;
	return 0;
}

static int t6_cursor_upload(struct t6_head *head, u8 slot,
			    struct drm_plane_state *new)
{
	struct drm_shadow_plane_state *shadow = to_drm_shadow_plane_state(new);
	struct drm_framebuffer *fb = new->fb;
	/*
	 * Upload the whole, unclipped cursor: new->src is clipped to the
	 * CRTC, so near a screen edge it holds only a slice of the shape, and
	 * that slice would stay on the chip after the pointer moves back.
	 * The chip clips by position itself (negative coordinates included).
	 */
	unsigned int w = new->src_w >> 16, h = new->src_h >> 16;
	unsigned int x0 = new->src_x >> 16, y0 = new->src_y >> 16;
	size_t total = T6_CURSOR_HDR_LEN + (size_t)w * h * 4, off;
	const u8 *src;
	unsigned int y;
	u8 *buf;
	int ret;

	buf = kmalloc(total, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	t6_cursor_hdr_encode(w, h, buf);
	ret = drm_gem_fb_begin_cpu_access(fb, DMA_FROM_DEVICE);
	if (ret)
		goto out;
	src = (const u8 *)shadow->data[0].vaddr + y0 * fb->pitches[0] + x0 * 4;
	for (y = 0; y < h; y++)
		memcpy(buf + T6_CURSOR_HDR_LEN + y * w * 4,
		       src + y * fb->pitches[0], w * 4);
	drm_gem_fb_end_cpu_access(fb, DMA_FROM_DEVICE);

	for (off = 0; off < total && !ret; off += T6_CURSOR_CHUNK)
		ret = t6_ctrl_out(head->t6,
				  t6_req(head, T6_REQ_SET_CURSOR1_SHAPE,
					 T6_REQ_SET_CURSOR2_SHAPE),
				  slot, off, buf + off,
				  min_t(size_t, T6_CURSOR_CHUNK, total - off));
out:
	kfree(buf);
	return ret;
}

static int t6_cursor_show(struct t6_head *head, u8 slot, bool visible)
{
	return t6_ctrl_out(head->t6, t6_req(head, T6_REQ_SET_CURSOR1_STATE,
					    T6_REQ_SET_CURSOR2_STATE),
			   slot, visible, NULL, 0);
}

static void t6_cursor_update(struct drm_plane *plane,
			     struct drm_atomic_state *state)
{
	struct drm_plane_state *new = drm_atomic_get_new_plane_state(state,
								      plane);
	struct drm_plane_state *old = drm_atomic_get_old_plane_state(state,
								      plane);
	struct t6_head *head = container_of(plane, struct t6_head, cursor);
	struct t6_cursor_state *cs = &head->cursor_state;
	struct drm_rect damage;
	u8 slot = cs->slot;
	int idx, ret = 0;

	if (!drm_dev_enter(plane->dev, &idx))
		return;

	if (!new->visible || !new->fb) {
		if (cs->visible)
			ret = t6_cursor_show(head, cs->slot, false);
		cs->visible = false;
		goto out;
	}

	/*
	 * The shape changes only with a new framebuffer or explicit damage.
	 * (No damage clips means "everything" to the damage helpers, which
	 * would re-upload the shape on every move.)
	 */
	if (!cs->uploaded || new->fb != old->fb ||
	    (drm_plane_get_damage_clips_count(new) &&
	     drm_atomic_helper_damage_merged(old, new, &damage))) {
		/* Into the hidden slot; the shown one stays intact meanwhile. */
		if (cs->uploaded)
			slot ^= 1;
		ret = t6_cursor_upload(head, slot, new);
		cs->uploaded = !ret;
		if (ret)
			goto out;
	}

	ret = t6_ctrl_out(head->t6, t6_req(head, T6_REQ_SET_CURSOR1_POS,
					   T6_REQ_SET_CURSOR2_POS),
			  t6_cursor_coord(new->crtc_x),
			  t6_cursor_coord(new->crtc_y), NULL, 0);
	if (!ret && (!cs->visible || slot != cs->slot)) {
		ret = t6_cursor_show(head, slot, true);
		cs->visible = !ret;
		if (!ret)
			cs->slot = slot;
	}
out:
	if (ret)
		drm_err_ratelimited(plane->dev, "head %u: cursor update failed: %d\n",
				    head->index, ret);
	drm_dev_exit(idx);
}

static const struct drm_plane_helper_funcs t6_cursor_helper_funcs = {
	DRM_GEM_SHADOW_PLANE_HELPER_FUNCS,
	.atomic_check = t6_cursor_check,
	.atomic_update = t6_cursor_update,
};

static const struct drm_plane_funcs t6_cursor_funcs = {
	.update_plane = drm_atomic_helper_update_plane,
	.disable_plane = drm_atomic_helper_disable_plane,
	.destroy = drm_plane_cleanup,
	DRM_GEM_SHADOW_PLANE_FUNCS,
};

int t6_cursor_plane_init(struct t6_head *head)
{
	int ret;

	ret = drm_universal_plane_init(&head->t6->drm, &head->cursor, 0,
				       &t6_cursor_funcs, t6_cursor_formats,
				       ARRAY_SIZE(t6_cursor_formats),
				       t6_cursor_modifiers,
				       DRM_PLANE_TYPE_CURSOR, NULL);
	if (ret)
		return ret;
	drm_plane_helper_add(&head->cursor, &t6_cursor_helper_funcs);
	drm_plane_enable_fb_damage_clips(&head->cursor);
	return 0;
}
