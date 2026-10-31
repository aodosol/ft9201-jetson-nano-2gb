#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
case "${1:---native-only}" in
    --native-only|--with-matcher) ;;
    *) echo 'Usage: bash build.sh [--native-only|--with-matcher]'; exit 2 ;;
esac
cc -Wall -Wextra -Werror -O2 probe.c -lusb-1.0 -o probe
cc -Wall -Wextra -Werror -O2 capture.c -lusb-1.0 -o capture
if [ "${1:---native-only}" = '--with-matcher' ]; then
    bash prepare-matcher.sh
fi
