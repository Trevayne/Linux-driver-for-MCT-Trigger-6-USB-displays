import sys, zlib, struct
fn,w,h,swap,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]=='vu',sys.argv[5]
sc=8
d=open(fn,'rb').read()[48:]
Y=d[:w*h]; UV=d[w*h:]
print('total', len(d), 'Y', w*h, 'UV', len(UV), 'expected', w*h//2)
rows=[]
cl=lambda v: 0 if v<0 else 255 if v>255 else int(v)
for y in range(0,h,sc):
    r=bytearray([0])
    for x in range(0,w,sc):
        yy=Y[y*w+x]; o=(y//2)*w+(x//2)*2
        u,v=UV[o],UV[o+1]
        if swap: u,v=v,u
        c=1.164*(yy-16); r+=bytes([cl(c+1.596*(v-128)), cl(c-0.392*(u-128)-0.813*(v-128)), cl(c+2.017*(u-128))])
    rows.append(bytes(r))
W=len(range(0,w,sc)); H=len(rows)
def chunk(t,b): return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
open(out,'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))
