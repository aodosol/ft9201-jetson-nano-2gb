#!/usr/bin/env python3
"""Host-only interactive acquisition/enrollment/recognition experiment.
No PAM changes. No stored image may be used as a live authentication factor.
"""
import os
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

BASE = Path(__file__).resolve().parent

def main():
    if os.geteuid() != 0:
        sys.exit('請用 sudo python3 執行，需要開啟 USB 裝置。')
    for name in ('capture', 'firmware.bin', 'matcher-x86_64',
                 'matcher-blobs/ftWbioEngineAdapter.dll'):
        if not (BASE / name).is_file():
            sys.exit('缺少檔案：' + name)
    if not shutil.which('qemu-x86_64'):
        sys.exit('缺少 qemu-x86_64')
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path, help='Reuse existing enrollment captures')
    args = parser.parse_args()
    os.umask(0o077)
    if args.resume:
        session = args.resume.resolve(strict=True)
        if not session.is_dir():
            sys.exit('Resume path must be a directory')
    else:
        session = Path(tempfile.mkdtemp(prefix='recognition-', dir=str(BASE)))
    print('測試資料保存在 {}（只有 root 可讀取）。'.format(session), flush=True)
    print('這是辨識實驗，尚未啟用登入。Ctrl+C 可中止。', flush=True)

    def capture(label, prompt):
        image = session / (label + '.pgm')
        if image.exists():
            image = session / (label + '-' + uuid.uuid4().hex + '.pgm')
        input('\n' + prompt + '\n先將手指移開，按 Enter 開始；看到 Place finger 再放上。')
        result = subprocess.run([str(BASE/'capture'), str(BASE/'firmware.bin'), str(image)])
        if result.returncode:
            raise RuntimeError('擷取失敗（{}）。請先拔插模組再重新執行。'.format(result.returncode))
        return image

    previous = list(session.glob('engine-*-*.log'))
    counter = [max([int(p.name.split('-')[1]) for p in previous] + [0])]
    def matcher(mode, paths):
        counter[0] += 1
        log = session / ('engine-{:02d}-{}.log'.format(counter[0], mode))
        command = ['qemu-x86_64', str(BASE/'matcher-x86_64'),
                   str(BASE/'matcher-blobs/ftWbioEngineAdapter.dll'), mode]
        try:
            with log.open('xb') as output:
                result = subprocess.run(command + [str(p) for p in paths],
                                        stdout=output, stderr=subprocess.STDOUT, timeout=120)
        except subprocess.TimeoutExpired:
            raise RuntimeError('比對引擎逾時。紀錄：{}'.format(log))
        # Never dump vendor logs or biometric data. Return codes are described
        # by matcher.c: 0 success/match, 1 no match, 2 processing error.
        print('引擎紀錄：{}'.format(log), flush=True)
        return result.returncode

    images = sorted(session.glob('enroll-*.pgm'))
    template = session / 'template.bin'
    enrolled = template.is_file() and template.stat().st_size > 0
    if images:
        print('重用 {} 張已有錄入影像，不需要重新掃描。'.format(len(images)), flush=True)
    for count in (8, 12, 16, 20, 24):
        if enrolled:
            break
        if len(images) > count:
            continue
        while len(images) < count:
            number = len(images)+1
            images.append(capture('enroll-{:02d}'.format(number),
                '錄入第 {} 次：使用同一根手指，每次抬起後稍微改變接觸位置。'.format(number)))
        result = matcher('enroll', [template] + images)
        if result == 0:
            enrolled = True
            print('錄入成功，接著用全新擷取的影像測試。', flush=True)
            break
        log = session / ('engine-{:02d}-enroll.log'.format(counter[0]))
        if result != 2 or 'ENROLL_INCOMPLETE;' not in log.read_text(errors='replace'):
            raise RuntimeError('錄入引擎失敗，請貼回上述 engine 紀錄的文字內容以便診斷。')
        print('覆蓋範圍不足，繼續增加樣本。', flush=True)
    if not enrolled:
        raise RuntimeError('24 次仍未完成錄入；目前不適合接入登入，需分析引擎紀錄。')

    summary = []
    for same in (True, False):
        for number in range(1, 4):
            kind = 'same' if same else 'different'
            instruction = ('用剛才錄入的同一根手指。' if same else
                           '換成沒有錄入過的另一根手指；不要使用剛才錄入的手指。')
            image = capture('{}-{}'.format(kind, number),
                            '辨識測試 {}/3：{}'.format(number, instruction))
            result = matcher('verify', [template, image])
            if result not in (0, 1):
                raise RuntimeError('比對發生錯誤，不能視為指紋不符。請查看引擎紀錄。')
            passed = (result == 0) if same else (result == 1)
            summary.append((kind, number, result == 0, passed))
            print('{}：{}；{}'.format(kind, 'MATCH' if result == 0 else 'NO_MATCH',
                                     '符合預期' if passed else '不符合預期'), flush=True)
    report = session / 'results.txt'
    if report.exists():
        report = session / ('results-' + uuid.uuid4().hex + '.txt')
    with report.open('x') as output:
        for kind, number, matched, passed in summary:
            output.write('{} {} {} {}\n'.format(kind, number,
                'MATCH' if matched else 'NO_MATCH', 'PASS' if passed else 'FAIL'))
    print('\n測試完成。文字結果：{}'.format(report), flush=True)
    print('這六次測試不能證明安全性或辨識率；登入設定尚未修改。', flush=True)
    print('請貼回 results.txt 的文字，不需要分享指紋影像或 template.bin。', flush=True)

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\n已中止；既有測試資料保留，登入設定未修改。', file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, OSError) as error:
        print('\n測試停止：{}'.format(error), file=sys.stderr)
        sys.exit(2)
