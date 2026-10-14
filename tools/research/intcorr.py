# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, struct, glob, os
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
# video frames: from sessions output text
vids=[]
for line in open(sys.argv[3]):
    if line.startswith('VIDEO'):
        parts=line.split()
        n=int(parts[1]); rng=parts[2]; t=parts[3].split('=')[1].split('..')
        hdr=line.strip().split('hdr=')[1]
        typ=int.from_bytes(bytes.fromhex(hdr[0:8]),'little')
        last=int(rng.split('..#')[1])
        vids.append((n, float(t[1]), last, typ))
ints=[]; comp={}
t0=None
for p in usbmon(sys.argv[2]):
    if t0 is None: t0=p['ts']
    if p['xfer']=='BULK' and p['type']=='C': comp[p['id']]=(p['frame'], p['ts']-t0)
    if p['xfer']=='BULK' and p['type']=='S': last_s=p
    if p['xfer']=='INTR' and p['type']=='C':
        d=p['data']; w=struct.unpack('<16I', d[:64])
        ints.append((p['frame'], p['ts']-t0, w))
vi=0
for fr,t,w in ints:
    while vi < len(vids) and vids[vi][2] < fr: vi+=1
    prev = vids[vi-1] if vi else None
    print(f"INT #{fr} t={t:.6f} type={w[0]:#x} dw3={w[3]} dw4={w[4]:#010x} dw8={w[8]:#010x} | last video before: {prev[0] if prev else None} type {prev[3] if prev else ''} lastURB#{prev[2] if prev else ''}")
