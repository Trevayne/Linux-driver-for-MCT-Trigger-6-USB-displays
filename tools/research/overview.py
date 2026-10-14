import sys, collections
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
path = sys.argv[2]
c = collections.Counter(); first = {}; trunc = collections.Counter(); tot=collections.Counter()
for p in usbmon(path):
    k = (p['bus'], p['dev'], hex(p['ep']), p['xfer'], p['type'])
    c[k] += 1; first.setdefault(k, p['frame'])
    tot[k]+=p['length']
    if p['lencap'] < p['length']: trunc[k] += 1
for k, v in sorted(c.items(), key=lambda x: first[x[0]]):
    print(k, v, 'first', first[k], 'bytes', tot[k], 'truncated', trunc[k])
