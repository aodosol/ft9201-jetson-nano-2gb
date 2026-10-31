#!/usr/bin/env bash
# Build an isolated, static x86 helper; no system libraries or PAM changes.
set -euo pipefail
cd -- "$(dirname -- "$0")"
for tool in x86_64-linux-gnu-gcc qemu-x86_64 cabextract curl timeout; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool"; echo 'Install on host: sudo apt install gcc-x86-64-linux-gnu libc6-dev-amd64-cross qemu-user cabextract'; exit 1; }
done
mkdir -p matcher-blobs
if [ ! -f matcher-blobs/ftWbioEngineAdapter.dll ]; then
    curl -fL --retry 2 -o matcher-blobs/vendor.cab 'https://catalog.s.download.windowsupdate.com/d/msdownload/update/driver/drvs/2023/05/fd237921-f610-43de-b77c-f1685416480b_710b4d2c8dd2e80043e371b91bebb1721b5163a0.cab'
    cabextract -q -d matcher-blobs matcher-blobs/vendor.cab
fi
[ -f matcher-blobs/ftWbioEngineAdapter.dll ] || { echo 'Matching DLL missing after extraction'; exit 1; }
sha256sum matcher-blobs/ftWbioEngineAdapter.dll
mkdir -p build
python3 - <<'PATCH'
from pathlib import Path
source = Path('upstream/src/ft_engine.c').read_text()
old = 'MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE'
if source.count(old) != 1:
    raise SystemExit('Unexpected upstream mmap reservation; review required')
# A non-fixed hint never overwrites existing mappings. The upstream exact
# address check rejects a different address. Works on pre-4.17 kernels.
source = source.replace(old, 'MAP_PRIVATE|MAP_ANONYMOUS')
source = source.replace('if(m==MAP_FAILED || m!=(void*)g_imagebase){',
    'if(m==MAP_FAILED || m!=(void*)g_imagebase){\n'
    '    if(m!=MAP_FAILED) munmap(m,sizeofimage);')
# Old qemu-user lacks the memfd_create syscall. A private unlinked file
# provides equivalent file-backed mappings for this isolated test process.
source = source.replace('int mfd=memfd_create("ftengine",MFD_CLOEXEC);',
                        'int mfd=ft_compat_memfd();')
helper = r'''
#include <errno.h>
static int ft_compat_memfd(void) {
  int fd=memfd_create("ftengine",MFD_CLOEXEC);
  if(fd>=0 || errno!=ENOSYS) return fd;
  char path[]="/tmp/ft9201-engine-XXXXXX";
  fd=mkstemp(path);
  if(fd<0) return -1;
  if(unlink(path)!=0 || fcntl(fd,F_SETFD,FD_CLOEXEC)<0) {
    int saved=errno; close(fd); errno=saved; return -1;
  }
  return fd;
}
'''
source = source.replace('static int load_pe(void){', helper+'\nstatic int load_pe(void){')
# Record exact vendor return codes to distinguish an unimplemented status
# query from an enrollment that is genuinely still in progress.
source = source.replace('u32 srej=0; u64 shr=Status(pipeline,&srej);',
    'u32 srej=0; u64 shr=Status(pipeline,&srej);\n'
    '  fprintf(stderr,"[compat] Update HRESULT=%#x reject=%u; Status HRESULT=%#x reject=%u\\n", (u32)uhr, urej, (u32)shr, srej);')
# Correct upstream's reordered output arguments and 32-bit SIZE_T buffers.
start = source.index('int ft_engine_verify(const uint8_t *tmpl,size_t tmpllen){')
if source[start:].count('int ft_engine_verify(') != 1:
    raise SystemExit('Unexpected verify implementation; review required')
import hashlib
expected_dll = 'ca34ba1e8494fc84a9ac31dd5c003e825d847484e5e3509f099de123d7953c6a'
if hashlib.sha256(Path('matcher-blobs/ftWbioEngineAdapter.dll').read_bytes()).hexdigest() != expected_dll:
    raise SystemExit('DLL changed; reverse-engineered diagnostics need review')
source = source[:start] + Path('verify-compat.txt').read_text()
Path('build/ft_engine_compat.c').write_text(source)
PATCH
x86_64-linux-gnu-gcc -static -no-pie -O0 -g -I upstream/src matcher.c build/ft_engine_compat.c -o matcher-x86_64
file matcher-x86_64
printf '%s\n' 'Built offline matcher. Run the smoke test with a previously captured image.'
