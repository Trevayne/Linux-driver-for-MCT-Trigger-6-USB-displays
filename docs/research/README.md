# Research notes

Raw material behind docs/PROTOCOL.md, kept so that work can continue on any
machine. Everything here is derived from public sources; nothing is copied
from MCT's proprietary Windows binaries.

| File | Contents |
|---|---|
| `capture-analysis.md` | Ground truth from the Windows-driver USB captures in [cyrozap/mct-usb-display-adapter-re](https://github.com/cyrozap/mct-usb-display-adapter-re) (`captures/*.pcapng.gz`): descriptors, control sequence, timing layout, PLL formula, bulk framing, frame formats, interrupt packets. Frame numbers are cited throughout. |
| `prior-driver-protocol.md` | The protocol as implemented by the experimental [RL-Charles/jcd543-mct-t6-linux-driver](https://github.com/RL-Charles/jcd543-mct-t6-linux-driver), with its recorded hardware failures. |
| `windows-captures/ctrl-*.txt` | Every control transfer in each capture, decoded. |
| `windows-captures/modes*.txt` | EDIDs, set-mode records and the chips' full timing tables, decoded. |
| `windows-captures/sess*.txt` | Bulk session selectors and video headers. |

The scripts that produced these are in `tools/research/` (stdlib-only Python;
`usbpcap.py` parses pcapng/usbmon and the rest build on it). Reassembled frame
payloads and rendered PNGs were not kept: they are large, and can be
regenerated from the public captures with those scripts. The same parser
works on usbmon captures taken on Linux, for comparing our driver's traffic
against Windows'.
