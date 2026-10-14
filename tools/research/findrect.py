import sys
dma=open(sys.argv[1],'rb').read(); w=int(sys.argv[2])
for vf in sys.argv[3:]:
    v=open(vf,'rb').read()[48:]
    stride=5760
    rows=[dma[i:i+w] for i in range(0,len(dma)-w+1,w)]
    for ri in (0, 1, len(rows)//2, len(rows)-1):
        r=rows[ri]
        hits=[]; s=0
        while True:
            k=v.find(r,s)
            if k<0 or len(hits)>5: break
            hits.append((k//stride, (k%stride)/3)); s=k+1
        print(vf.split('/')[-1], 'row',ri,'hits(y,xpix)',hits)
