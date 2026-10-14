# MCT Trigger 6 protocol as implemented by the prior "trigger6" GPL driver

Source: `ext/jcd543-mct-t6-linux-driver` (untrusted; read only, never built or run).
It is a fork of ramifriedman/mct-t6-linux @ e2aca2c (D/UPSTREAM_AUDIT.md:8-12). The fork
credits MCT `triggerdm` (GPL userspace) and cyrozap's RE notes as protocol sources (drv.c:16-17).

Citation key:
- `drv.c` = kernel/trigger6_drv.c, `conn.c` = kernel/trigger6_connector.c, `codec.c` = kernel/trigger6_codec.c
- `t6.h` = kernel/trigger6.h, `match.h`, `query.h`, `quiesce.h`, `refresh.h` = kernel/trigger6_*.h
- `D/X.md` = docs/X.md

All multi-byte fields are little-endian. "MiB" means 1024*1024.

> **WARNING: PID mismatch.** This driver matches only **0711:5601**, bcdDevice 0x1010
> (match.h:6-8, drv.c:3349-3352). The device is "MCT Corp., T6 USB Station" in a JCD543 dock
> (D/EVIDENCE.md:83-84). Your device, **0711:5621**, is never mentioned anywhere in the
> sources or docs. The only other ID the docs mention is an upstream issue about 0711:560b,
> which the fork did not add (D/UPSTREAM_AUDIT.md:26-28). So everything below was proven on
> 5601 only. Check the descriptors/endpoints on 5621 before assuming they are the same.

---

## 1. USB identity, interface and endpoints

The driver has two layers of matching:

- **USB ID table:** `USB_DEVICE_AND_INTERFACE_INFO(0x0711, 0x5601, 0xff, 0, 0)`
  (drv.c:3349-3352).
- **Exact descriptor policy:** `t6_profile_matches()` (match.h:40-76), called from probe
  (drv.c:2885-2920, 2932). It requires:
  - VID 0x0711, PID 0x5601, bcdDevice 0x1010.
  - Device class/subclass/protocol ff/00/00.
  - 1 configuration, bConfigurationValue 1, 1 interface.
  - bInterfaceNumber 0, bAlternateSetting 0, exactly 1 altsetting.
  - Interface class ff/00/00.
  - SuperSpeed link (`udev->speed == USB_SPEED_SUPER`).
  - Exactly 3 endpoints, in any order:

| EP | Type (bmAttributes) | wMaxPacketSize | bInterval | Use in driver |
|---|---|---|---|---|
| 0x81 | bulk IN (2) | 1024 | 0 | never used |
| 0x02 | bulk OUT (2) | 1024 | 0 | all frame data (`T6_EP_BULK_OUT`, match.h:9; drv.c:1288) |
| 0x83 | interrupt IN (3) | 64 | 5 | **never used** (no URB is ever submitted) |

- The measured descriptors agree with the table: bcdUSB 3.20 at 5 Gbit/s, max burst 1 on
  both bulk endpoints, no serial number (D/EVIDENCE.md:83-92).
- The driver never calls `usb_set_interface`; it uses altsetting 0 as enumerated.
- **Port-path guard (driver policy, not protocol):** probe refuses any device unless the
  module parameter `device_path` exactly equals `dev_name(udev)`, for example `2-3.4.1`
  (drv.c:60-63, 2934-2938). This exists because the device has no serial number and
  `devnum` changes (D/EVIDENCE.md:87).
- Default `manual_only=1` matches descriptors and does no I/O (drv.c:244-250, 2939-2945).
- Only one active probe is allowed per module insertion (drv.c:70-76, 2965-2969).
- `output_mask` must be 1 (head 0) or 2 (head 1). Two heads are never run together
  (match.h:78-82, drv.c:2946-2954).

## 2. Control-transfer primitives

- **OUT:** `bmRequestType = USB_TYPE_VENDOR|USB_DIR_OUT = 0x40`, device recipient, EP0.
  - Timeout 1000 ms (t6.h:45; drv.c:1199-1201).
  - Any result other than exactly `size` latches a permanent I/O fault: no more traffic
    until reload (drv.c:1203-1204, 1173-1180).
- **IN:** `bmRequestType = 0xC0`, timeout 1000 ms (drv.c:1226-1228).
  - Bounce buffer from `kzalloc`; an exact length is required, else the same fault latch
    applies (drv.c:1222-1233).

### Request codes the driver uses

| bReq | Dir | Name in source | Meaning per docs | Defined at |
|---|---|---|---|---|
| 0x80 | IN | GET_EDID | EDID block | query.h:12 |
| 0x84 | IN | GET_RES_COUNT | firmware timing-table count | query.h:13 |
| 0x87 | IN | GET_STATUS | connector status (0 = disconnected, 1 = connected) | query.h:14; D/INSTALL_TEST_2026-09-06.md:385-387 |
| 0x88 | IN | GET_RAM | VRAM size in MB | query.h:15 |
| 0x89 | IN | GET_RES_TABLE | 32-byte timing records | query.h:16 |
| 0x03 | OUT | MONITOR_CTRL | monitor power: wValue = head, wIndex = 1 on / 0 off, no data | t6.h:48; D/IDLE_REFRESH_EXPERIMENT.md:30-32; D/QUIESCE_EXPERIMENT.md:29-31 |
| 0x12 | OUT | SET_RESOLUTION | 32-byte timing record (mode set) | t6.h:49 |
| 0x1C | OUT | RESET_LO/HI, FINALIZE | **undocumented** in the MCT headers; used with wValue 0x0000, 0x0100 and 0x0002 | t6.h:53-55; D/TIMING_QUERY.md:37-38 |
| 0x23 | OUT | "SET_COLOR" (misnamed) | actually the **audio** "node values" request | t6.h:50; D/TIMING_QUERY.md:31-34 |
| 0x24 | OUT | "SET_TIMING" (misnamed) | actually the **audio** engine state request (`T6AUD_SETENGINESTATE`) | t6.h:51; D/TIMING_QUERY.md:31-34 |
| 0x31 | OUT | SET_READY | not explained; sent per head after 0x12 | t6.h:52 |

