#!/usr/bin/env python3
"""Re-evaluate existing private test frames. No USB access or new capture."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import uuid
BASE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('session',type=Path)
parser.add_argument('--internal', action='store_true', help='Audit public result against internal matcher outputs')
args=parser.parse_args()
if os.geteuid()!=0:
    sys.exit('請用 sudo python3 執行，才能讀取原有測試資料。')
os.umask(0o077)
session=args.session.resolve(strict=True)
template=session/'template.bin'
if not template.is_file():
    sys.exit('找不到 template.bin；未進行任何測試。')
images=[]
for kind in ('same','different'):
    for number in range(1,4):
        image=session/('{}-{}.pgm'.format(kind,number))
        if not image.is_file():
            sys.exit('缺少原始測試影像：{}'.format(image.name))
        images.append((kind,number,image))
run=uuid.uuid4().hex[:12]
lines=[]
for kind,number,image in images:
    log=session/('replay-{}-{}-{}.log'.format(run,kind,number))
    command=['qemu-x86_64',str(BASE/'matcher-x86_64'),
             str(BASE/'matcher-blobs/ftWbioEngineAdapter.dll'),
             'verify',str(template),str(image)]
    with log.open('xb') as stream:
        try:
            result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=120,
                    env=dict(os.environ, FT9201_INTERNAL_DIAGNOSTICS='1') if args.internal else
                    {k:v for k,v in os.environ.items() if k != 'FT9201_INTERNAL_DIAGNOSTICS'})
            code=result.returncode
        except subprocess.TimeoutExpired:
            code=124
    outcome={0:'MATCH',1:'NO_MATCH'}.get(code,'ERROR({})'.format(code))
    expected=0 if kind=='same' else 1
    line='{} {}: {} {}'.format(kind,number,outcome,'PASS' if code==expected else 'FAIL')
    lines.append(line)
    print(line,flush=True)
    # Show only the typed API return diagnostic, not raw images or templates.
    for entry in log.read_text(errors='replace').splitlines():
        marker=entry.find('[compat] Verify HRESULT=')
        if marker<0:
            marker=entry.find('[internal]')
        if marker>=0:
            print(entry[marker:],flush=True)
    print('紀錄：{}'.format(log),flush=True)
report=session/('replay-results-{}.txt'.format(run))
report.write_text('\n'.join(lines)+'\n')
print('結果：{}\n這是既有影像重測；登入設定未修改。'.format(report),flush=True)
