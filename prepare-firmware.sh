#!/usr/bin/env bash
# Download an upstream-referenced vendor package; EXTRACT ONLY, never install it.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ -s firmware.bin ]; then echo 'firmware.bin already exists'; exit 0; fi
mkdir -p vendor
curl -fL --retry 2 -o vendor/ft9201.deb 'https://github.com/mrrbrilliant/ft9201-static/raw/main/libfprint_2_2_1_90_1%2Btod1_0ubuntu120_04_2_amd64_16c6e64404f8411.deb'
dpkg-deb -x vendor/ft9201.deb vendor/extracted
mapfile -t libraries < <(find vendor/extracted -type f -name 'libfprint-2.so.2.0.0')
[ "${#libraries[@]}" -eq 1 ] || { echo 'Expected exactly one vendor library'; exit 1; }
python3 extract-fw.py "${libraries[0]}" firmware.bin
sha256sum vendor/ft9201.deb firmware.bin