The docs also mention requests the driver does **not** use:

- 0x30 is the documented *hardware reset*: "Do not substitute the documented hardware reset
  request 0x30" for 0x1C (D/TIMING_QUERY.md:37-38).
- 0x1D: the Windows capture sends three identity-gamma 0x1D tables (D/INSTALL_TEST_2026-09-06.md:166-170).
- Audio requests 0x20-0x27 and 0xA0-0xA7 are deliberately blocked in query mode (D/TIMING_QUERY.md:92).

## 3. Probe / init sequence (exact order)

The `t6_usb_probe` path is drv.c:2922-3196. Steps 1-3 are IN only; step 4 is `t6_chip_init`.

### Step 1: RAM query (drv.c:3001-3014)

`C0 88 wValue=0000 wIndex=0000 wLength=4` returns a u32 LE count of MB.

- The device answered **58**. The driver refuses any other value because its VRAM address
  layout is derived from it (drv.c:3008-3013).

### Step 2: per head 0 and 1, if selected by `output_mask` (`t6_probe_head`, drv.c:720-779)

**a. Connector status:** `C0 87 wValue=head wIndex=0000 wLength=1` (drv.c:730).

- 0x01 means connected. Anything else means disconnected, and the head is skipped
  (drv.c:737-739).
- 0x00 is a normal answer and is not a USB error (D/INSTALL_TEST_2026-09-06.md:385-387).

**b. EDID:** `C0 80 wValue=0000 wIndex=head wLength=128` (drv.c:742-743).

- **The head goes in wIndex here**, but in wValue for 0x87.
- Only the 128-byte base block is read. No extension blocks are fetched, and no
  block/offset parameter is used.
- Validation: the 8-byte header `00 FF FF FF FF FF FF 00` plus a zero byte-sum
  (drv.c:1237-1249). Invalid EDID refuses the active test (drv.c:768-773).
- The driver then forces the extension count to 0 and keeps the checksum valid:
  `edid[127] += edid[126]; edid[126] = 0` (drv.c:747-748).
- It parses the preferred size from DTD1 for logging only (drv.c:749-767) and the monitor
  name from descriptor tag 0xFC (drv.c:693-718).

**c.** The head size is forced to 1920x1080 whatever the EDID says (drv.c:775-776).

### Step 3 (optional diagnostic): timing table, see section 5

This only runs with `query_only`; it never feeds the init path (drv.c:3028-3042).

### Step 4: `t6_chip_init` (drv.c:1321-1382)

Every request below is bmRequestType **0x40** (vendor OUT, device). The table in
D/INSTALL_TEST_2026-09-06.md:136-148 confirms the same order.

| # | bReq | wValue | wIndex | wLength | Payload | Src |
|---|---|---|---|---|---|---|
| 1 | 0x1C | 0x0000 | 0 | 0 | none | drv.c:1337 |
| 2 | 0x1C | 0x0100 | 0 | 0 | none | drv.c:1340 |
| 3 | 0x23 | 0 | 0 | 40 | `t6_init_color`, below | drv.c:1343-1344 |
| 4 | 0x24 | 0 | 0 | 16 | `t6_init_timing_pre` | drv.c:1347-1348 |
| 5 | 0x12 | head | 0 | 32 | mode record (section 4) | drv.c:1358-1359 |
| 6 | 0x31 | head | 0 | 0 | none | drv.c:1362-1363 |
| 7 | 0x03 | head | **1** (on) | 0 | none | drv.c:1366-1367 |
| 8 | 0x24 | 0 | 0 | 16 | `t6_init_timing_post` | drv.c:1373-1374 |
| 9 | 0x1C | 0x0002 | 0 | 0 | none | drv.c:1377 |

- Steps 5-7 repeat for each connected, selected head (drv.c:1352-1371).
- After step 7 the head's stream state is reset: `frame_seq=0`, slot index and command
  cursor rewound (drv.c:1370, 576-587).

**Payload bytes for step 3: 0x23, 40 bytes** (drv.c:265-271)

```
00 00 00 00 00 00 00 1f  00 00 00 1f 00 00 00 0f
00 00 00 0f 00 00 00 0f  00 00 00 0f 00 00 00 0f
00 00 00 0f 00 00 00 00
```

**Payload bytes for step 4: 0x24 "pre", 16 bytes** (drv.c:272-275)

```
00 00 00 00 00 00 00 00  80 25 00 00 00 00 02 00
```

**Payload bytes for step 8: 0x24 "post", 16 bytes** (drv.c:276-279)

