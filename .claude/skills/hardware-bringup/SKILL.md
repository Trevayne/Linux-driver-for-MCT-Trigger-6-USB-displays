---
name: hardware-bringup
description: Step-by-step bring-up and debugging of mct_t6 on a real Trigger 6 dock on a Linux machine (load, discovery, first picture, desktop, hot-plug, throughput, usbmon captures). Use when testing on hardware or when the dock misbehaves.
---

# Hardware bring-up

Confirm with the user before any state-changing step (loading modules,
suspending, writing sysfs). The full checklist is in docs/TESTING.md,
"Hardware bring-up checklist". Follow it in order: each step isolates one
layer.

## First, on a fresh (live) Fedora session

Run `tools/fedora-live-setup.sh`. It installs gcc and the matching
kernel-devel, builds and unit-tests the module, and warns about Secure Boot,
which blocks the unsigned module: disable it in the firmware. It must be
re-run after each live boot. Before going further, confirm the dock is seen
(`lsusb -d 0711:`) and note the link speed. 480M may just mean the laptop port
is USB 2 only: check the port map (debugging.md, "Link speed").

## Notes from earlier sessions: read these first

- `machines.md`: per-machine log: port maps, what was tested, what's left.
  Add a section for every new machine.
- `debugging.md`: session hygiene (sudo, waiting for unplugs, the module
  reload cycle), usbmon filters, DRM debugfs, and every bug found on hardware
  with its symptoms.

## Quick reference

```sh
lsusb -d 0711: ; lsusb -t                    # device ID and link speed (480M = USB 2.0)
sudo insmod src/mct_t6.ko                    # or: sudo modprobe mct_t6 (DKMS)
sudo dmesg | grep -i mct_t6                  # discovery line: outputs, VRAM, fw, speed
grep . /sys/class/drm/card*-{HDMI,VGA}-*/status
cat /sys/class/drm/card*-HDMI-A-*/modes
sudo cat /sys/kernel/debug/mct_t6-*/stats    # frames, bytes, quality, encode/send ms, fences
modetest -M mct_t6 -s <conn>@<crtc>:1920x1080   # picture without a compositor (libdrm tests)
```

Runtime tuning with no reload: `/sys/module/mct_t6/parameters/jpeg_quality` and
`encode_jobs`.

## Capturing USB traffic when something's wrong

```sh
sudo modprobe usbmon
sudo cat /sys/kernel/debug/usb/usbmon/<bus>u > t6.usbmon   # text format, or Wireshark on usbmonN
```

Compare against the Windows captures (see the `t6-protocol-research` skill).
What to look for:

- Control requests that STALL. They show as status -32; e.g. `c0 cc` stalls even on Windows.
- Bulk objects the chip rejects. A JPEG decoder error appears as interrupt byte 0x13 bit 3; the driver logs "JPEG decoder error".
- Whether frame-done interrupts arrive. The stats file says `fences: ... (reported)` or `(not reported)`.

## Open questions only hardware can answer

These are listed at the end of docs/TESTING.md. Record each answer in
docs/PROTOCOL.md with the tag **[HW]**, and remove it from that list.

## Known hazards from the prior driver's logs

- Two T6 chips on one hub with interleaved bulk URBs can wedge xHCI.
- The chip may re-enumerate ~4 s after teardown unless head output is
  switched off (`0x03` off). Our CRTC disable sends this.
- A head can report status 0 until the monitor's power is cycled.
