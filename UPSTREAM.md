# Source provenance

The vendored loader files in `upstream/src/` and their license come from
https://github.com/OMGrant/ft9201-libfprint at commit
`fcf5499c6ddadf0d2a03be14b173609e760a7ec6` (LGPL-2.1-or-later).
Copyright (C) 2026 Grant Garrison; original notices are retained.

`capture.c` adapts the USB protocol and scan sequence from that commit's
`src/ft9201.c`. ARM64 capture, offline tools, and compatibility changes are
kept separately. `prepare-matcher.sh` generates the adapted x86 loader in
`build/` without modifying the vendored original.

The sensor firmware and Windows matching DLL belong to FocalTech and are
not included in this repository. Preparation scripts fetch public packages
referenced by the upstream project and extract the required files locally;
the amd64 Debian package is not installed.

The source implements a development experiment. Successful USB capture and
engine loading must not be interpreted as successful secure authentication.