```
01 00 00 00 00 00 00 00  80 25 00 00 00 00 02 00
```

How the docs decode the 0x24 blobs (D/TIMING_QUERY.md:31-34):

- They are `T6AUD_SETENGINESTATE` with Activity 0 (pre) / 1 (post), ReturnSize 9600 and
  CyclicBufferSize 131072.
- Byte view, consistent with that decode:
  - u32 @0x00 = Activity
  - u32 @0x04 = 0
  - u32 @0x08 = 0x2580 = 9600
  - u32 @0x0C = 0x00020000 = 131072
- These are **audio**, not video controls. Whether video needs them is unknown; the fork
  deliberately left them unchanged (D/DEVELOPMENT.md:110-117; D/USABILITY_SPEC.md:253-264).

The public Windows capture of the same dock differs from this init sequence
(D/INSTALL_TEST_2026-09-06.md:166-170):

- 0x31 is sent **earlier** in init.
- It uses a **different** 40-byte 0x23 payload; the bytes are not given.
- The 0x24 pre/post blobs and the 0x12 mode record are identical.
- It also sends **three identity-gamma 0x1D tables**, which this driver never sends.

### Step 5: DRM setup and registration (drv.c:3076-3178)

There are no more USB requests in this step. Frames only flow once userspace commits a
mode (section 6).

### Runtime control traffic after init

- **CRTC enable:** `40 03 wValue=head wIndex=1 wLength=0` (drv.c:2553-2554). This marks
  scanout active and, if enabled, arms the idle refresh (drv.c:2560-2563).
  - The mode is **not** re-sent on enable, because 0x12 is only sent at probe.
- **CRTC disable:** `40 03 wValue=head wIndex=0 wLength=0` (drv.c:2605-2606).
  - Before that request it cancels all timers and work and invalidates the last-frame
    cache, so the next real frame is sent in full (drv.c:2577-2595).
  - The keepalive timer had been waking the monitor in an on/off loop (comment drv.c:2578-2582).
- **Optional final off at disconnect** (`final_monitor_off=1`):
  - Request: `40 03 0000 0000 len0`, timeout 250 ms (quiesce.h:15-20; drv.c:3233-3264).
  - Sent after `drm_dev_unplug` and work drain, but before `usb_put_dev`.
  - It works because the USB core disables only the interface endpoints on unbind, not EP0
    (drv.c:3225-3232; D/QUIESCE_EXPERIMENT.md:58-65).
  - Measured: ret 0 in 1.576 ms and 1.866 ms (D/EVIDENCE.md:602, 667).

## 4. Mode set: the 32-byte 0x12 record

Request: `40 12 wValue=head wIndex=0 wLength=32` (drv.c:1358).

The record layout is MCT's `_ResolutionTiming`/`RESOLUTIONTIMING` from triggerdm t6.h
(field list at drv.c:280-287; D/TIMING_QUERY.md:50-55). The same layout is used by the
0x89 table records.

The driver **never builds this record from a `drm_display_mode`.** It sends one hard-coded
blob, `t6_mode_1080p` (drv.c:288-294), and the connector exposes exactly one DRM mode that
must be `drm_mode_equal` to it (conn.c:37-47, 74). The "derive from drm_display_mode"
column below is the obvious mapping, consistent with the record; the driver itself does
not do this.

Record bytes, verified equal to firmware record 26 and to a Windows 0x12 modeset capture
(drv.c:288-294; D/TIMING_QUERY.md:183-188; D/DEVELOPMENT.md:73-75):

```
14 44 02 00 3c 00 98 08 80 07 d8 07 2c 00 65 04
38 04 3c 04 05 00 bb 02 e8 03 1d 01 01 01 00 00
```

| Off | Size | Field | 1080p60 value | Derive from drm_display_mode |
|---|---|---|---|---|
| 0x00 | u32 | pixel clock, **kHz** | 0x00024414 = 148500 | `mode->clock` |
| 0x04 | u8 | refresh, Hz | 0x3C = 60 | `drm_mode_vrefresh()` |
| 0x05 | u8 | reserved | 0 | 0 |
| 0x06 | u16 | htotal | 0x0898 = 2200 | `htotal` |
| 0x08 | u16 | hdisplay | 0x0780 = 1920 | `hdisplay` |
| 0x0A | u16 | hsync start (active + front porch) | 0x07D8 = 2008 | `hsync_start` |
| 0x0C | u16 | hsync width | 0x002C = 44 | `hsync_end - hsync_start` |
| 0x0E | u16 | vtotal | 0x0465 = 1125 | `vtotal` |
| 0x10 | u16 | vdisplay | 0x0438 = 1080 | `vdisplay` |
| 0x12 | u16 | vsync start | 0x043C = 1084 | `vsync_start` |
| 0x14 | u16 | vsync width | 0x0005 = 5 | `vsync_end - vsync_start` |
| 0x16 | u16 | PLL FNUM | 0x02BB = 699 | **not derivable**: copy from the firmware table |
| 0x18 | u16 | PLL FDEN | 0x03E8 = 1000 | same |
| 0x1A | u8 | PLL IDIV | 0x1D = 29 | same |
| 0x1B | u8 | OutputSelect | 0x01 | same; meaning not documented |
| 0x1C | u8 | hsync polarity | 0x01 = positive | 1 if `DRM_MODE_FLAG_PHSYNC` (inferred encoding) |
| 0x1D | u8 | vsync polarity | 0x01 = positive | 1 if `DRM_MODE_FLAG_PVSYNC` (inferred encoding) |
| 0x1E | u8 | reduced blanking | 0 | presumably 1 for CVT-RB; untested |
| 0x1F | u8 | flags | 0 | unknown |

