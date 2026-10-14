# Hardware test log (per machine)

One section per machine and dock combination. For each, record: what was
tested, what worked, what broke, and what the hardware revealed. Protocol facts
also go in docs/PROTOCOL.md as **[HW]**; this file is about the *setup*.

When starting on a new machine, copy the template at the bottom, then fill in
the port map first. It decides the link speed, and the link speed decides
everything else.

---

## Lenovo 82QD (IdeaPad, Alder Lake-P) + j5create HDMI/VGA dock, Fedora 44 KDE live USB

*Session: 2026-10-14. Kernel 6.19.10-300.fc44, gcc 16.2.1, KDE Plasma on Wayland (KWin + Xwayland).*

**Environment**
- Live USB: user `liveuser`. sudo needed a password until the user added
  `/etc/sudoers.d/90-liveuser-nopasswd`, which is gone after a reboot. The
  user's own terminal caches sudo per tty, so "sudo works for me" does not
  mean it works for Claude's shell. Check with `sudo -n true`.
- Secure Boot: disabled in firmware.
- `tools/fedora-live-setup.sh` needed `libasan libubsan` for the host tests
  (now in its package list).
- `tools/build-matrix.sh` here: gcc W=1 is clean, but **sparse 0.6.4 fails** on
  6.19 headers (`bad constant expression` on every `MODULE_PARM_DESC` /
  `MODULE_*` line). This is a sparse limitation, not our code. The full
  6.1/6.12/6.18/7.2 matrix lives on the WSL machine.

**USB port map** (from `/sys/bus/usb/devices/usb3/3-0:1.0/usb3-port*/{peer,location}`)

| ACPI location | USB 2 port | SuperSpeed peer |
|---|---|---|
| 01 | `usb3-port1` (hotplug) | **none: USB 2.0 only** |
| 02 | `usb3-port2` (hotplug) | `usb2-port1`, 20 Gbps on TB4 xHCI `00:0d.0` (USB-C) |
| 05 | `usb3-port9` (hotplug) | `usb4-port1`, 10 Gbps on PCH xHCI `00:14.0` |

DRM: our device was `card0` (minor 0); i915 was `card1`.

**Dock topology** (on the USB 2.0-only port): Genesys `05e3:0610` hub with
`bcdUSB 2.10` → AX88179 Ethernet `0b95:1790` (`bcdUSB 2.10`) on hub port 3, and
T6 `0711:5601` (`bcdUSB 2.00`, `bcdDevice 10.10`) on hub port 4. All ran at
480M. The 2.10 values mean the hub and Ethernet are USB 3 devices. The T6
reporting 2.00 suggests it is USB 2 only inside this dock. SuperSpeed port: not
yet tried.

**Results**
- Discovery: `2 output(s), 58 MiB VRAM, platform 1, firmware 0x17091401, high-speed`. Worked first time.
- HDMI: EDID 256 bytes, 1920x1080. Picture correct (colour OK; the user thought
  quality was slightly soft at q85).
- VGA: EDID read via DDC works (1280x1024). For about a second after plug-in,
  DDC returns a constant garbage block (`64 02 00 43 47 f2 01 ff …` then
  `40 00 00 09` repeated), so the connector shows `unknown` until the poll
  re-detects it. Status `0x87` always returns 0 for VGA.
- JPEG on head 0 and head 1 at USB 2.0: accepted. Fences are reported
  (interrupt byte `04` per frame), with 0 drops and 0 fence timeouts over
  about 24k frames.
- Throughput at q85: about 250 KB/frame at 1080p; encode about 12.7 ms per
  frame, send about 6.8 ms per frame.
- Hot-unplug and replug of the whole dock: works; KWin releases the device.
- Cursor bugs found and fixed (see debugging.md):
  1. clipped-shape upload at screen edges;
  2. tearing during shape changes ("half and half") → double-buffered slots.
  Both fixes are confirmed by the user: the cursor is clean on HDMI and VGA.
- `WARNING drm_mode_config.c:578` on unplug: a DRM core issue in 6.19.10, not
  ours (see debugging.md).

**SuperSpeed:** the 10 Gbps USB-A port (location 05) holds the live USB
stick. Next time, boot the stick from the USB 2 port (location 01) and put
the dock in location 05, or use the USB-C port with an adapter.

**Still to do on this machine:** try a SuperSpeed port,
the throughput test with video, suspend/resume, fbcon on a text VT, and
modetest.

---

## Template

```
## <machine model> + <dock>, <distro> <installed|live>

*Session: <date>. Kernel <uname -r>, compositor <...>.*

**Environment**: sudo, Secure Boot, anything missing from the setup script.
**USB port map**: location → USB 2 port → SuperSpeed peer (see debugging.md for the command).
**Dock topology**: `lsusb -t` + bcdUSB of each dock device.
**Results**: discovery line, per-head EDID/modes, picture, cursor, hot-plug, stats.
**Still to do**:
```
