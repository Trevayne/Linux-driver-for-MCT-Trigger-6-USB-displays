# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
import sys
sys.path.insert(0, sys.argv[1])
from usbpcap import usbmon
want=set(int(x) for x in sys.argv[3].split(','))
for p in usbmon(sys.argv[2]):
    if p['frame'] in want:
        open(f"{sys.argv[4]}/frame{p['frame']}.bin",'wb').write(p['data'])