The matching DRM mode is `148500, 1920, 2008, 2052, 2200, 1080, 1084, 1089, 1125, +H +V`
(conn.c:37-42).

**Fixed bug: the inherited record had the wrong sync bytes, which gave a blank screen.**
The donor blob had hsync start 1816, vsync start 1000 and vsync width 29. Four bytes were
corrected (D/DEVELOPMENT.md:61-68):

- 0x0A: 0x18 → 0xD8
- 0x12: 0xE8 → 0x3C
- 0x13: 0x03 → 0x04
- 0x14: 0x1D → 0x05

The corrected record gave the first physical image (D/TIMING_QUERY.md:300-305).

**How to support other modes:** the PLL fields can't be computed from source, and the
formula is not documented. Take the whole 32-byte record from the firmware's 0x89 table
(section 5) and send it verbatim with 0x12. The docs recommend intersecting EDID modes with
validated firmware records and checking RAM, pitch and bandwidth limits
(D/USABILITY_SPEC.md:235-249).

The driver sends no 0x23/0x24/0x03 "around" a later modeset, because modes never change
after probe. The only modeset-adjacent order is the init order above: 0x23, 0x24(pre),
[0x12, 0x31, 0x03 on] per head, 0x24(post), 0x1C/2.

## 5. Timing-table query (0x84 / 0x89)

This is a diagnostic only (`query_only=1 query_timings=1`). It is never applied to
hardware (drv.c:781-835; D/TIMING_QUERY.md).

1. **Count:** `C0 84 wValue=0 wIndex=0 wLength=4` returns a u32 LE count
   (drv.c:802-805). It was **36** on this device (D/TIMING_QUERY.md:154).
2. **Records:** `C0 89 wValue=0 wIndex=<byte offset> wLength=32*n`, with n ≤ 16, so at most
   512 bytes per read (drv.c:815-821; query.h:18-20, 55-58).
   - **wIndex is a byte offset into the table:** 0, 512, 1024. In the Windows capture the
     three reads return 512, 512 and 128 bytes for 36 records (D/TIMING_QUERY.md:179-185).
   - MCT's source calls a non-zero wIndex "StartIndex", but the capture and the live device
     settle it as a byte offset (D/TIMING_QUERY.md:64-66, 181-183).
   - The driver itself only ever reads offset 0 or 512 (drv.c:793, 820-821).
3. **Record format:** 32 bytes each, identical to the 0x12 layout in section 4
   (drv.c:782-783).

Decoded records 0-15 (D/TIMING_QUERY.md:163-173):

| Index | Mode |
|---|---|
| 0-1 | 640x480 @ 60/75 |
| 2-4 | 800x600 @ 60/72/75 |
| 5-7 | 1024x768 @ 60/70/75 |
| 8 | 1152x864 @ 75 |
| 9 | 1280x720 @ 60 |
| 10-11 | 1280x768 @ 60/75 |
| 12-13 | 1280x800 @ 60/75 |
| 14 | 1280x960 @ 60 |
| 15 | 1280x1024 @ 60 |

- Records 16-31 come from offset 512. Record **26 is CEA 1080p60**, and is exactly the bytes
  in section 4 (D/TIMING_QUERY.md:250-258).
- Records 32-35 are at offset 1024 and were never read live.

**Open question: how is the head selected for 0x89?** cyrozap describes "head-selected"
0x89 reads, but the driver passes wValue=0 and wIndex=offset, and the doc table writes
"0, head 0" for wValue (D/TIMING_QUERY.md:61-62, 73-76). Treat per-head selection for
0x84/0x89 as **unknown**. It may be wValue = head.

## 6. Frame upload over bulk OUT (EP 0x02)

### 6.1 Transport mechanics (`t6_bulk_write`, drv.c:1251-1314)

- **Header and payload are separate bulk writes.** Every logical write is one call that
  sends the 32-byte header, then another call that sends the payload.
- **Chunking:** each call is split into synchronous `usb_bulk_msg` transfers of at most
  **102400 bytes** (`T6_USB_XFER_CHUNK_SIZE`, t6.h:90; drv.c:1277-1306).
  - 102400 = 100 × 1024, so only the final chunk can be a short packet.
  - Per-chunk timeout 5000 ms (t6.h:91).
  - There is no URB_ZERO_PACKET and no explicit ZLP. The device must rely on the lengths
    in the header.
- **Errors:** a short write or any error latches a permanent fault and halts traffic
  (drv.c:1293-1302).
- **Locking:**
  - A module-global `t6_usb_bus_lock` serialises bulk writes across all T6 devices. Reason
    given: two stations on one hub "can wedge the xHCI host controller" when their bulk URBs
    interleave (drv.c:117-122, 1275-1276, 1307-1308).
  - Per device, `io_lock` serialises control and bulk traffic (drv.c:2428).
- **Measured:** one full raw frame = 8,294,480 bytes in 83 chunks (D/RUNTIME_TEST_2026-09-05.md:141-142).
  - That is 1 chunk for the 32-byte header plus 82 for the 8,294,448-byte payload.

