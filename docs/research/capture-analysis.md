# MCT Trigger 6 (T6) – ground truth from Windows-driver USB captures

Source repo: `(cloned) mct-usb-display-adapter-re` (treated as data only; nothing from it was built or run).
Analysis tools (my own, stdlib-only Python, run with `-I`): `tools/research/`
(`usbpcap.py` pcapng + usbmon parser, `ctrl.py`, `bulk.py`, `sessions.py`, `modes.py`, `jpeginfo.py`,
`intcorr.py`, `topng.py`, `nv12png.py`, …). Raw dumps are in `docs/research/windows-captures/`
(`ctrl-*.txt`, `sess*.txt`, `modes*.txt`, reassembled payloads `s<capture>/v*.bin`).

tshark is **not** installed; captures were decompressed to `scratchpad/captures/` and parsed directly.

Captures (all are Linux **usbmon** captures, linktype 220 / `LINKTYPE_USB_LINUX_MMAPPED`, i.e. Windows 10 in a VM
with the device passed through; frame numbers below are pcapng packet numbers = Wireshark frame numbers; for a
control transfer the number cited is the SUBMIT (`S`) packet, its completion is the next packet of that URB):

| Tag | File | Device | Notes |
|---|---|---|---|
| **1925** | `trace-JCD543-20220514T1925-…-connect-1080p-edid` | JCD543, bus 6 dev 25 | 1 output used, 1080p60 EDID, **raw RGB** video, older driver |
| **1928** | `trace-JCD543-20220514T1928-…-connect-4k-edid` | JCD543, bus 6 dev 25 | 3840x2160@30, raw RGB then **raw NV12** |
| **JUA365** | `trace-JUA365-20230820T2157-…` | JUA365, bus 6 dev 42 | 2 outputs, hot plug/unplug, newer driver, **JPEG** video |

> Important for your 0711:5621 device: the *USB device descriptor* in all captures says **idProduct 0x5601**
> (JCD543 and JUA365). **0x5621** appears in the captures only as the "virtual display device" PID returned by
> vendor request `0xB1`/`0xB3` ("USB 3.0 External Graphic Device" / "Trigger 6 External Graphics").
> If your dock really enumerates as 0711:5621, expect the same protocol (it is the same T6 family) but verify the
> descriptors with `lsusb -v` on your unit.

---------------------------------------------------------------------------------------------------------------

## 1. USB descriptors of the T6 display function

### 1.1 As seen on the wire (GET_DESCRIPTOR responses in the captures)

