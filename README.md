# mct_t6: Linux driver for MCT Trigger 6 USB displays

A Linux DRM/KMS driver for USB display adapters and docks built on the Magic
Control Technology (MCT) **Trigger 6** chip. Examples are j5create docks such
as the JCD543, with HDMI and VGA outputs alongside USB-A ports, Ethernet and
audio. On such docks the Ethernet and USB ports already work on Linux; the
display outputs need this driver.

The driver registers a normal DRM device, so GNOME, KDE, Sway and X11 see the
dock's outputs as ordinary monitors: hot-plug, resolution changes, a hardware
cursor and a text console all work through the standard interfaces.

> **Status: prototype.** It builds warning-free on kernels 6.1 through 7.2 and
> passes its host tests, KUnit, and an end-to-end test against an emulated chip
> under KASAN and lockdep. It has **not yet been run on real hardware.** See [docs/TESTING.md](docs/TESTING.md) for the
> hardware bring-up checklist.

## How it works

| | |
|---|---|
| USB device | The dock exposes one vendor-specific device, `0711:5601` "T6 USB Station" (driver matches `0711:5600–561F` and `5650–565F`, as MCT's Windows driver does). |
| Transport | Frames are sent as **baseline JPEG** and decoded by the chip. Over USB 2.0 that is the only way to reach 60 fps: raw 1080p60 would need ~10× the link's bandwidth. MCT's own drivers do the same. |
| Encoding | An in-kernel, integer-only JPEG encoder that re-encodes only the 16-line strips that changed, spread across CPU cores (see [docs/DESIGN.md](docs/DESIGN.md)). |
| Pacing | Frames are sent only when the screen changes. A timer-driven vblank paces compositors at the mode's refresh rate. JPEG quality adapts to the link. |
| Cursor | Uses the chip's hardware cursor, so moving the pointer costs one tiny USB request instead of a frame. |
| Modes | Up to 1920×1200 / 2048×1152 per output at the refresh rates in the chip's mode table (60 Hz at 1080p; up to 75 Hz at lower resolutions). |

The protocol is documented in [docs/PROTOCOL.md](docs/PROTOCOL.md), with the
source of every fact.

## Requirements

- Linux **6.1 or newer** with DRM, USB and the DRM shmem helpers enabled; all
  stock Fedora, Debian/Ubuntu and Arch kernels qualify.
- Kernel headers for the running kernel, and DKMS.

There are no runtime dependencies: no daemon, no userspace libraries.

## Installation (DKMS)

DKMS rebuilds the module automatically whenever the kernel is updated.

**Debian / Ubuntu**

```sh
sudo apt install dkms linux-headers-$(uname -r)
sudo cp -r . /usr/src/mct-t6-0.1.0
sudo dkms install mct-t6/0.1.0
```

**Fedora**

```sh
sudo dnf install dkms kernel-devel-$(uname -r)
sudo cp -r . /usr/src/mct-t6-0.1.0
sudo dkms install mct-t6/0.1.0
```

**Arch**

```sh
sudo pacman -S dkms linux-headers
cd packaging/arch && makepkg -si
```

Then plug in the dock. The module loads automatically through its USB device
table, and the outputs show up in your display settings.

**Secure Boot:** an unsigned module will not load. Debian/Ubuntu and Fedora's
DKMS sign modules with a machine owner key (MOK) that you enroll once with
`mokutil`; follow your distribution's DKMS instructions.

To remove: `sudo dkms remove mct-t6/0.1.0 --all`.

### Building by hand

```sh
make                       # build against the running kernel
sudo insmod src/mct_t6.ko
```

## Module parameters

| Parameter | Default | Meaning |
|---|---|---|
| `jpeg_quality` | 85 | Maximum JPEG quality (30–100). Lowered automatically while the link is saturated, then raised again. |
| `encode_jobs` | 0 | Parallel encoder jobs per frame; 0 = one per CPU (max 8). |
| `hw_cursor` | true | Use the chip's hardware cursor. |

Set them persistently in `/etc/modprobe.d/mct_t6.conf`, e.g.
`options mct_t6 jpeg_quality=90`.

## Troubleshooting

- `dmesg | grep mct_t6` shows what the driver found: output count, VRAM, firmware
  version and link speed.
- `/sys/kernel/debug/mct_t6-<usb-interface>/stats` (debugfs) shows per-output
  statistics: frames, bytes, current JPEG quality, encode and send time, and
  dropped frames.
- A VGA monitor without working DDC can't be detected; force it on with the
  kernel parameter `video=VGA-1:e`.
- If the link is USB 2.0, the log says `high-speed`. A SuperSpeed port gives far
  more headroom.

## Development

```sh
make check                               # host unit tests (needs python3 + Pillow + numpy)
tools/build-matrix.sh <kdir> [<kdir>...] # compile-test against kernel trees (W=1, sparse)
tests/e2e/run.sh                         # full driver vs. emulated chip under User-Mode Linux
```

See [docs/TESTING.md](docs/TESTING.md) for all test layers, and
[docs/DESIGN.md](docs/DESIGN.md) for the architecture.

## Limitations and roadmap

- Not yet validated on hardware: mode set, cursor and hot-plug follow MCT's own
  driver exactly, but need confirming on a real dock.
- No 4K: the chip can do 3840×2160@30 over SuperSpeed with a different memory
  layout, which is not implemented.
- Each update sends a whole-frame JPEG. The Windows driver can also patch
  rectangles (protocol command 7), which would cut USB traffic for small
  changes.
- Audio (HDMI audio session 3) is not implemented.

## Credits

- MCT's GPL reference driver [triggerdm](https://github.com/mcttrigger/triggerdm).
- [cyrozap/mct-usb-display-adapter-re](https://github.com/cyrozap/mct-usb-display-adapter-re) for protocol notes and Windows captures.
- [RL-Charles/jcd543-mct-t6-linux-driver](https://github.com/RL-Charles/jcd543-mct-t6-linux-driver), whose test logs informed several design decisions.

## License

GPL-2.0-only; see [LICENSE](LICENSE).