### 6.2 32-byte bulk header (`struct t6_bulk_header`, t6.h:100-111)

| Off | Field | Value used |
|---|---|---|
| 0x00 | u32 signature | **always 0**; the struct is memset and never assigned (drv.c:1493, 1509, 1535, 1568, 1732, 2038) |
| 0x04 | u32 payload_length | length of the following payload write |
| 0x08 | u32 payload_address | destination address in device VRAM |
| 0x0C | u32 packet_length | same as payload_length |
| 0x10 | u32 bytes_written | 0 |
| 0x14 | u32 output_index | **always 0, even for head 1** |
| 0x18 | u32 reserved[2] | 0 |

So the header is effectively "write `payload_length` bytes to VRAM address X". There is no
separate "select session" opcode in this driver.

### 6.3 48-byte flip header (`struct t6_flip_header`, t6.h:113-129)

This is the "video" command. It must be written to VRAM like any other payload.

| Off | Size | Field | Raw (head 0) | NV12 (head 1) | JPEG (head 1) |
|---|---|---|---|---|---|
| 0x00 | u32 | command | **3** = FLIP_PRIMARY, for head 0 | 4 = FLIP_SECONDARY | 4 |
| 0x04 | u32 | payload_size | frame_size = stride×h (**excludes** the header; no padding) | total−48 (NV12 + 1024 pad) | total−48 (JPEG + 1024 pad) |
| 0x08 | u32 | fence_id | 0 | 0 | 0 |
| 0x0C | u32 | target_format | **8** (RGB32, "BGRX 32-bit") | 6 (NV12) | 6 (NV12) |
| 0x10 | u16 | y_pitch | width×4 = **7680** (0x1E00) | ALIGN(w,16) | ALIGN(w,32) |
| 0x12 | u16 | uv_pitch | 0 | ALIGN(w,16) | ALIGN(w,32) |
| 0x14 | u32 | y_fb_offset | fb_addr + 48 | slot + 48 | slot (decode target) |
| 0x18 | u32 | u_offset | 0 | slot + 48 + y_pitch×h | slot + y_pitch×ALIGN(h,32) + 1024 |
| 0x1C | u32 | v_offset | 0 | 0 | 0 |
| 0x20 | u32 | source_format | 8 | 6 | **13** (JPEG) |
| 0x24 | u8[11] | padding | 0 | 0 | 0 |
| 0x2F | u8 | flag | **0x80** if frame_seq < 10, else 0 | same | 0x80 if seq < 10 **or** the cmd ring wrapped |

Field sources:

- Raw: drv.c:1469-1478.
- NV12: drv.c:2023-2033.
- JPEG: drv.c:1695-1705.
- Constants: t6.h:57-73.

Notes on `flag` (0x80):

- It is named "JPEG reset" in the MCT lineage, yet the driver also sets it for raw frames.
  Whether raw needs it is listed as **unresolved** (D/TIMING_QUERY.md:43-45; D/DEVELOPMENT.md:114-115).
- `frame_seq` counts successfully sent frames, refreshes included (drv.c:1619). It resets to
  0 at init (drv.c:584).

### 6.4 VRAM address map (ram_mb = 58; `t6_init_head_addressing`, drv.c:589-640)

Let `tmp = ram_mb − 18 = 40`.

**Head 0:**

- `fb_addr = (tmp − 12) MiB = 28 MiB = 0x01C00000` (drv.c:598).
- The flip header sits at 0x01C00000 and pixels start at **0x01C00030**.
- `cmd_addr = 0` is unused.

**Head 1 with NV12/JPEG** (triple buffering):

- Command ring base `tmp MiB = 40 MiB (0x02800000)`.
- fb slots at **46, 50 and 54 MiB** (ram−12, −8, −4) (drv.c:623-629).
- The command ring wraps before it reaches slot 0 (limit 46 MiB) (drv.c:630-636).
- Walking past that limit gave "a few visible frames, then stop" (drv.c:632-634).

**Head 1 with experimental raw** (blocked in this fork):

- Command ring at 40 MiB, two fb slots at 42 and 50 MiB (drv.c:602-621).
- Without double buffering it tears (drv.c:604-608).

### 6.5 Pixel format

- DRM exposes only `DRM_FORMAT_XRGB8888` (drv.c:296).
- The bytes go to the device **unchanged**, i.e. B,G,R,X in memory. The driver calls this
  "RGB32 (8), BGRX 32-bit" (t6.h:69-70).
- Format: 32 bpp, no compression, no byte swizzle, packed tightly at width×4. The driver
  re-packs if the framebuffer pitch differs (drv.c:521-550, 2790-2794).

Secondary-head formats (donor code; **never tested on this hardware** because head 1 had
no sink):

- **NV12:** BT.601 studio range with integer coefficients.
  - Y = ((66R + 129G + 25B + 128) >> 8) + 16.
  - U/V are taken from the top-left pixel of each 2x2 block:
    U = ((−38R − 74G + 112B + 128) >> 8) + 128 and V = ((112R − 94G − 18B + 128) >> 8) + 128.
  - Source: codec.c:741-815.
- **JPEG:** an in-kernel baseline 4:2:0 encoder (codec.c:1-15, 632-738). Default quality 40,
  adapted toward a 30 ms encode time (drv.c:1889-1912).

