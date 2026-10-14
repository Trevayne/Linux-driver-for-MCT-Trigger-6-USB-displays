"""Minimal pcapng + USBPcap parser (no external deps)."""
import struct

def pcapng_packets(path):
    """Yield (frame_no, ts_seconds, linktype, data) for each EPB/SPB."""
    with open(path, 'rb') as f:
        buf = f.read()
    off = 0
    n = len(buf)
    endian = '<'
    ifaces = []  # (linktype, tsresol)
    frame = 0
    while off + 12 <= n:
        btype, blen = struct.unpack_from(endian + 'II', buf, off)
        if btype == 0x0A0D0D0A:
            bom = struct.unpack_from('<I', buf, off + 8)[0]
            endian = '<' if bom == 0x1A2B3C4D else '>'
            blen = struct.unpack_from(endian + 'I', buf, off + 4)[0]
            ifaces = []
        elif btype == 1:  # IDB
            lt = struct.unpack_from(endian + 'H', buf, off + 8)[0]
            tsres = 1e-6
            o = off + 16
            end = off + blen - 4
            while o + 4 <= end:
                code, ln = struct.unpack_from(endian + 'HH', buf, o)
                if code == 0:
                    break
                if code == 9:
                    v = buf[o + 4]
                    tsres = (2 ** -(v & 0x7f)) if v & 0x80 else 10 ** -v
                o += 4 + ((ln + 3) & ~3)
            ifaces.append((lt, tsres))
        elif btype == 6:  # EPB
            iid, th, tl, caplen, origlen = struct.unpack_from(endian + 'IIIII', buf, off + 8)
            frame += 1
            lt, tsres = ifaces[iid]
            ts = ((th << 32) | tl) * tsres
            yield frame, ts, lt, buf[off + 28: off + 28 + caplen], origlen
        elif btype == 3:  # SPB
            frame += 1
            origlen = struct.unpack_from(endian + 'I', buf, off + 8)[0]
            yield frame, 0.0, ifaces[0][0], buf[off + 12: off + blen - 4], origlen
        off += blen


XFER = {0: 'ISO', 1: 'INTR', 2: 'CTRL', 3: 'BULK'}


def usbpcap(path):
    """Yield dicts for USBPcap (linktype 249) packets."""
    for fr, ts, lt, d, origlen in pcapng_packets(path):
        if lt != 249 or len(d) < 27:
            continue
        hlen, irp, status, func, info, bus, dev, ep, xfer, dlen = struct.unpack_from('<HQIHBHHBBI', d, 0)
        p = dict(frame=fr, ts=ts, irp=irp, status=status, func=func, info=info,
                 bus=bus, dev=dev, ep=ep, xfer=xfer, dlen=dlen,
                 completion=bool(info & 1), stage=None)
        if xfer == 2 and hlen >= 28:
            p['stage'] = d[27]
        p['data'] = d[hlen:]
        p['caplen'] = len(d) - hlen
        yield p


XT = {0: 'ISO', 1: 'INTR', 2: 'CTRL', 3: 'BULK'}


def usbmon(path):
    """Yield dicts for Linux usbmon mmapped (linktype 220) packets."""
    for fr, ts, lt, d, origlen in pcapng_packets(path):
        if lt not in (189, 220):
            continue
        hdr = 64 if lt == 220 else 48
        (uid, typ, xt, epn, devn, busn, fsetup, fdata, tsec, tusec, status,
         length, lencap) = struct.unpack_from('<QBBBBHbbqiiII', d, 0)
        setup = d[40:48]
        if lt == 220:
            interval, start_frame, xfer_flags, ndesc = struct.unpack_from('<iiII', d, 48)
        else:
            ndesc = 0
        data = d[hdr:]
        if xt == 0 and ndesc:
            data = data[ndesc * 16:]
        yield dict(frame=fr, ts=tsec + tusec * 1e-6, id=uid, type=chr(typ), xfer=XT[xt],
                   ep=epn, dev=devn, bus=busn, setup_valid=(fsetup == 0), setup=setup,
                   status=status, length=length, lencap=lencap, data=data,
                   fdata=fdata)