Device descriptor (1925 #1/#11, JUA365 #5; identical on both devices):
`12 01 10 03 ff 00 00 09 11 07 01 56 10 10 01 02 00 01`

| Field | Value |
|---|---|
| bcdUSB | 3.10 |
| bDeviceClass/Sub/Proto | 0xFF / 0x00 / 0x00 (vendor) |
| bMaxPacketSize0 | 9 (=512 B, SuperSpeed) |
| idVendor:idProduct | **0711:5601** |
| bcdDevice | 10.10 |
| iManufacturer / iProduct / iSerial | 1 "MCT Corp." / 2 "USB Station" (JCD543) or "T6 USB Station" (JUA365) / 0 |
| bNumConfigurations | 1 |

Configuration descriptor (1925 #5, JUA365 #13), wTotalLength 57:

```
09 02 39 00 01 01 00 80 1f      config 1, 1 interface, bus powered, MaxPower 0x1f*8 = 248 mA (JUA365: 0x32 = 400 mA)
09 04 00 00 03 ff 00 00 00      interface 0 alt 0, 3 endpoints, class ff/00/00, iInterface 0
07 05 81 02 00 04 00            EP 0x81 BULK IN,  wMaxPacketSize 1024
06 30 00 00 00 00                 SS companion: bMaxBurst 0, bmAttributes 0
07 05 02 02 00 04 00            EP 0x02 BULK OUT, wMaxPacketSize 1024
06 30 00 00 00 00                 SS companion: bMaxBurst 0
07 05 83 03 40 00 05            EP 0x83 INTERRUPT IN, wMaxPacketSize 64, bInterval 5 (2^(5-1)*125us = 2 ms)
06 30 00 00 00 00                 SS companion: bMaxBurst 0, wBytesPerInterval 0
```

BOS (1925 #15): `05 0f 16 00 02 | 07 10 02 02 00 00 00 (USB2 ext, LPM) | 0a 10 03 00 0e 00 01 0a 20 00 (SS cap: FS/HS/SS, U1 exit 10 us, U2 exit 32 us)`.

Strings: LANGID 0x0409; idx1 "MCT Corp."; idx2 "USB Station" (JCD543) / "T6 USB Station" (JUA365).
JUA365: Windows also asks for the MS OS string descriptor (`80 06 wValue=03EE`, #23, #25) -> STALL (-EPIPE). Ignore.

### 1.2 From doc/descriptors (lsusb text files)

All T6 parts (JCD543, JUA365, JUA311, USB32HDESv2, USB32DPES2, JCA366 = 0711:5601; JUA214/JUA254 = 0711:5600)
have **exactly the same single vendor interface**: EP 0x81 bulk IN 1024, EP 0x02 bulk OUT 1024, EP 0x83 interrupt
IN 64 bytes bInterval 5. The lsusb files list `bMaxBurst 15` for the bulk EPs (JCD543, JUA365, …) whereas the
captured descriptors say `bMaxBurst 0` (firmware difference; irrelevant to a driver). JCA366 is a T6 behind a
USB3.2 hub. (0711:58xx JUA310/350/355/USB32HDES are Trigger 5, 0711:5200 is Trigger 2 – different protocol.)

Endpoint usage in the captures: **EP 0x02 bulk OUT carries all video/audio; EP 0x83 interrupt IN is polled
continuously; EP 0x81 bulk IN is never used.** No alternate settings, no SET_INTERFACE.

---------------------------------------------------------------------------------------------------------------

## 2. Control-transfer sequence, plug-in -> first frame

Notation: `bmRequestType bRequest wValue wIndex wLength -> data` (all hex, little-endian fields shown as the
16-bit values). Times are seconds from capture start. Status 0 unless noted.

### 2.1 JCD543, 1080p (capture 1925) – complete list

Enumeration by the Windows USB stack (not driver-specific):

| # | t | Request | Data / meaning |
|---|---|---|---|
| 1,3,5 | 0.000 | `80 06 0100/0200` | device/config descriptors (a pre-reset enumeration) |
| 7 | 7.911 | `80 06 0100 0000 8` | GET_DESCRIPTOR device (first 8 B) |
| 9 | 7.911 | `00 31 01df 0000 0` | SET_ISOCH_DELAY (standard USB3) |
| 11–17 | 7.911 | `80 06 0100/0f00/0f00/0200` | device, BOS(5), BOS(22), config(57) |
| 19 | 7.913 | `00 09 0001 0000 0` | **SET_CONFIGURATION 1** |
| 21–29 | 7.928–7.948 | `80 06 …` | device, config(255), BOS(255), string 0, string 2 |
| 31 | 7.948 | `00 31 0028 0000 0` | SET_ISOCH_DELAY 40 ns |
| 33 | 7.948 | `00 30 0000 0000 6` -> `5f0a75002000` | SET_SEL |
| 35, 37 | 7.954 | `00 03 0030 / 0031` | SET_FEATURE U1_ENABLE, U2_ENABLE |
| 39–47 | 7.955 | `80 06 0300/0301/0302` | strings |

Vendor driver initialisation (device idle, no monitor connected):

| # | t | bmRT bReq wValue wIndex wLength | Response / data | Meaning |
|---|---|---|---|---|
| 49 | 7.957 | `c0 b0 0000 0001 4` | `b9280616` | info field 1 "Boot code version" = 0x160628b9 |
| 51 | 7.957 | `c0 b0 0000 0002 4` | `01130821` | field 2 "Image code version" = 0x21081301 |
| 53 | 7.958 | `c0 b0 0000 0004 4` | `08000000` | field 4 "Vendor command version" = 8 |
| 55 | 7.958 | `c0 b0 0000 0000 4` | `01000000` | field 0 "Hardware platform" = 1 = **Super Lite -> 40 MHz PLL ref** |
| 57 | 7.958 | `c0 b0 0000 0005 8` | `0000000000000000` | field 5 serial (blank) |
| 59 | 7.958 | `c0 b4 0000 0000 4` | `00000000` | unknown |
| 61 | 7.958 | `c0 b0 0000 0003 16` | `"D9058HV\0…"` | field 3 project code (JUA365: `"A8610HH2"`) |
| 63 | 7.959 | `c0 b1 0000 0000 132` | vid 0x0711, pid **0x5621**, UTF-16 "USB 3.0 External Graphic Device", then the same 32 bytes as B3@80..111, then the first 0x89 mode entry (640x480) | session-0 (video) info |
| 65 | 7.961 | INT EP 0x83 polling starts (URB submitted) | | |
| 70 | 7.961 | INT IN | `24 00 00 00 … [16..19]=00000001 …` | initial status |
| 72 | 7.971 | `c0 cc 0001 0000 104` | **STALL** (status -32) | unsupported on this FW; driver ignores |
| 74 | 7.972 | `c0 b1 0000 0000 132` | same as #63 | |
| 76 | 7.972 | `c0 b1 0000 0003 132` | vid 0x0711 pid 0x5640 "USB Audio Device", …, ends with the A5 audio descriptor | session-3 (audio) info |
| 78 | 7.972 | `c0 a1 0000 0000 16` | `00010100010000000000000000000200` | per-output info, output 0 (unknown) |
| 80 | 7.972 | `c0 a4 0000 0000 16` | `00000000000000000000000000000200` | (readback of the 0x24 block) |
| 82 | 7.972 | `c0 a1 0000 0001 16` | `01010100010000000000000000000200` | per-output info, output 1 |
| 84 | 7.972 | `c0 a4 0000 0001 16` | `00000000000000000000000000000000` | |
| 86 | 10.013 | `c0 b3 0000 0000 112` | `"DISP"`, size 0x8b0, vid 0711 pid 5621, name, ver 1, func 0x02008003, disp0caps 0x00702402, disp1caps 0x04f01e01, intf 0x00003200 | config blob. disp caps byte1 = number of 0x89 mode entries (0x24=36, 0x1e=30) |
| 88 | 10.013 | `c0 88 0000 0000 1` | `3a` | VRAM = 58 MB |
| 90 | 10.014 | `40 1c 0000 0000 0` | | LUT/gamma control output 0 = 0 (off) — see 0x1c below |
| 92 | 10.014 | `40 1c 0100 0000 0` | | same for output 1 |
| 94 | 10.015 | `40 31 0000 0000 0` | | unknown |
| 96 | 10.019 | `c0 89 0000 0000 512` | 16 mode records | chip mode table, output 0, offset 0 |
| 98 | 10.020 | `c0 89 0000 0200 512` | 16 mode records | offset 512 |
| 100 | 10.020 | `c0 89 0000 0400 128` | 4 mode records | offset 1024 (total 36 = 1152 B) |
| 102 | 10.021 | `c0 89 0001 0000 512` | | output 1 table, offset 0 |
| 104 | 10.021 | `c0 89 0001 0200 448` | | offset 512 (total 30 = 960 B) |
| 106 | 10.021 | `c0 87 0000 0000 1` | `00` | output 0 disconnected |
| 108 | 10.022 | `c0 87 0001 0000 1` | `00` | output 1 disconnected |

(Note: 0x89 wValue = output, wIndex = byte offset, and the driver asks for exactly the size implied by the B3
mode count.)

Monitor plugged in (HDMI on output 0) — see §5 for the interrupt packets:

| # | t | bmRT bReq wValue wIndex wLength | Data | Meaning |
|---|---|---|---|---|
| 110 | 65.023 | INT IN | type 0x04, dw4 = 0x01000000 | connector-0 change |
| 112 | 65.024 | `c0 87 0000 0000 1` | `01` | output 0 connected |
| 114 | 65.029 | `c0 87 0001 0000 1` | `00` | |
| 116 | 65.029 | INT IN | type 0x20, dw8 = 0x02000000 | state: connector 0 present |
| 118–124 | 65.03–66.03 | `c0 87` out0/out1 polled once per second | `01`/`00` | debounce/poll |
| 126 | 66.496 | `c0 a5 0000 0000 32` | `80bb0000 80001002 00005046 00000000 00701700 e9440100 eb01e803 00000000` | audio descriptor: 48000 Hz, 16-bit, 2 ch, … |
| 128 | 66.496 | `c0 a2 0000 0000 16` | `00000000 01000000 00000000 1f000000` | unknown |
| 130 | 66.496 | `c0 a3 0000 0000 40` | `ff000000 00000000 0f000000 x8` | read 40-byte block (pairs with 0x23) |
| 132 | 66.497 | `40 23 0000 0000 40` | `03000000 00000000 1f000000 1f000000 0f000000 0f000000 0f000000 0f000000 0f000000 0f000000` | write 40-byte block (meaning unknown; likely audio routing/volume) |
| 134 | 66.504 | `40 24 0000 0000 16` | `00000000 00000000 80250000 00000200` | audio config, **byte0 = 0 (stopped)**, dw2 = 0x2580 = 9600 (= first audio session size), byte14 = 2 (channels) |
| 136,138 | 67.030 | `c0 87 0000 0000 1` | `01` | |
| 140 | 67.031 | `c0 80 0000 0000 128` | EDID block 0 (see §3) | **wValue = byte offset, wIndex = output** |
| 142 | 67.032 | `c0 87 0001 0000 1` | `00` | |
| **144** | 67.041 | **`40 12 0000 0000 32`** | `144402003c0098088007d8072c00650438043c040500bb02e8031d0101010000` | **SET VIDEO MODE output 0: 1920x1080@60** (§3) |
| **146** | 67.041 | **`40 03 0000 0001 0`** | | **enable output 0** (wValue = output, wIndex = 1 on / 0 off) |
| 148 | 67.183 | `40 24 0000 0000 16` | `01000000 00000000 80250000 00000200` | **audio start** (byte0 = 1) |
| 150 | 67.189 | **first bulk OUT** (audio session 3, 9600 B of silence) | | |
| 158 | 67.192 | **first video selector** (session 0, frame 1) | | §4 |
| 170 | 67.194 | `40 1d 0000 0100 256` | `00 01 02 … ff` | LUT upload, output 0 (wValue hi byte), table 0x100 |
| 176 | 67.195 | `40 1d 0000 0200 256` | `00 01 02 … ff` | table 0x200 |
| 180 | 67.195 | `40 1d 0000 0400 256` | `00 01 02 … ff` | table 0x400 (one per colour channel; identity ramp) |
| 183 | 67.196 | `40 1c 0002 0000 0` | | LUT control output 0 = 2 (enable) |
| 444 | 67.240 | last URB of frame 1 | | |
| 446 | 67.241 | INT IN type 0x04, dw3 = 1, dw4 = 0x04000000 | | **frame seq 1 done** (§5) |
| 2420 | 68.895 | `40 24 0000 0000 16` | byte0 = 0 | audio stop (≈1.7 s later; no sound playing) |

No cursor requests (0x04/0x05/0x10) occur in any capture (the cursor is composited into the framebuffer).

### 2.2 Differences in the other captures

* **1928 (JCD543 4K)**: identical request order up to the mode set (#49…#106; frame numbers equal or −2). Monitor EDID has
  an extension, so the driver reads `c0 80 0000 0000 128` (#138) **and** `c0 80 0080 0000 128` (#140).
  Then `40 12 0000 0000 32` = `288804001e003011000fb00f5800ca08700878080a00bb02e8031d0301010000` (#144),
  `40 03 0000 0001` (#146), `40 24` byte0=1 (#148), `40 1d` x3 (#150/#164/#169), `40 1c 0002` (#171).
  Note here `c0 a3` already returned `03…1f 1f…` (the value written by 0x23 earlier survived).
* **JUA365 (2 outputs, newer driver)**: init order differs slightly: `a1`(out0) `a4`(out0) `a1`(out1, returned
  0 bytes) **then immediately** `a5`, `a2`, `a3`, `40 23` (#102–#108) during init, then `b3`, `88`, `1c`x2, `31`,
  `89`x5, `87`x2, `40 24 byte0=0` (#134).
  1080p monitor plugged into **output 1**: INT dw4=0x02000000 (#136) -> `87` polls -> `c0 80 0000 0001 128`
  (#158, wIndex=1) -> `40 12 0001 0000 32` (#160, wValue=1) -> `40 03 0001 0001` (#162) -> first bulk (#164,
  JPEG video) -> `40 24 byte0=1` (#168) -> `40 1d 0100 0100/0200/0400` (#174/#182/#184, wValue=0x0100 = output 1)
  -> `40 1c 0102` (#186).
  4K plugged into output 0 (#1944…): `c0 80 0000/0080 0000` -> `40 12 0000` 4K30 (#1970) -> `40 03 0000 0001`
  -> `40 24 byte0=1` -> `40 1c 0100` (LUT1 off) -> `1d`x3 out1 -> `1c 0102` -> `1d`x3 out0 -> `1c 0002`.
  Unplug 1080p (output 1, #5468 dw4=0x02000000): after 3 s of `87` polling: `40 03 0001 0000` (#5488, disable
  out1), `40 03 0000 0000` (#5490, disable out0), `40 12 0000` **1080p** (#5492, Windows moved the 4K panel to
  1920x1080), `40 03 0000 0001` (#5494), `40 24 01`, `40 1c 0000`, `40 1d` x3, `40 1c 0002`.
  Unplug last monitor (#6158): `40 03 0000 0000` (#6176), `40 24 01…` then `40 24 00…`.

### 2.3 Meaning summary of every vendor request seen

| bmRT/bReq | wValue | wIndex | wLength | Meaning (status) |
|---|---|---|---|---|
| c0/b0 | 0 | field 0..5 | 4/4/4/16/4/8 | adapter info (known) |
| c0/b1 | 0 | session (0 video, 3 audio) | 132 | session info: u16 vid, u16 pid, 64 B UTF-16 name, then type-specific (video: same as B3@80, + first mode record; audio: … + A5 descriptor) |
| c0/b3 | 0 | 0 | 112 | "DISP" config blob (u32 'DISP', u32 0x8b0, …, @12 vid/pid, @16 name, @80 ver=1, @84 func, @88 disp0 caps (byte1 = mode count), @92 disp1 caps, @96 intf) |
| c0/b4 | 0 | 0 | 4 | unknown, returns 0 |
| c0/cc | 1 | 0 | 104 | STALLs on both devices |
| c0/88 | 0 | 0 | 1 | VRAM MB (0x3a = 58) |
| c0/89 | output | byte offset | ≤512 | chip mode table, 32-byte records (same layout as 0x12) |
| c0/87 | output | 0 | 1 | connector status 0/1 |
| c0/80 | byte offset (0, 0x80) | **output** | 128 | EDID block |
| c0/a1 | 0 | output | 16 | unknown per-output info |
| c0/a2 | 0 | 0 | 16 | unknown |
| c0/a3 / 40/23 | 0 | 0 | 40 | read/write 40-byte block (unknown; audio-related by context) |
| c0/a4 / 40/24 | 0 | 0 (out?) | 16 | read/write audio state: byte0 enable, dw2 = 9600, byte14 = 2 |
| c0/a5 | 0 | 0 | 32 | audio capability (48 kHz, 16-bit, 2 ch) |
| 40/12 | output | 0 | 32 | set mode (§3) |
| 40/03 | output | 1/0 | 0 | output enable/disable |
| 40/1c | (output<<8) \| state | 0 | 0 | LUT (gamma) control: 0 = off/bypass, 2 = enabled (used after 1d uploads) |
| 40/1d | output<<8 | 0x100 / 0x200 / 0x400 | 256 | LUT upload for one channel (bit 8/9/10 selects the channel), 256 x u8 |
| 40/31 | 0 | 0 | 0 | unknown, sent once at init |

---------------------------------------------------------------------------------------------------------------

## 3. 0x12 "set video mode" – definitive field layout

All three distinct 0x12 payloads seen, matched against the EDID detailed timing descriptor actually read:

**1925 #144** EDID (#140) DTD0: 1920x1080, pclk 148.50 MHz, htotal 2200, hfp 88, hsw 44, hbp 148, vtotal 1125,
vfp 4, vsw 5, vbp 36, digital separate sync, H+ V+.
```
14 44 02 00 | 3c 00 | 98 08 | 80 07 | d8 07 | 2c 00 | 65 04 | 38 04 | 3c 04 | 05 00 | bb 02 | e8 03 | 1d | 01 | 01 | 01 | 00 | 00
148500      | 60    | 2200  | 1920  | 2008  | 44    | 1125  | 1080  | 1084  | 5     | 699   | 1000  | 29 | x4 | H+ | V+ | 0  | 0
```
**1928 #144 / JUA365 #1970** EDID DTD0: 3840x2160, 297.00 MHz, htotal 4400, hfp 176, hsw 88, hbp 296, vtotal 2250,
vfp 8, vsw 10, vbp 72, H+ V+ (monitor "HDP-V104").
```
28 88 04 00 | 1e 00 | 30 11 | 00 0f | b0 0f | 58 00 | ca 08 | 70 08 | 78 08 | 0a 00 | bb 02 | e8 03 | 1d | 03 | 01 | 01 | 00 | 00
297000      | 30    | 4400  | 3840  | 4016  | 88    | 2250  | 2160  | 2168  | 10    | 699   | 1000  | 29 | x8 | H+ | V+ | 0  | 0
```
JUA365 #160 (output 1) and #5492 (output 0): identical bytes to the 1080p one above.

| Off | Size | Field | Units / derivation (verified) |
|---|---|---|---|
| 0 | u32 | pixel clock | **kHz** (EDID pclk*10 kHz -> 148500, 297000) |
| 4 | u16 | refresh | integer Hz (60, 30) |
| 6 | u16 | htotal | pixels = hactive + hblank |
| 8 | u16 | hactive | pixels |
| 10 | u16 | **hsync start** | = hactive + hfront porch (2008 = 1920+88; 4016 = 3840+176) |
| 12 | u16 | hsync width | pixels (44, 88) |
| 14 | u16 | vtotal | lines |
| 16 | u16 | vactive | lines |
| 18 | u16 | **vsync start** | = vactive + vfront porch (1084 = 1080+4; 2168 = 2160+8) |
| 20 | u16 | vsync width | lines (5, 10) |
| 22 | u16 | PLL P (fractional numerator) | |
| 24 | u16 | PLL Q (fractional denominator) | always 1000 in all 66 table entries + 3 set-modes |
| 26 | u8 | PLL N (integer) | |
| 27 | u8 | PLL post-multiplier bits | bit1 = x2, bit0 = x4 -> 0:x1, 2:x2, 1:x4, 3:x8 |
| 28 | u8 | hsync polarity | **1 = positive**, 0 = negative |
| 29 | u8 | vsync polarity | 1 = positive, 0 = negative |
| 30 | u8 | "reduced blanking"? | 0 in every set-mode; 1 in the chip table for 1600x900RB, 2560x1440RB, 2560x1600RB and the three 4K CEA modes (driver sends 0 for 4K30) |
| 31 | u8 | flags | 0 in set-modes; 0x02 in table for 1360x768 and 1680x1050 (dissector: bit0 "custom vs standard timing") |

Polarity semantics proven from the chip mode table (`out/modes1925.txt`): 640x480@60 VGA (-H -V) has 00 00;
1280x768 CVT (-H +V) has 00 01; 1600x900/2560x1440 CVT-RB (+H -V) have 01 00; CEA 1080p/4K (+H +V) have 01 01.

**PLL formula** (40 MHz reference because hardware platform = 1 "Super Lite"; "Lite" = 48 MHz per notes):
`f_pix = (N + P/Q) * 40 MHz * mult / 32`, i.e. VCO = (N + P/Q) * 40 MHz in [800, 1600] MHz, divided by
32/16/8/4. Verified on every one of the 66 table entries (e.g. 640x480: N=20 P=140 mult 1 -> 25.175 MHz;
800x600@72: N=20 P=0 mult x2 -> 50.0 MHz; 1080p: N=29 P=699 x4 -> 148.495 MHz; 4K30: N=29 P=699 x8 -> 296.99 MHz).
Recipe that reproduces the driver/firmware values: pick mult in {1,2,4,8} so VCO = pclk*32/mult lies in
800–1600 MHz, `N = floor(VCO/40MHz)`, `P = floor((VCO/40MHz − N)*1000)` (truncation: 29.7 -> 699, 24.17 -> 169), Q = 1000.

The same 32-byte record format is used by the 0xC0/0x89 mode list (36 entries for output 0 incl. 2560x1080,
2560x1440, 2560x1600, 4K24/25/30; 30 entries for output 1, max 2048x1152) — full decode in `out/modes1925.txt`.

**0x23 (40 bytes)**: only one value ever written:
`03000000 00000000 1f000000 1f000000 0f000000 0f000000 0f000000 0f000000 0f000000 0f000000`
(10 x u32). Read counterpart 0xA3 returns `ff000000 00000000 0f000000 x8` on a fresh device. Not decodable from
the captures (no variation, no video effect); sent once per session before audio is used.

**0x24 (16 bytes)**: `EE000000 00000000 80250000 00000200` where byte0 = audio enable (1 sent right after a mode
set / when the audio stream starts, 0 ≈1.2–1.7 s later), dw2 = 0x2580 = 9600 = size of the first audio bulk
payload, byte14 = 2 (channels). Read counterpart 0xA4.

EDIDs: 1925 #140 "Linux FHD" (`00ffffffffffff0031d8…`, no extension). 1928 #138/#140 "HDP-V104" + CEA
extension (VICs 1,2,3,5,6,7,16–22,31,4). JUA365 #158 (out1) = the "Linux FHD" EDID, #1964/#1966 (out0) = HDP-V104.

---------------------------------------------------------------------------------------------------------------

## 4. Bulk OUT stream (EP 0x02)

### 4.1 Framing: 32-byte "select session" selector + one data URB

Every data URB is preceded by its own 32-byte selector URB (separate bulk transfers). 8 x u32 LE:

| Off | Field | Video (session 0) | Audio (session 3) | Rect-DMA (session 7) |
|---|---|---|---|---|
| 0 | session | 0 | 3 | 7 |
| 4 | total payload length (whole object incl. 48-B video header) | e.g. 0x005eec30 = 6220848 | 9600 / 1920 | total rect bytes |
| 8 | device destination address of payload byte 0 | buffer addr − 0x30 (raw) or JPEG ring addr | 0 | plane-A dst addr |
| 12 | length of the data URB that follows | ≤ 102400 | = total | plane-B dst addr (!) |
| 16 | offset of this fragment within the payload | 0, 0x19000, … | 0 | pitches: u16 A, u16 B |
| 20 | **more-fragments flag** | 1 on every fragment except the last (0) | 0 | u16 width-bytes, u16 plane-A lines |
| 24, 28 | 0 | 0 | 0 | 0 |

Real examples (1925): `#158 00000000 30ec5e00 30000000 00900100 00000000 01000000 0 0` (frame 1, frag 0),
`#442 00000000 30ec5e00 30000000 30f00000 00fc5d00 00000000 0 0` (last fragment, 61488 B at 0x5dfc00),
`#150 03000000 80250000 00000000 80250000 0 0 0 0` (audio 9600 B), `#154 03000000 80070000 0 80070000 0…` (audio 1920 B).

Fragmentation of a video object (1925, frame 1 = sel #158 … data #444, 65 fragments): the payload is cut into
**1 047 552-byte (0xFFC00 = 1023 KiB) blocks, each sent as 10 x 102400 + 1 x 23552** (offsets 0, 0x19000, …,
0xFA000 [23552] , 0xFFC00, …), last fragment = remainder (61488). The same 102400/23552 pattern is used for 4K
NV12/RGB objects; small JPEG objects are simply 102400-byte pieces plus a remainder (e.g. 228320 = 2x102400 +
23520, JUA365 sel #1054…#1064; objects ≤102400 go as a single fragment with more-flag 0, e.g. #164/#166). Audio selector+data pairs (session 3)
are **interleaved between video fragments** (e.g. #172/#174, #210/#212). A Linux driver can almost certainly
use other fragment sizes (the selector carries offset/length), but 102400 is the proven-safe maximum for
session 0. Session 7 sends the whole rect (up to 725 760 B, #3750) in one data URB.

Throughput: 102400-byte URBs complete every ≈0.6–0.7 ms (≈150 MB/s); whole 1080p RGB frame 49 ms median
(127 MB/s), 4K RGB 226 ms (110 MB/s), 4K NV12 73–101 ms.

### 4.2 Video object header (first 48 bytes of the session-0 payload)

12 x u32 LE. Real values:

```
1925 #160 (1080p RGB):  03000000 00ec5e00 01000000 09000000 80160000 60000000 60000000 00000000 09000000 0 0 0
1928 #3590 (4K NV12):   03000000 00d8bd00 04000000 06000000 000f000f 30000000 30907e00 30000000 06000000 0 0 0
JUA365 #166 (JPEG out1):04000000 b0070100 01000000 06000000 80078007 30045002 30e46f02 00000000 0d000000 0 0 0
JUA365 #296 (JPEG rect):07000000 b02f0000 09000000 06000000 80073800 80078007 f056b302 f036c402 00000000 0d000000 0 0
```

| Off | Full frame (type 3/4) | Rect (type 7) |
|---|---|---|
| 0 | **type: 3 = full frame for output 0, 4 = full frame for output 1** (JUA365: out1 1080p frames are all type 4, out0 4K/1080p frames type 3; JCD543 single output: type 3) | 7 = partial rectangle |
| 4 | byte length after the 48-byte header (pixel bytes, or JPEG length incl. zero padding) | same |
| 8 | sequence number (1, 2, 3 … shared across outputs, echoed by the interrupt EP when done) | same |
| 12 | **scan-out framebuffer format: 9 = 24-bit BGR (“RGB888”), 6 = NV12** | 6 |
| 16 | u16 pitch0, u16 pitch1 (bytes): RGB 1080p `0x1680,0` (5760), RGB 4K `0x2d00,0` (11520), NV12 `w,w` (3840,3840 / 1920,1920) | u16 rect width px, u16 rect height px |
| 20 | plane-0 (Y or RGB) address in device memory | u16 pitchY, u16 pitchUV |
| 24 | plane-1 (UV) address (RGB: = plane-0 addr) | Y address of rect top-left |
| 28 | RGB: 0; raw NV12: = plane-0 addr; JPEG: 0 | UV address of rect top-left |
| 32 | **source encoding: 9 = raw RGB, 6 = raw NV12, 0x0d = JPEG** | 0 |
| 36 | 0 | 0x0d |
| 40, 44 | 0 (one JUA365 frame, #944, had 0x80000000 at @44) | 0 |

Buffer management (all addresses are device-memory byte addresses):
* Raw formats: the selector destination = plane-0 address − 0x30, so the header lands immediately before the
  pixels and the pixels land at plane-0. **Triple buffering**, buffers rotate per frame:
  1080p RGB plane-0 = 0x60, 0xc555c0, 0x18aab20 (spacing 0xc55560 = 12 932 448 B ≈ 4K NV12 size);
  4K NV12 at 0x30 / 0xc55590 / 0x18aaaf0 with UV = Y + 3840*2160. (The 1928 capture first sent three 4K **RGB**
  frames, 24.9 MB each, into those same overlapping slots, then switched to NV12 from seq 4 on.)
* JPEG: selector dest is a **ring buffer** starting at 0x3000000; each object is placed at previous dest +
  previous length (32-byte aligned, e.g. #164 0x3000000, #170 0x30107e0), wrapping at ≈0x39cxxxx back to
  0x3200000. The decoded image goes into the NV12 triple buffer named by @20/@24 (out1 1080p: Y 0x2500430 /
  0x29556f0 / 0x2daa9b0, UV = Y + 1920*1088 — height rounded up to 16).
* Type-7 rects (and session-7 rects, below) patch **the buffer that was sent in the most recent full frame**
  (e.g. #294 writes into 0x29556f0, the buffer of frame seq 8; rect at y=1024, x=0, 1920x56).

### 4.3 Pixel payload formats (definitive)

1. **Raw 24-bpp, byte order B,G,R** (format 9). Proven by rendering frame seq 11 (`s1925/v0011_f3480.bin`) both
   ways: as R,G,B the Windows 10 wallpaper is orange, as **B,G,R it is the correct blue** (`out/v11_asbgr.png`).
   = DRM_FORMAT_RGB888 (little-endian 0xRRGGBB packed). Stride = width*3 (5760 for 1920; no padding),
   top-down, **full frame** (6220800 + 48 = 6220848 bytes per frame). Used by the JCD543 driver at 1080p.
2. **Raw NV12** (format 6, encoding 6): Y plane w*h bytes (pitch w) followed directly by interleaved
   **U,V** (Cb first) plane w*h/2 bytes; 4K payload = 12 441 600 B. Verified by rendering
   `s1928/v0004_f3588.bin` (`out/nv12_uv.png`, correct colours with Cb first).
3. **JPEG** (encoding 0x0d, JUA365 driver): a complete baseline JFIF file (`FFD8 FFE0 … JFIF`, COM "Intel(R) IPP
   JPEG encoder [7.1.37466]"), SOF0 8-bit, **3 components with IDs 0,1,2, sampling 0x22/0x11/0x11 (4:2:0)**,
   2 DQT, 4 DHT, **DRI = 1 (restart marker after every MCU)**, followed by 1–2 KB of zero padding so the object
   length is a multiple of 32. Full-frame JPEGs are 1920x1080 or 3840x2160; type-7 JPEGs are MCU-aligned rects
   (seen: 1920x56, 1728x56 @x=128, 96x56, 32x800, 224x1080). 1080p JPEGs are 67–370 KB.
4. **Session 7 raw rect DMA** (JCD543 driver, 21 instances in 1925, e.g. sel #2422 / data #2424):
   selector `07000000 c02a0000 a094e401 a0ebe701 80168016 c0002600 0 0`:
   total 10944, dst A 0x1e494a0, dst B 0x1e7eba0, pitch A = pitch B = 5760, width = 0xc0 = 192 bytes (64 px),
   lines A = 0x26 = 38. The data (no header) is **38 + 19 = 57 rows of 192 bytes, BGR**; I verified byte-exact
   against the full frame (rows y=1023…1079, x=0, all 57 rows equal; #3746 clock area x=1824 48/57 rows equal,
   the clock changed). The engine is clearly a 2-plane (NV12-style) copier: h lines to dst A, h/2 lines to dst B;
   for RGB the driver sets h = rows*2/3 and B = A + h*pitch so the two planes are contiguous. Total = 1.5*w*h.

### 4.4 Frame timing / fps

The Windows driver only sends on damage; there is no periodic refresh (gaps of seconds between frames are normal,
the device keeps scanning out the last buffer).
* 1925 (1080p RGB): 11 full frames; back-to-back intervals 40–77 ms (median 58.6 ms ≈ 17 fps), each frame takes
  ≈49 ms on the wire — bandwidth-bound at ≈20 fps max for raw 1080p RGB.
* 1928 (4K): RGB frames ≈226 ms each (≈4 fps); NV12 ≈73 ms.
* JUA365 (JPEG): median interval 21.5 ms, e.g. 14 frames in 0.293 s at #1226–#1422 (≈48 fps); 4K NV12 raw frames
  ≈100 ms, alternating with 1080p JPEGs for the other output.
* Audio (session 3) when enabled: one 9600-byte zero buffer, then 1920 bytes (10 ms of 48 kHz s16 stereo) every
  ≈10 ms, interleaved with video.

---------------------------------------------------------------------------------------------------------------

## 5. Interrupt endpoint (EP 0x83, 64-byte packets, 16 x u32 LE)

Observed packet kinds:

| dw0 type | dw3 | dw4 | dw8 | Meaning | Examples |
|---|---|---|---|---|---|
| 0x24 | 0 | 0x01000000 | 0 | first packet after driver load (combined status) | 1925 #70 |
| 0x04 | 0 | **0x01000000** | 0 | **hot-plug change on connector 0** | 1925 #110 (plug), JUA365 #1944 (plug 4K), #6158 (unplug) |
| 0x04 | 0 | **0x02000000** | 0 | **hot-plug change on connector 1** | JUA365 #136 (plug), #5468 (unplug) |
| 0x20 | 0 | 0 | connector state bits | current state, sent ~1–50 ms after a change and occasionally later | see below |
| 0x04 | **seq** | **0x04000000** | 0 | **frame done**: dw3 = sequence number from the video header @8 of the object just completed | 1925 #446 (seq 1) … #3742 (seq 11) |

dw8 in type-0x20 packets: bit 25 (0x02000000) = connector 0 connected, bit 26 (0x04000000) = connector 1
connected; JUA365 additionally always has bits 24 and 30 set: 0x41000000 none, 0x45000000 out1 only (#142),
0x47000000 both (#1948), 0x43000000 out0 only (#5474), 0x41000000 none (#6164). JCD543: 0x02000000 (#116).

The driver reacts to a hot-plug packet by reading `c0 87` for both outputs, then polls `c0 87` once per second
for ~2–3 s before reading the EDID and setting the mode (plug) or disabling the outputs (unplug).
Frame-done packets are emitted for full frames and type-7 rects (JUA365 #980–#1028 ack seq 14–22, all type 7);
the session-7 DMA in 1925 produced no ack. Some acks are missing in the capture when the host had no interrupt
URB queued (JUA365 seq 3–11).

---------------------------------------------------------------------------------------------------------------

## 6. Minimal bring-up recipe implied by the captures (single output 0, raw RGB)

1. SET_CONFIGURATION 1 (interface 0, alt 0); start polling EP 0x83 with 64-byte URBs.
2. `c0 b0` fields 0–5, `c0 b1` session 0, `c0 b3`, `c0 88`, `c0 89` mode tables, `40 1c 0000` / `40 1c 0100`.
3. On connect (`c0 87 0000` = 1): `c0 80 0000 0000 128` (+ `0080` if EDID byte 126 > 0).
4. `40 12 0000 0000 32` with the §3 record, then `40 03 0000 0001`.
5. Optionally `40 1d 0000 0100/0200/0400` identity LUTs then `40 1c 0002` (Windows does it; probably optional).
6. Bulk OUT: for each ≤102400-byte fragment send selector `{0, 48+w*h*3, bufaddr-0x30, fraglen, fragoff, more, 0, 0}`
   then the data; payload = header `{3, w*h*3, seq, 9, pitch=w*3, bufaddr, bufaddr, 0, 9, 0, 0, 0}` + BGR pixels.
   Rotate bufaddr among 0x60, 0xc555c0, 0x18aab20 (or any non-overlapping region of the 58 MB VRAM) and wait for
   the interrupt `type 4, dw4 0x04000000, dw3 = seq` before reusing a buffer.
For 4K use NV12 (format 6) — raw RGB 4K does not fit the 3-buffer layout and runs at ≈4 fps.
