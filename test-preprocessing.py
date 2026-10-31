#!/usr/bin/env python3
"""Compare the original capture preprocessing with upstream's missing stretch.
Uses existing private frames and a new template. Never installs login changes.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HEADER=b'P5\n96 96\n255\n'
BASE=Path(__file__).resolve().parent

def stretch(pixels):
    lo,hi=min(pixels),max(pixels)
    return bytes((value-lo)*255//(hi-lo) for value in pixels) if hi>lo else pixels

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('session',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0:
        sys.exit('請在主機使用 sudo python3 執行。')
    session=args.session.resolve(strict=True)
    enrollment=sorted(session.glob('enroll-*.pgm'))
    tests=[(kind,n,session/('{}-{}.pgm'.format(kind,n)))
           for kind in ('same','different') for n in range(1,4)]
    paths=enrollment+[path for _,_,path in tests]
    if not enrollment or any(not p.is_file() for p in paths):
        sys.exit('缺少錄入或測試影像。')
    os.umask(0o077)
    dest=Path(tempfile.mkdtemp(prefix='preprocessing-',dir=str(session)))
    print('測試資料：{}'.format(dest),flush=True)
    changed=0
    for path in paths:
        data=path.read_bytes()
        if not data.startswith(HEADER) or len(data)!=len(HEADER)+9216:
            sys.exit('影像格式不符：'+path.name)
        pixels=data[len(HEADER):]
        normalized=stretch(pixels)
        changed+=normalized!=pixels
        with (dest/path.name).open('xb') as output:
            output.write(HEADER+normalized)
        if not path.name.startswith('enroll-'):
            print('{}: original_range={}-{} saturated_pixels={:.1f}% changed={}'.format(
                path.name,min(pixels),max(pixels),100*pixels.count(255)/len(pixels),normalized!=pixels),flush=True)
    print('對比拉伸改變了 {}/{} 張影像。'.format(changed,len(paths)),flush=True)
    if not changed:
        print('所有影像原本已涵蓋 0–255；漏掉拉伸不是本次誤判原因。',flush=True)
        return
    def engine(mode,files,logname):
        log=dest/logname
        with log.open('xb') as output:
            try:
                result=subprocess.run(['qemu-x86_64',str(BASE/'matcher-x86_64'),
                    str(BASE/'matcher-blobs/ftWbioEngineAdapter.dll'),mode]+[str(p) for p in files],
                    stdout=output,stderr=subprocess.STDOUT,timeout=120)
            except subprocess.TimeoutExpired:
                print('TIMEOUT; log={}'.format(log),flush=True)
                return 124
        print('紀錄：{}'.format(log),flush=True)
        return result.returncode
    template=dest/'normalized-template.bin'
    result=engine('enroll',[template]+[dest/p.name for p in enrollment],'enroll.log')
    if result!=0:
        print('重新錄入未成功；請貼回 enroll.log 文字，原有範本未修改。',flush=True)
        return
    results=[]
    for kind,number,path in tests:
        code=engine('verify',[template,dest/path.name],'{}-{}.log'.format(kind,number))
        outcome={0:'MATCH',1:'NO_MATCH'}.get(code,'ERROR({})'.format(code))
        line='{} {}: {} {}'.format(kind,number,outcome,
                'PASS' if code==(0 if kind=='same' else 1) else 'FAIL')
        results.append(line)
        print(line,flush=True)
    (dest/'results.txt').write_text('\n'.join(results)+'\n')
    print('這是影像處理差異測試；仍需獨立實測才能評估辨識。登入設定未修改。',flush=True)

if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError) as error:
        sys.exit(str(error))