### 6.6 Raw head-0 send algorithm (`t6_send_frame_raw`, drv.c:1437-1638)

**Damage detection:**

- The driver keeps a host copy of the last frame sent and compares each 7680-byte row with
  `memcmp`. It builds up to **32** dirty row-ranges; more than that, or no valid reference,
  means a full frame (drv.c:1389-1435; t6.h:76).
- No DRM damage clips are used.
- Zero dirty rows means nothing is sent at all (drv.c:1461-1464).

**Full frame** (no reference, or more than 32 ranges): two bulk writes (drv.c:1521-1546).

1. Header: `{payload_length = 48 + 8294400 = 8294448, payload_address = fb_addr (0x01C00000), packet_length = 8294448}`.
2. Payload: the 48-byte flip header followed by all 8,294,400 pixel bytes, in one contiguous write.

So the flip header and pixels are written together at fb_addr, with pixels at fb_addr + 48.
This matches the documented 8,294,448-byte full payload (D/RUNTIME_TEST_2026-09-05.md:346).

**Partial frame** (head 0 only, drv.c:1480-1520):

1. For each dirty range, two bulk writes:
   - Header: `{len = rows×7680, addr = fb_addr + 48 + y_start×7680, packet_length = len}`.
   - Payload: those rows.
2. Then the flip: header `{48, fb_addr, 48}` plus the 48-byte flip header (payload_size is
   still the **full** frame size).
   - The source comment says the flip header is written last because it "triggers display
     after all rows written". The firmware reads the flip for the primary head directly from
     VRAM, and unchanged rows persist there (drv.c:1481-1488, 1508).

**Code quirk:** a comment says the first 10 frames are sent in full (drv.c:1522-1524), but
the code only forces a full frame when there is no reference. Frames 2-10 can therefore be
partial while still carrying flag 0x80.

**Head-1 NV12/JPEG sends** (untested):

- NV12: one write, header `{total, slot, total}` and then flip + NV12 + 1024 zero bytes, with
  slot rotation (drv.c:1996-2078).
- JPEG: written to the **command ring address** (not the fb slot): header
  `{total, cmd_addr, total}`, then flip + JPEG + 1024 zero bytes.
  - The command cursor advances by 1, 2 or 3 MiB depending on size; total must be ≤ 3 MiB
    (drv.c:1640-1773).

### 6.7 Frame pacing, queueing and refresh

- **Queueing:** the plane `atomic_update` copies the shadow-plane vmap into `tx_back`
  (drv.c:2666-2816). USB I/O happens later in a worker on an unbound workqueue
  (drv.c:2350-2523, 3057).
  - There is one pending slot per head; a newer frame overwrites it (drv.c:2757-2761).
- **Raw head:** no rate limit. Damage detection is the only throttle (drv.c:1000-1008).
- **NV12/JPEG:** adaptive gate at the last encode time, between 5 ms and the cap
  `secondary_frame_min_interval_ms` (default 250) (t6.h:97-98; drv.c:1010-1029).
- **Keepalive (donor, JPEG/NV12):** "The T6 chip blanks JPEG-decoded outputs that stop
  receiving frames after roughly 2-3 seconds". The driver re-sends the last frame every
  **2000 ms** (t6.h:93-95; drv.c:1775-1779, 1769, 2072).
- **Raw idle refresh** (fork opt-in `raw_idle_refresh=1`, head 0 only):
  - After **1000 ms** with no real frame, it re-sends the last frame in full through the
    normal sender (drv.c:104-109, 1780-1804, 2450-2460).
  - It runs only while the CRTC is active, and costs about 8.3 MB per idle second
    (D/IDLE_REFRESH_EXPERIMENT.md:36-49).
  - This correlated with ending the "disconnect 7-12 s after init on static content"
    problem (section 8). The docs call the watchdog explanation a **hypothesis**
    (D/DEVELOPMENT.md:119-123).
- **Boot keepalive** (donor, 1500 ms; drv.c:1806-1840): it writes cached data to fb_addr
  without a flip header. It is dead code in this fork, because black-frame boot priming was
  removed (D/IDLE_REFRESH_EXPERIMENT.md:25-29).
- **No vblank:** the driver sets `crtc_state->no_vblank = true` (drv.c:2616-2635).

## 7. Connector detection, EDID and hotplug

- Status (0x87) and EDID (0x80) are read **once, at probe**. All DRM callbacks serve cached
  data and do "ZERO USB calls" (conn.c:1-7, 20-31, 49-69).
- **No hotplug support:**
  - `connector.polled = 0`. "Polling caused system freezes -- drm_kms_helper_poll workqueue
    takes mode_config.mutex which deadlocks during probe" (conn.c:134-139).
  - The interrupt endpoint 0x83 is never read, so its message format is **unknown**.
  - Reconnecting means a deliberate unplug and reload.
  - `drm_kms_helper_hotplug_event` is only fired to report faults and resume
    (drv.c:2292-2293, 3339-3340).
- Connector type is HDMI-A, with subpixel order horizontal RGB (conn.c:124-132).
- EDID is published to DRM, and the physical size comes from EDID bytes 0x15/0x16 × 10 mm.
  The only mode offered is the fixed 1080p60 mode (conn.c:57-68).

## 8. Known problems, crashes, quirks and safety warnings

