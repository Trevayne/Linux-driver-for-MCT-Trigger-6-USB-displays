# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import pickle, sys
ev=pickle.load(open(sys.argv[1],'rb'))
want=set(int(x) for x in sys.argv[2].split(','))
on=False; prev=None
for e in ev:
    sf, df, t, sess, plen, dest, flen, foff, f5, f6, f7 = e
    if sess==0 and foff==0: on = sf in want
    if on: print(f"sel#{sf} data#{df} t={t:.6f} sess={sess} plen={plen} dest={dest:#x} flen={flen} foff={foff:#x} end={foff+flen:#x} more={f5}" + (f" dt={1e3*(t-prev):.3f}ms" if prev else '')); prev=t
