#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
"""Regenerate t6emu_data.h from the decoded Windows captures.

Usage: gendata.py docs/research/windows-captures > tests/e2e/t6emu_data.h
"""
import re, sys
out = sys.argv[1]
modes = open(out + '/modes1925.txt').read().splitlines()
ctrl = open(out + '/ctrl-1925.txt').read().splitlines()
tables = {}
cur = None
for l in modes:
    m = re.match(r'MODELIST output (\d): (\d+) bytes = (\d+) entries', l)
    if m:
        cur = int(m.group(1)); tables[cur] = []; continue
    m = re.match(r'\s+\[\s*\d+\]\s+([0-9a-f]{64})\s+(\S+)', l)
    if m and cur is not None:
        tables[cur].append((bytes.fromhex(m.group(1)), m.group(2)))
edid = None
for l in modes:
    m = re.match(r'EDID #\d+ conn=0 off=0: ([0-9a-f]+)', l)
    if m: edid = bytes.fromhex(m.group(1))
# cross-check against raw 0x89 control reads (wValue=head, wIndex=offset)
raw = {0: {}, 1: {}}
sect = None
for l in ctrl:
    m = re.search(r' c0 (..) wV=(....) wI=(....) wL=\s*(\d+) st=0 act=(\d+) ([0-9a-f]*)', l)
    if not m: continue
    req, wv, wi = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
    data = bytes.fromhex(m.group(6))
    if req == '89': raw[wv][wi] = data
    if req == 'b3': sect = data
for h in (0, 1):
    blob = b''.join(raw[h][k] for k in sorted(raw[h]))
    tb = b''.join(e for e, _ in tables[h])
    assert blob == tb, h
assert len(tables[0]) == 36 and len(tables[1]) == 30 and len(edid) == 128 and len(sect) == 112
assert sum(edid) % 256 == 0
def arr(b, indent='\t'):
    s = []
    for i in range(0, len(b), 8):
        s.append(indent + ', '.join('0x%02x' % x for x in b[i:i+8]) + ',')
    return '\n'.join(s)
print('''/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Copyright (C) 2026 Gareth Palmer
 *
 * Trigger 6 device data for t6emu, verbatim from USB captures of MCT's
 * Windows driver talking to a real JCD543 dock (capture "1925" in
 * cyrozap/mct-usb-display-adapter-re).  Generated once from the decoded
 * captures (modes1925.txt / ctrl-1925.txt); the timing tables were checked
 * byte for byte against the raw 0x89 control reads.  Do not edit by hand.
 */
#ifndef T6EMU_DATA_H
#define T6EMU_DATA_H

#include <stdint.h>

/* 0xB3 display section header: head 0 DVO/36 timings, head 1 DAC/30. */
static const uint8_t t6_section_hdr[112] = {
%s
};

/* 0x80 EDID of the head 0 monitor: "Linux FHD", 1920x1080@60 preferred. */
static const uint8_t t6_edid_1080p[128] = {
%s
};
''' % (arr(sect), arr(edid)))
for h in (0, 1):
    name = 'DVO/HDMI' if h == 0 else 'DAC/VGA'
    print('/* 0x89 timing table, head %d (%s): %d entries of 32 bytes. */' % (h, name, len(tables[h])))
    print('static const uint8_t t6_timings_head%d[%d][32] = {' % (h, len(tables[h])))
    for e, desc in tables[h]:
        print('\t/* %s */' % desc)
        print('\t{\n%s\n\t},' % arr(e, '\t\t'))
    print('};\n')
print('#endif /* T6EMU_DATA_H */')