1. **Wrong mode sync fields gave a black screen** while the USB transfers succeeded. Fixed
   with the 4-byte change above (D/TIMING_QUERY.md:9-29, 263-268, 300-305).
2. **Device disconnects and re-enumerates 7-12 s after successful init**, with zero transfer
   errors. This correlated with static content (D/IDLE_REFRESH_EXPERIMENT.md:8-21;
   D/EVIDENCE.md:186-193).
   - USB-core reprobes then re-ran init in a loop, so the fork added a one-probe-per-insertion
     latch (drv.c:70-76).
   - The 1 Hz full-frame idle refresh coincided with stable runs; the cause is unproven.
3. **Firmware re-enumerates about 4.36 s after a clean driver teardown** if the monitor is
   not switched off first (D/EVIDENCE.md:495-501; D/INSTALL_TEST_2026-09-06.md:350-353).
   - Sending a final `40 03 head0 off` after unplug/drain left the device enumerated for
     15 s+ (D/EVIDENCE.md:600-608).
   - The ordering matters: `drm_dev_unplug` blocks the normal `atomic_disable` monitor-off,
     so a private post-unplug EP0 request is needed (D/QUIESCE_EXPERIMENT.md:21-27).
4. **Head status 0x00 after re-enumeration or a dock cold reset**, even with a monitor
   attached.
   - An HP-only AC power cycle of about 20 s restored status 1 on the same USB generation.
     A dock cold reset alone sometimes did not (D/INSTALL_TEST_2026-09-06.md:357-392;
     D/QUIESCE_EXPERIMENT.md:15-19).
   - Sink and HDMI power state is a separate firmware issue. Seconds since enumeration don't
     explain it (D/INSTALL_TEST_2026-09-06.md:374-383).
5. **Init failure:** once the T6 disconnected about 42 ms into active probe, and init
   returned -110 (timeout). Which OUT request failed is unknown
   (D/INSTALL_TEST_2026-09-06.md:125-150).
6. **Query side effect, suspected:** after a head-1 IN-only query, the device disconnected
   about 5 s later, and the next head-0 probe returned an invalid EDID. The cause could not
   be pinned down (D/EVIDENCE.md:224-232).
7. **The "0x23 color" and "0x24 timing" requests are really audio controls.** They were left
   in place untested; removing them is an open experiment (D/TIMING_QUERY.md:31-36).
8. **0x1C is undocumented.** Don't substitute 0x30, the real hardware reset
   (D/TIMING_QUERY.md:37-38).
9. **Two T6 devices on one hub can wedge xHCI** if their bulk transfers interleave, hence
   the global bus mutex (drv.c:117-122).
10. **Connector polling deadlocks or freezes the system** (conn.c:134-139).
11. **Kernel 6.17 can pass a stale `old_state` during `drm_dev_register`**, so the plane
    update queues the latest full frame (drv.c:2753-2756).
12. **JPEG/NV12 outputs blank after 2-3 s idle**, hence the 2 s keepalive (drv.c:1775-1779).
    The JPEG command ring must not wrap into the fb slots (drv.c:631-636).
13. **Suspend/resume is not supported:**
    - Suspend sets the I/O fault latch and stops all work.
    - Resume does not re-initialise, and traffic stays stopped until reload (drv.c:3315-3342).
    - After a whole-dock detach plus S4 resume, the device re-enumerated and was left unbound
      (D/EVIDENCE.md:58-66).
14. **Fault policy:** the first USB error or short transfer latches all traffic off. There is
    no automatic reset or retry (drv.c:1173-1180, 2262-2294).
15. **Compositor:** Hyprland/Aquamarine tries to create an EGL renderer on a renderless USB
    card and fails. Frames only flowed when the DRM driver name was faked as "evdi"
    (`aquamarine_evdi_name`) (drv.c:94-102; D/RUNTIME_TEST_2026-09-05.md:497-515).
    - A Ghostty/GTK4 SIGSEGV on output hotplug is a client bug, not a driver bug
      (D/EVIDENCE.md:525-533).
16. **`modetest -D <path>` is ignored by libdrm 2.4.134**; use `-M trigger6`
    (D/RUNTIME_TEST_2026-09-05.md:488-496).
17. **Donor behaviour the fork removed as unsafe:** a broad device alias, multiple
    active heads, a dynamic mode table that could overrun the frame buffers, automatic USB
    resets after control errors, re-initialisation on resume, and sysfs controls that issued
    USB writes (D/UPSTREAM_AUDIT.md:46-57).

### Achieved resolution, refresh rate and throughput

- **Only 1920x1080@60 is supported and proven** (head 0, HDMI, HP X27q)
  (D/DEVELOPMENT.md:9-17).
  - The monitor's native 2560x1440 was not attempted (D/USABILITY_SPEC.md:235-238).
  - Head 1 (VGA?) was never streamed because its status was 0 (D/USABILITY_SPEC.md:268-274).
  - "Not a measured 60-frame-per-second USB delivery rate" (D/UPSTREAM_AUDIT.md:127-128).
- **Measured, about 6 minutes of Hyprland desktop including screensaver animation:**
  6,181 frames and 22,939,240,336 bulk bytes in 260,213 chunks, with zero errors
  (D/RUNTIME_TEST_2026-09-05.md:173-176).
  - My arithmetic: about 17 frames/s and about 64 MB/s average. That counts partial
    (damage) frames.
  - Another instance: 6,914 frames and 22.78 GB (D/RUNTIME_TEST_2026-09-05.md:252).
