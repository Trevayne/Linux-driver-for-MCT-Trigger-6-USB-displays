# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, struct
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
path = sys.argv[2]; n = int(sys.argv[3]); start = int(sys.argv[4]) if len(sys.argv)>4 else 0
t0=None; i=0
for p in usbmon(path):
    if t0 is None: t0=p['ts']
    if p['xfer']=='BULK' and p['type']=='S':
        i+=1
        if i<=start: continue
        d=p['data']
        print(f"#{p['frame']:6d} t={p['ts']-t0:10.6f} len={p['length']:8d} cap={p['lencap']:8d} {d[:64].hex()}")
        if i>=start+n: break
