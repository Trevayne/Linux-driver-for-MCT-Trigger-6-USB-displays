import pickle, sys, collections
ev=pickle.load(open(sys.argv[1],'rb'))
c=collections.Counter()
for e in ev:
    sf, df, t, sess, plen, dest, flen, foff, f5, f6, f7 = e
    last = foff+flen>=plen
    c[(sess, 'last' if last else 'notlast', f5, f6, f7)]+=1
for k,v in sorted(c.items()): print(k,v)
fl=collections.Counter(e[6] for e in ev if e[3]==0)
print('video frag lens', fl.most_common(8))