- **Idle refresh:** 44 full frames in 45 s = 364,957,120 bytes, i.e. exactly 8,294,480 bytes
  per refresh at about 1 Hz (D/TIMING_QUERY.md:307; D/RUNTIME_TEST_2026-09-05.md:443-445).
- **A 45 s mixed sample:** 87 frames, of which 42 were refreshes, and 638,984,336 bytes
  (D/EVIDENCE.md:590-592).
- **A longer cumulative run:** 10,711 frames and 48,991,281,968 bytes
  (D/QUIESCE_EXPERIMENT.md:235).
- **Donor claims for head 1, unverified here:** NV12 takes about 2-3 ms to convert plus
  3-5 ms of USB per frame; JPEG takes about 52 ms to encode plus 1 ms of USB
  (drv.c:1946-1947).
- No per-frame USB latency figures are recorded in the docs. The metrics are available via
  sysfs `t6_metrics` (drv.c:397-508).

## 9. DRM architecture and kernel version

- **No simple display pipe:** it builds a full atomic CRTC, primary plane, VIRTUAL encoder
  and HDMI-A connector for each of 2 heads (drv.c:3089-3138).
  - The donor history mentions a "full CRTC/plane/encoder rewrite" (D/UPSTREAM_AUDIT.md:16-17).
- **GEM:** shmem (`DRM_GEM_SHMEM_DRIVER_OPS`, `DEFINE_DRM_GEM_FOPS`), with framebuffers from
  `drm_gem_fb_create` (drv.c:2856-2866, 298-302).
  - The DMA device is set via `usb_intf_get_dma_device` and `drm_dev_set_dma_dev`
    (drv.c:2993-2996).
- **Plane:** `DRM_GEM_SHADOW_PLANE_HELPER_FUNCS` / `DRM_GEM_SHADOW_PLANE_FUNCS` provide a
  vmap of the framebuffer, plus `drm_gem_plane_helper_prepare_fb` (drv.c:2833-2845).
  - No scaling; the plane must be exactly 1920x1080 at 0,0 (drv.c:2638-2664).
- **No DRM damage helpers:** damage comes from its own row-memcmp against the previous frame.
- **Mode config:**
  - `drm_atomic_helper_commit` with `drm_atomic_helper_commit_tail_rpm` (drv.c:298-306).
  - min 640x480, max 1920x1080, preferred_depth 32 (drv.c:3083-3087).
  - `drmm_mode_config_init` for managed cleanup (drv.c:3077).
- **Lifecycle:**
  - `drm_dev_enter/exit` guards around USB I/O from DRM/worker paths.
  - On disconnect: `drm_dev_unplug`, then cancel work, then the optional final off, then
    `drm_atomic_helper_shutdown` (drv.c:3266-3308).
  - Modelled on udl (drv.c:16-24).
- **Kernel version:** no minimum is stated.
  - Tested only on 7.1.9-arch1-2 (D/EVIDENCE.md:32, 79).
  - The donor README advertises 6.18 (D/UPSTREAM_AUDIT.md:22).
  - A comment references 6.17 behaviour (drv.c:2754).
  - Inference, not documented: it uses `drm_dev_set_dma_dev()`, which I believe first
    appeared around 6.16. In practice expect at least about 6.16 to 6.18.
  - The mode_valid const/non-const signature is handled with `__builtin_choose_expr`
    (conn.c:91-104).

## 10. Documented unknowns and guesses (collected)

- What 0x1C (wValue 0, 0x100, 2) and 0x31 (SET_READY) mean, and whether they are needed
  (D/TIMING_QUERY.md:37-38; t6.h:52-55).
- Whether the audio requests 0x23/0x24 are needed for video. The Windows capture uses a
  different 0x23 payload and sends 0x31 earlier (D/INSTALL_TEST_2026-09-06.md:166-172).
- Whether the 0x1D gamma tables, which Windows sends and this driver does not, matter.
- Whether the 0x80 flag is right for raw frames (D/DEVELOPMENT.md:114-115).
- PLL field semantics, OutputSelect, and the `reduced` and `flags` bytes. These are copied
  from firmware and never synthesised (D/TIMING_QUERY.md:28-29; D/USABILITY_SPEC.md:240-241).
- Head selection for 0x84/0x89, and the unit of wIndex (resolved as a byte offset) (section 5).
- The interrupt endpoint 0x83 message format and whether it signals hotplug; it is never used.
- The meaning of the `signature`, `bytes_written` and `output_index` fields of the bulk header;
  all are sent as 0.
- `fence_id` in the flip header (always 0) and any completion or acknowledgement mechanism.
  None is read, and EP 0x81 is unused.
- Whether 58 MB RAM makes every inherited VRAM address safe (D/EVIDENCE.md:282).
- Head-1 physical wiring (VGA?), dual-head operation, hotplug, suspend/resume and long-run
  stability (D/EVIDENCE.md:276-293).
- Root cause of the static-frame disconnects, the teardown re-enumeration and the status-0
  sink state (all hypotheses; section 8).
- Colour and image accuracy beyond a readable test screen (D/EVIDENCE.md:283-284).
- Whether the device is JCD543 or JCD543P, and its firmware revision (D/EVIDENCE.md:278-279).
