# Debugging playbook (learned on real hardware)

Recipes that worked, and the traps hit along the way. Machine-specific
details go in machines.md.

## Session hygiene

- **sudo.** Run `sudo -n true` first. If it fails, ask the user to add a
  NOPASSWD drop-in, or to run the sudo steps themselves. A sudo password the
  user entered in their own terminal doesn't carry over to Claude's shell.
- **Waiting for the user.** Don't ask "tell me when you've unplugged". Start a
  background poll instead (`run_in_background`), which re-invokes Claude when it
  exits, and tell the user what to do. For example:
  `for i in $(seq 1200); do lsusb -d 0711: >/dev/null || break; sleep 0.5; done`.
- **Reloading the module.** The compositor holds the DRM device open, so
  `rmmod` fails while the dock is attached. Reload cycle: user unplugs →
  `rmmod mct_t6` (refcount is 0 once KWin lets go) → `insmod` the new build →
  user replugs. This exercises hot-unplug each time, which is a useful side
  effect. One background script can do the whole cycle, waiting for each event.
- Keep captures and logs in `hw-logs/` inside the repo. Live-USB scratch space
  disappears on reboot.

## Link speed: is it really USB 2?

```sh
lsusb -t                                    # 480M = USB 2, 5000M+ = SuperSpeed
cat /sys/bus/usb/devices/<dev>/version      # bcdUSB: 2.10 on a USB 3 device running at USB 2 speed
for p in /sys/bus/usb/devices/usb*/*-0:1.0/usb*-port*; do
  echo "$(basename $p) peer=$(readlink $p/peer | xargs -r basename) loc=$(cat $p/location) $(cat $p/connect_type)"
done
```

A USB 2 port with no `peer` has no SuperSpeed lane. Match `location` values
across controllers: on Intel, the USB-C ports' SuperSpeed lanes sit on the
Thunderbolt xHCI and may not be linked as peers. A dock whose devices report
`bcdUSB 2.10` but enumerate at 480M is plugged into a USB 2 port (or a USB 2
cable).

## usbmon

```sh
sudo modprobe usbmon
sudo timeout 60 cat /sys/kernel/debug/usb/usbmon/<bus>u > hw-logs/NN-name.usbmon
```

In the text format, field 4 is `<type><dir>:<bus>:<dev>:<ep>`. Setup lines
then carry `s bmRequestType bRequest wValue wIndex wLength`. The data is
truncated to 32 bytes. Filters that helped:

```sh
# control requests to the dock (device 6 on bus 3), by request
awk '$4 ~ /^C[io]:3:006/ && $3=="S"' f.usbmon | awk '{print $6,$7}' | sort | uniq -c
# cursor traffic only (0x04/06 position, 0x05/07 state, 0x10/11 shape)
awk '$4 ~ /^Co:3:0/ && $3=="S" && $6=="40" && ($7=="10"||$7=="11"||$7=="05"||$7=="07")' f.usbmon
# bulk frames and interrupt events
awk '$4 ~ /^Bo:3:006|^Ii:3:006/' f.usbmon
```

The device number changes on every replug: check `lsusb` before filtering.
Bus 3 also carries the dock's Ethernet, webcam and so on, so always filter by
device.

## DRM-side inspection (read-only)

```sh
sudo cat /sys/kernel/debug/dri/<minor>/name          # find our minor ("mct_t6 dev=...")
sudo cat /sys/kernel/debug/dri/<minor>/framebuffer   # every fb, size, refcount, "allocated by"
sudo cat /sys/kernel/debug/dri/<minor>/clients       # who has the device open
sudo cat /sys/kernel/debug/dri/<minor>/state         # atomic state: plane src/crtc rects, fbs
sudo cat /sys/kernel/debug/mct_t6-*/stats
```

KMS debug logging is a state change, so ask first. It is very chatty (i915
too). Record it with `dmesg -w > file &` instead of relying on the ring buffer,
and switch it off afterwards:
`echo 0x4 > /sys/module/drm/parameters/debug` … `echo 0 > …`.

## Bugs found on hardware, and how they showed up

1. **Cursor clipped at screen edges** ("cursor derps out when moving onto the
   screen"). usbmon showed shape headers with widths of 59, 60, 46 and 5 for a
   64x64 KWin cursor. Cause: `new->src` is clipped to the CRTC by
   `drm_atomic_helper_check_plane_state()`. Upload the unclipped
   `src_x/src_y/src_w/src_h` instead. The e2e test never moved a cursor
   partly off-screen *with a shape upload in the same commit*.
2. **Cursor "half and half" when the shape changes.** The chip draws the shown
   slot live while 5×4 KiB control writes (about 10 ms) overwrite it. There are
   slots 0–9 per head (MCT `t6.h`; wValue of 0x05/07 and 0x10/11). MCT's own
   Linux driver only ever uses slot 0, and Windows never uses the hardware
   cursor (captures have no cursor requests). Fix: double-buffer slots 0 and 1.
   Verified: showing slot N replaces the shown slot, and the user confirmed
   the cursor is clean (capture `hw-logs/04-cursor-slots.usbmon`).
3. **`WARNING drm_mode_config.c:578` on unplug: not our bug.** This is 6.19.10
   stable: `drm_file_free()` now skips `drm_fb_release()` when the device has
   been unplugged (commit "drm: Fix use-after-free on framebuffers and
   property blobs when calling drm_dev_unplug"). KWin's fbs stay on its file
   and are freed by `drm_mode_config_cleanup()`, which still WARNs. Tell-tale:
   no `[leaked fb]` lines even with drm.debug=0x4, because 6.19.10 prints only
   fbs that are *not* owned by a file. Every hot-unpluggable DRM driver
   (udl, gud, evdi) hits this.
4. **VGA DDC garbage right after plug-in** (`EDID has corrupt header` dumps).
   It is transient; polling recovers. It is only cosmetic, unless it starts to
   persist.

## Things the emulator (tests/e2e) can't tell you

The chip's real timing (DDC readiness, the time a shape upload takes), live
scanout of cursor buffers, what real compositors do (KWin: 64x64 cursor,
partially off-screen positions, dma-buf imported fbs, Xwayland as the last fd
holder), and kernel-version quirks in the DRM core. When the e2e test passes
but hardware misbehaves, capture usbmon first, then compare the request
sequence with what the emulator accepts.
