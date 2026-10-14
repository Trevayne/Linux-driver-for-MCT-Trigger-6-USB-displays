import sys
dma=open(sys.argv[1],'rb').read(); w=int(sys.argv[2]); y0=int(sys.argv[3]); xb=int(sys.argv[4]); rowstride=int(sys.argv[5]) if len(sys.argv)>6 else 5760
v=open(sys.argv[-1],'rb').read()[48:]
rows=len(dma)//w
eq=0
for r in range(rows):
    a=dma[r*w:(r+1)*w]; o=(y0+r)*5760+xb; b=v[o:o+w]
    eq+= a==b
    if r<3 or a!=b and r<60: print(r, a==b, sum(x==y for x,y in zip(a,b)), '/', w)
print('rows',rows,'equal rows',eq)
