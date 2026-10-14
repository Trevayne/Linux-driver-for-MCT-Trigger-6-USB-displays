import sys, struct, glob, os
for fn in sorted(glob.glob(sys.argv[1]+'/v*.bin')):
    b=open(fn,'rb').read()
    h=struct.unpack('<12I', b[:48])
    p=b[48:]
    tail=p[-2:].hex()
    print(os.path.basename(fn), 'type',h[0],'len',h[1],'seq',h[2],'fmt',h[3], 'w16@16', [hex(x) for x in h[4:10]], 'payload0', p[:12].hex(), 'tail', tail, 'jpeg' if p[:2]==b'\xff\xd8' else '')
