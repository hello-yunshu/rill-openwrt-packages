#!/usr/bin/env python3
"""Verify the published OpenWrt feed layout and package/index correspondence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


EXPECTED = {
    ("24.10.8", "ipk"),
    ("25.12.5", "apk"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    leaves = sorted(path for path in root.glob("*/*/*/*") if path.is_dir())
    if not leaves:
        return ["feed has no version/target/subtarget/package-arch directories"]

    seen: set[tuple[str, str]] = set()
    manifest_entries: list[dict[str, str]] = []
    for leaf in leaves:
        relative = leaf.relative_to(root).parts
        if len(relative) != 4:
            errors.append(f"invalid feed directory depth: {leaf}")
            continue
        version, target, subtarget, package_arch = relative
        pkgtype = "ipk" if version == "24.10.8" else "apk" if version == "25.12.5" else "unknown"
        if (version, pkgtype) not in EXPECTED:
            errors.append(f"unsupported feed version/type: {leaf}")
            continue
        key = (version, package_arch)
        if key in seen:
            errors.append(f"duplicate version/package architecture: {version}/{package_arch}")
        seen.add(key)
        packages = sorted(leaf.glob(f"*.{pkgtype}"))
        if len(packages) != 1:
            errors.append(f"expected exactly one {pkgtype} package in {leaf}")
            continue
        package = packages[0]
        if pkgtype == "ipk":
            index = leaf / "Packages"
            compressed = leaf / "Packages.gz"
            if not index.is_file() or not compressed.is_file():
                errors.append(f"missing IPK index in {leaf}")
            elif gzip.decompress(compressed.read_bytes()) != index.read_bytes():
                errors.append(f"Packages.gz does not match Packages in {leaf}")
            elif f"Filename: {package.name}" not in index.read_text(encoding="utf-8"):
                errors.append(f"Packages does not reference {package.name}")
        else:
            index = leaf / "packages.adb"
            if not index.is_file() or index.stat().st_size == 0:
                errors.append(f"missing or empty APK packages.adb in {leaf}")
        manifest_entries.append(
            {
                "openwrtVersion": version,
                "target": target,
                "subtarget": subtarget,
                "packageArch": package_arch,
                "pkgtype": pkgtype,
                "package": package.name,
                "sha256": sha256(package),
                "index": "Packages.gz" if pkgtype == "ipk" else "packages.adb",
                "signing": "unsigned",
            }
        )

    if len(manifest_entries) != 6:
        errors.append(f"expected 6 qualified feed leaves, found {len(manifest_entries)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    errors = verify(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
