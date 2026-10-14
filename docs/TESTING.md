# Testing

The driver is tested in layers. Each one catches a different class of
problem, and all but the last run without hardware.

| Layer | Command | What it proves |
|---|---|---|
| Host unit tests | `make check` | Wire formats byte-exact against Windows captures; JPEG encoder correct and on par with libjpeg |
| Compile matrix | `tools/build-matrix.sh <kdir>...` | Builds warning-free (`W=1`, sparse) on every supported kernel API generation |
| KUnit | inside the e2e run, or any KUnit kernel | The same pure code behaves when built with kernel flags, in-kernel |
| End-to-end (UML) | `tests/e2e/run.sh` | The real module against an emulated chip: probe, EDID, mode set, frames, cursor, teardown |
| Hardware | checklist below | The real dock |

## Host unit tests (`tests/host`)

Built with AddressSanitizer and UndefinedBehaviorSanitizer.

**`test_proto`** checks the protocol encoders and parsers:

- timing records: the 1080p60 and 4K30 records exactly as the Windows driver
  sent them, plus rejection of malformed entries;
- the JPEG video header, byte-for-byte against a captured Windows frame;
- the bulk header;
- the VRAM layout for one and two heads, matching MCT's diagrams;
- ring placement over 100 frames: bounds, alignment, wrap and reset-flag rules;
- interrupt packets, the section header and cursor encodings.

**`test_jpeg`** plus **`check_jpeg.py`** check the encoder on 96 images: 8 sizes
from 1×1 to 1920×1080, including non-multiple-of-16 edges and padded pitches,
4 kinds of content, and 3 qualities.

- Frames assembled from cached rows must be **byte-identical** to a naive
  one-pass encoder built from the same primitives, including after 20 random
  partial re-encodes. This proves the row cache and bit splicing.
- An independent decoder (libjpeg via Pillow) must decode every file without
  warnings, as baseline 4:2:0 of the right size.
- Fidelity must be within 0.5 dB PSNR of libjpeg's own encoder at the same
  quality and subsampling, and the file no more than 10% larger.
- Undersized buffers must fail with `-ENOSPC`, never overrun.

`make -C tests/host bench` reports encoder throughput.

## Compile matrix

```sh
tools/build-matrix.sh /path/to/linux-6.1 /path/to/linux-6.12 /path/to/linux-6.18 /path/to/linux-7.2
```

Each tree must be configured with DRM, USB and a driver that selects
`DRM_GEM_SHMEM_HELPER` (e.g. `DRM_GUD=m`), then prepared with `make
modules_prepare`. With a fully built tree, modpost also verifies every
imported symbol. During development, all four kernels above were tested with
zero diagnostics. 6.1, 6.12 and 6.18 cover Debian 12, Debian 13 and current
Fedora; 7.2 covers Arch.

## End-to-end under User-Mode Linux (`tests/e2e`)

A UML kernel runs as an ordinary process, so this needs no root and no VM.
Inside it, `dummy_hcd` + `raw_gadget` let a userspace program (`t6emu`) act as
a Trigger 6. It serves the real chip's descriptors, timing tables and EDID
(taken from the Windows captures), and validates and records every request and
frame. A DRM client (`t6drm`) sets a mode, draws, sends partial updates and
moves the cursor. `verify.py` decodes the recorded frames and compares them
with what the client drew. It also checks the control-request sequence, runs
the KUnit suite's results, and fails on any kernel warning.

See [tests/e2e/README.md](../tests/e2e/README.md) for details and
requirements.

## Hardware bring-up checklist

When moving to a Linux machine with the dock, go in this order. Each step
isolates one layer.

1. **Identify the device.** `lsusb -d 0711:` should show `0711:5601`, or another
   ID in `5600–561F` / `5650–565F`. `lsusb -t` shows the link speed (480M or
   5000M).
2. **Load the module.** Use `sudo modprobe mct_t6` (DKMS), or `sudo insmod
   src/mct_t6.ko`.
3. **Check discovery.** `dmesg` should show `Trigger 6: 2 output(s), 58 MiB VRAM,
   ... high-speed`. A failure here (e.g. `device discovery failed`) means a
   control request is answered differently than documented. Capture it with
   usbmon (step 9).
4. **Check connectors.** `cat /sys/class/drm/card*-HDMI-A-*/status` should say
   `connected` with a monitor attached. Run the same for `card*-VGA-*`, and check
   `modes` lists 1920x1080.
5. **First picture, without a desktop.** On a text console (Ctrl+Alt+F3), the
   fbdev console should appear on the dock's monitor. Then use `modetest -M
   mct_t6 -s <connector>@<crtc>:1920x1080` from libdrm's tests. It draws a test
   pattern with no compositor involved.
6. **Desktop.** Log into GNOME/KDE. The monitor appears in display settings.
   Check that the pointer is smooth (hardware cursor), and that typing and
   scrolling update promptly.
7. **Hot-plug.** Unplug and replug the HDMI cable; the desktop should notice
   within a second. Unplug and replug the whole dock, then check `dmesg` for
   warnings.
8. **Throughput.** Play a full-screen video, then read
   `/sys/kernel/debug/mct_t6-*/stats`. Frames per second is the delta of
   `frames` over time, and `quality` shows the adaptive JPEG quality. Compare
   `encode_ms` and `send_ms` to see whether the CPU or the link is the limit.
9. **When something's wrong, capture the traffic.** Load usbmon (`modprobe
   usbmon`) and record `/sys/kernel/debug/usb/usbmon/<bus>u` (or use Wireshark
   on `usbmonN`). cyrozap's Wireshark dissector in
   [mct-usb-display-adapter-re](https://github.com/cyrozap/mct-usb-display-adapter-re)
   decodes the T6 protocol. Compare against the Windows captures in that
   repository.
10. **Suspend/resume** with the dock attached and an output active.

Things that only hardware can confirm, in rough order of risk:

- ~~that the chip accepts JPEG frames on head 0 at USB 2.0 speed~~: yes, on both
  heads (2026-10-14, see PROTOCOL.md **[HW]** and
  `.claude/skills/hardware-bringup/machines.md`);
- ~~whether the chip reports frame-done fences for JPEG frames~~: yes
  (`fences: … (reported)`, interrupt byte `04` per frame);
- ~~whether showing cursor slot N hides the previously shown slot~~: yes,
  so the driver double-buffers shapes in slots 0/1;
- whether cursor alpha is premultiplied;
- ~~whether VGA connection status is reported or only DDC works~~: only DDC
  (status `0x87` is always 0 for VGA); DDC answers garbage for about a second
  after plug-in;
- whether the T6 links at SuperSpeed on a USB 3 port (on this dock it reports
  `bcdUSB 2.00`);
- real throughput on this laptop's USB 2.0 link (single-frame numbers so far:
  about 250 KB per 1080p frame at q85, about 7 ms to send).
