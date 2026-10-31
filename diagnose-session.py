#!/usr/bin/env python3
"""Print text diagnostics; never export fingerprint images or templates."""
import argparse
import hashlib
import math
from pathlib import Path
import re
import sys
p=argparse.ArgumentParser()
p.add_argument('session',type=Path)
a=p.parse_args()
session=a.session.resolve(strict=True)
try:
    frames={}
    all_paths=sorted(session.glob('enroll-*.pgm'))
    all_paths += [session/('{}-{}.pgm'.format(k,n)) for k in ('same','different') for n in range(1,4)]
    digests={}
    for path in all_paths:
        data=path.read_bytes()
        header=b'P5\n96 96\n255\n'
        if not data.startswith(header) or len(data)!=len(header)+9216:
            print('INVALID_FRAME',path.name); continue
        pixels=data[len(header):]
        digest=hashlib.sha256(pixels).digest()
        digests.setdefault(digest,[]).append(path.name)
        # Same center crop as engine; only aggregate statistics are printed.
        crop=[pixels[y*96+x] for y in range(8,88) for x in range(16,80)]
        mean=sum(crop)/len(crop)
        centered=[x-mean for x in crop]
        norm=math.sqrt(sum(x*x for x in centered))
        frames[path.name]=(centered,norm)
        if not path.name.startswith('enroll-'):
            print('{}: min={} max={} mean={:.2f} std={:.2f}'.format(
                path.name,min(crop),max(crop),mean,norm/math.sqrt(len(crop))))
    duplicates=[names for names in digests.values() if len(names)>1]
    print('EXACT_DUPLICATE_GROUPS:',duplicates if duplicates else 'none')
    tests=[name for name in frames if not name.startswith('enroll-')]
    print('Center-crop pixel correlations (diagnostic only, not biometric scores):')
    for i,left in enumerate(tests):
        for right in tests[i+1:]:
            v,n=frames[left]; w,m=frames[right]
            corr=sum(x*y for x,y in zip(v,w))/(n*m) if n and m else float('nan')
            print('{} / {}: {:.5f}'.format(left,right,corr))
    # Most recent corrected replay logs; include enrollment diagnostics too.
    replays=sorted(session.glob('replay-*-different-1.log'),key=lambda x:x.stat().st_mtime)
    logs=[session/'engine-06-enroll.log']
    if replays:
        prefix=replays[-1].name.rsplit('-different-1.log',1)[0]
        logs += sorted(session.glob(prefix+'-*.log'))
    else:
        logs += sorted(session.glob('engine-*-verify.log'))
    for log in logs:
        if not log.is_file():continue
        print('\nLOG:',log.name)
        text=log.read_text(errors='replace')
        entries=re.sub(r'(\[Engine\]|\[storage\]|\[compat\])', r'\n\1', text).splitlines()
        for entry in entries:
            if re.search(r'Verify|verify return|score|match|GetCurrentRecord|QueryBySubject|FirstRecord|AddRecord|HRESULT|ENROLL_COMPLETE|CommitEnrollment|GetEnrollmentStatus',entry,re.I):
                print(entry.strip())
except PermissionError:
    sys.exit('請在主機使用 sudo python3 執行；不需修改資料權限。')
