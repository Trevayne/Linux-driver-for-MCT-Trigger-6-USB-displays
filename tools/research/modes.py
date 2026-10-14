# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, struct, re
def mode(b):
    pclk, hz, ht, ha, hss, hsw, vt, va, vss, vsw, fnum, fden, idiv, mul, hp, vp, rb, fl = struct.unpack('<IHHHHHHHHHHHBBBBBB', b)
    m = (2 if mul & 2 else 1) * (4 if mul & 1 else 1)
    pll = (fnum / fden + idiv) * m * 40000 / 32 if fden else 0
    return dict(pclk=pclk, hz=hz, ht=ht, ha=ha, hss=hss, hsw=hsw, vt=vt, va=va, vss=vss, vsw=vsw, fnum=fnum, fden=fden, idiv=idiv, mul=mul, hp=hp, vp=vp, rb=rb, fl=fl, pll_khz=round(pll, 1), refresh=round(pclk*1000/(ht*vt), 3))
def fmt(m):
    return (f"{m['ha']}x{m['va']}@{m['hz']} pclk={m['pclk']}kHz ht={m['ht']} hss={m['hss']} (hfp={m['hss']-m['ha']}) hsw={m['hsw']} (hbp={m['ht']-m['hss']-m['hsw']}) "
            f"vt={m['vt']} vss={m['vss']} (vfp={m['vss']-m['va']}) vsw={m['vsw']} (vbp={m['vt']-m['vss']-m['vsw']}) pll(P={m['fnum']},Q={m['fden']},N={m['idiv']},mul={m['mul']:#x})={m['pll_khz']}kHz "
            f"hpol={m['hp']} vpol={m['vp']} rb={m['rb']} flags={m['fl']:#x} calc_refresh={m['refresh']}")
def dtd(d):
    pclk = struct.unpack('<H', d[0:2])[0] * 10
    ha = d[2] | ((d[4] & 0xf0) << 4); hb = d[3] | ((d[4] & 0x0f) << 8)
    va = d[5] | ((d[7] & 0xf0) << 4); vb = d[6] | ((d[7] & 0x0f) << 8)
    hfp = d[8] | ((d[11] & 0xc0) << 2); hsw = d[9] | ((d[11] & 0x30) << 4)
    vfp = (d[10] >> 4) | ((d[11] & 0x0c) << 2); vsw = (d[10] & 0xf) | ((d[11] & 0x03) << 4)
    fl = d[17]
    sync = ''
    if (fl >> 3) & 3 == 3: sync = f"digital-separate hsync{'+' if fl & 2 else '-'} vsync{'+' if fl & 4 else '-'}"
    return f"{ha}x{va} pclk={pclk}kHz htotal={ha+hb} hfp={hfp} hsw={hsw} hbp={hb-hfp-hsw} hss={ha+hfp} vtotal={va+vb} vfp={vfp} vsw={vsw} vbp={vb-vfp-vsw} vss={va+vfp} interlaced={fl>>7} {sync} refresh={pclk*1000/((ha+hb)*(va+vb)):.3f}"
if __name__ == '__main__':
    import sys
    sys.path.insert(0, sys.argv[1])
    from usbpcap import usbmon
    pend = {}
    modelists = {}
    for p in usbmon(sys.argv[2]):
        if p['xfer'] != 'CTRL': continue
        if p['type'] == 'S': pend[p['id']] = p; continue
        s = pend.pop(p['id'], None)
        bm, br, wv, wi, wl = struct.unpack('<BBHHH', s['setup'])
        if bm == 0xc0 and br == 0x80:
            e = p['data']
            print(f"EDID #{s['frame']} conn={wi} off={wv}: {e.hex()}")
            if wv == 0:
                print('  mfg', e[8:10].hex(), 'product', e[10:12].hex())
                for k in range(4):
                    d = e[54 + 18*k: 72 + 18*k]
                    if d[0] or d[1]: print(f'  DTD{k}:', dtd(d))
                    else: print(f'  desc{k}: tag {d[3]:#x}', d[5:18])
                print('  extensions', e[126])
            else:
                if e[0] == 2:
                    off = e[2]; i = off
                    while i + 18 <= 127 and (e[i] or e[i+1]):
                        print('  ext DTD:', dtd(e[i:i+18])); i += 18
                    # SVDs
                    j = 4
                    while j < off:
                        tag, ln = e[j] >> 5, e[j] & 31
                        if tag == 2: print('  CEA VICs', [x & 0x7f for x in e[j+1:j+1+ln]])
                        j += 1 + ln
        if bm == 0x40 and br == 0x12:
            print(f"SETMODE #{s['frame']} wValue={wv} data={s['data'].hex()}")
            print('  ', fmt(mode(s['data'][:32])))
        if bm == 0xc0 and br == 0x89:
            modelists.setdefault(wv, bytearray()).extend(p['data'])
    for out, b in modelists.items():
        print(f"MODELIST output {out}: {len(b)} bytes = {len(b)//32} entries")
        for i in range(0, len(b), 32):
            print(f'  [{i//32:2d}] {b[i:i+32].hex()}  ', fmt(mode(bytes(b[i:i+32]))))
