#!/usr/bin/env bash
# Kconfig can write .config despite a recursive dependency diagnostic.
set -euo pipefail
sdk="${1:?SDK directory required}"
log="${2:?configuration evidence log required}"
cd "$sdk"
# Keep the actual patched build inputs available for post-build qualification.
python3 - .config <<'PYCONFIG'
from pathlib import Path
import sys
path=Path(sys.argv[1])
lines=path.read_text().splitlines() if path.exists() else []
lines=[line for line in lines if line!='CONFIG_AUTOREMOVE=y' and line!='CONFIG_AUTOREMOVE=n' and line!='# CONFIG_AUTOREMOVE is not set']
path.write_text('\n'.join(lines+['# CONFIG_AUTOREMOVE is not set'])+'\n')
PYCONFIG
make defconfig 2>&1 | tee "$log"
grep -Fx '# CONFIG_AUTOREMOVE is not set' .config >/dev/null
if grep -Eq '(^|[[:space:]])error:|recursive dependency detected' "$log"; then
    echo 'SDK configuration contains an error; refusing package qualification.' >&2
    exit 1
fi
