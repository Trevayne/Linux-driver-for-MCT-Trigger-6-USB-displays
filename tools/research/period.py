# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys
d=open(sys.argv[1],'rb').read()
n=len(d)
res=[]
for P in range(3, min(12000, n//2)):
    m=sum(1 for i in range(0, n-P, 7) if d[i]==d[i+P])
    res.append((m/len(range(0,n-P,7)), P))
res.sort(reverse=True)
print(n, res[:15])
