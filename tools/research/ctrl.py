import sys, struct
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
path = sys.argv[2]
maxhex = int(sys.argv[3]) if len(sys.argv) > 3 else 64
pend = {}
t0 = None
nb = 0; bulkfirst=None
for p in usbmon(path):
    if t0 is None: t0 = p['ts']
    if p['xfer'] == 'BULK':
        if p['type']=='S':
            nb += 1
            if bulkfirst is None: bulkfirst=p['frame']; print(f"#{p['frame']:6d} t={p['ts']-t0:9.6f} FIRST BULK OUT len={p['length']}")
        continue
    if p['xfer'] == 'INTR':
        if p['type']=='C':
            print(f"#{p['frame']:6d} t={p['ts']-t0:9.6f} INTR IN st={p['status']} len={p['length']} {p['data'].hex()}")
        continue
    if p['xfer'] != 'CTRL': continue
    if p['type'] == 'S':
        pend[p['id']] = p
        continue
    s = pend.pop(p['id'], None)
    if s is None: print('orphan', p['frame']); continue
    bm, br, wv, wi, wl = struct.unpack('<BBHHH', s['setup'])
    data = s['data'] if not (bm & 0x80) else p['data']
    h = data.hex()
    if len(h) > maxhex*2: h = h[:maxhex*2] + f'...(+{len(data)-maxhex})'
    print(f"#{s['frame']:6d} t={s['ts']-t0:9.6f} {bm:02x} {br:02x} wV={wv:04x} wI={wi:04x} wL={wl:4d} st={p['status']} act={p['length']} {h}")
print('bulk S count', nb)
