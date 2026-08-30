#!/usr/bin/env python3
"""Sign an already-qualified feed without rebuilding any package."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed", type=Path)
    parser.add_argument("--ipk-private-key", type=Path, required=True)
    parser.add_argument("--apk-private-key", type=Path, required=True)
    parser.add_argument("--usign", type=Path, required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--apk-root", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.ipk_private_key, args.apk_private_key):
        if not path.is_file():
            raise SystemExit(f"missing signing key: {path}")
    for metadata_path in sorted(args.feed.glob("*/*/*/*/feed-metadata.json")):
        leaf = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["pkgtype"] == "ipk":
            subprocess.run([str(args.usign), "-S", "-m", str(leaf / "Packages"), "-s", str(args.ipk_private_key), "-x", str(leaf / "Packages.sig")], check=True)
        elif metadata["pkgtype"] == "apk":
            index = leaf / "packages.adb"
            packages = sorted(leaf.glob("*.apk"))
            subprocess.run([str(args.apk), "mkndx", "--root", str(args.apk_root), "--keys-dir", str(args.apk_root), "--allow-untrusted", "--sign", str(args.apk_private_key), "--output", str(index), *map(str, packages)], check=True)
        metadata["signing"] = "signed"
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
