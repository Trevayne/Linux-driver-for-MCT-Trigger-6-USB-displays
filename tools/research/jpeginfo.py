# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys, struct, glob, os
for fn in sorted(glob.glob(sys.argv[1]+'/v*.bin')):
    b=open(fn,'rb').read(); p=b[48:]
    if p[:2]!=b'\xff\xd8': continue
    h=struct.unpack('<12I', b[:48])
    i=2; info=[]
    while i<len(p):
        if p[i]!=0xff: info.append(f'?@{i}'); break
        m=p[i+1]
        if m==0xd9: info.append(f'EOI@{i}'); break
        L=struct.unpack('>H',p[i+2:i+4])[0]
        if m in (0xc0,0xc1,0xc2):
            prec,hh,ww,nc=struct.unpack('>BHHB',p[i+4:i+10])
            comps=[(p[i+10+3*k],hex(p[i+11+3*k]),p[i+12+3*k]) for k in range(nc)]
            info.append(f'SOF{m-0xc0} {ww}x{hh} comps={comps}')
        elif m==0xdd: info.append(f'DRI {struct.unpack(">H",p[i+4:i+6])[0]}')
        elif m==0xdb: info.append(f'DQT L={L}')
        elif m==0xda:
            # skip entropy data
            j=i+2+L
            k=p.find(b'\xff\xd9', j)
            info.append(f'SOS..EOI@{k}')
            i=k; continue
        else: info.append(f'{m:02x} L={L}')
        i+=2+L
    eoi=p.rfind(b'\xff\xd9')
    print(os.path.basename(fn), 'type',h[0],'hdrlen',h[1],'paylen',len(p),'EOI end',eoi+2,'pad',len(p)-eoi-2, 'wh16' , hex(h[4]) if h[0]==7 else '', ' '.join(info))
