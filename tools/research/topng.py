# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, zlib, struct
fn, w, h, order, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
sc = int(sys.argv[6]) if len(sys.argv)>6 else 4
d=open(fn,'rb').read()[48:]
stride=w*3
W=w//sc; H=h//sc
rows=[]
for y in range(H):
    r=bytearray([0])
    base=y*sc*stride
    for x in range(W):
        o=base+x*sc*3
        px=d[o:o+3]
        if order=='bgr': px=px[::-1]
        r+=px
    rows.append(bytes(r))
raw=b''.join(rows)
def chunk(t,b): return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
open(out,'wb').write(png)
