#!/usr/bin/env python3
"""Extract firmware DATA from ELF64 without running the x86 library."""
import os
import struct
import sys
with open(sys.argv[1], 'rb') as stream:
    data = stream.read()
if data[:6] != b'\x7fELF\x02\x01':
    sys.exit('Expected little-endian ELF64')
offset = struct.unpack_from('<Q', data, 40)[0]
stride, count = struct.unpack_from('<HH', data, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset+i*stride)
            for i in range(count)]
for section in sections:
    if section[1] not in (2, 11):
        continue
    strings = sections[section[6]]
    names = data[strings[4]:strings[4]+strings[5]]
    if section[9] < 24:
        continue
    for pos in range(section[4], section[4]+section[5], section[9]):
        name, info, other, index, addr, size = struct.unpack_from('<IBBHQQ', data, pos)
        if names[name:].split(b'\0', 1)[0] != b'FOCALFP_9348_FW_APP':
            continue
        if not 0 < index < count or not 0 < size <= 65536:
            sys.exit('Invalid firmware symbol')
        target = sections[index]
        start = target[4] + addr - target[3]
        if target[1] == 8 or not target[4] <= start <= start+size <= target[4]+target[5] or start+size > len(data):
            sys.exit('Invalid firmware bounds')
        with open(sys.argv[2], 'xb') as output:
            output.write(data[start:start+size])
        print('Extracted {} firmware bytes (data only)'.format(size))
        sys.exit(0)
sys.exit('Firmware symbol not found')
