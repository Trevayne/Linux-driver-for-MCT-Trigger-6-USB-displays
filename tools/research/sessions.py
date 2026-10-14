# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, struct, os, pickle
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
path = sys.argv[2]; outdir = sys.argv[3]; verbose = len(sys.argv) > 4
os.makedirs(outdir, exist_ok=True)
t0=None
pending=None  # selector
cur = {}  # session -> dict(buf, frames, sel list)
events=[]
vidx=0
for p in usbmon(path):
    if t0 is None: t0=p['ts']
    if not (p['xfer']=='BULK' and p['type']=='S'): continue
    d=p['data']; t=p['ts']-t0
    if pending is None:
        if p['length']!=32: print('unexpected non-selector', p['frame'], p['length']); continue
        sel=struct.unpack('<8I', d[:32])
        pending=(p['frame'], t, sel, [])
        continue
    sf, st, sel, _ = pending
    sess, plen, dest, flen, foff, f5, f6, f7 = sel
    if sess==7:
        pending[3].append((p['frame'], p['length'], p['lencap'], bytes(d[:64])))
        got=sum(x[1] for x in pending[3])
        if got>=plen:
            print(f"DMA sel#{sf} t={st:.6f} sel={bytes(struct.pack('<8I',*sel)).hex()} urbs={[(x[0],x[1],x[2]) for x in pending[3]]}")
            print('   first data', pending[3][0][3].hex())
            pending=None
        continue
    pending=None
    if p['length']!=flen: print('len mismatch', p['frame'], p['length'], flen)
    if p['lencap']<p['length']: print('truncated data', p['frame'])
    events.append((sf, p['frame'], st, sess, plen, dest, flen, foff, f5, f6, f7))
    if verbose: print(f"sel#{sf} data#{p['frame']} t={st:.6f} sess={sess} plen={plen} dest={dest:#x} flen={flen} foff={foff} f5={f5:#x} f6={f6:#x} f7={f7:#x}")
    if sess==0:
        c=cur.get(0)
        if foff==0:
            c={'buf':bytearray(), 'first':sf, 't':st, 'plen':plen, 'nfrag':0, 'f5':f5}
            cur[0]=c
        if c is None or len(c['buf'])!=foff: print('offset gap', sf, foff, None if c is None else len(c['buf'])); continue
        c['buf']+=d[:flen]; c['nfrag']+=1
        if len(c['buf'])>=plen:
            vidx+=1
            fn=f"{outdir}/v{vidx:04d}_f{c['first']}.bin"
            open(fn,'wb').write(c['buf'])
            print(f"VIDEO {vidx} sel#{c['first']}..#{p['frame']} t={c['t']:.6f}..{st:.6f} plen={plen} nfrag={c['nfrag']} f5={c['f5']} hdr={bytes(c['buf'][:48]).hex()}")
            cur[0]=None
pickle.dump(events, open(f"{outdir}/events.pkl",'wb'))
