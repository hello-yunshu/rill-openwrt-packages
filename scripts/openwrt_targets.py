#!/usr/bin/env python3
"""Load the single OpenWrt Runtime target registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "metadata/openwrt-targets.json"
REQUIRED = (
    "openwrtVersion", "target", "subtarget", "packageArch", "pkgtype", "rustTarget",
)


def entries() -> list[dict[str, object]]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or not isinstance(data.get("targets"), list):
        raise ValueError("invalid OpenWrt target registry")
    result = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in data["targets"]:
        if not isinstance(item, dict) or any(not item.get(key) for key in REQUIRED):
            raise ValueError("target registry entry is missing required fields")
        identity = tuple(str(item[key]) for key in ("openwrtVersion", "target", "subtarget", "packageArch"))
        if identity in seen:
            raise ValueError(f"duplicate target registry identity: {'/'.join(identity)}")
        seen.add(identity)
        if item.get("enabled", True):
            result.append(item)
    if not result:
        raise ValueError("target registry has no enabled entries")
    return result


def matrix() -> list[dict[str, object]]:
    return [
        {
            "branch": f"v{item['openwrtVersion']}",
            "release_version": item["openwrtVersion"],
            "openwrt_target": item["target"],
            "openwrt_subtarget": item["subtarget"],
            "sdk_prefix": item.get("sdkPrefix", ""),
            "package_arch": item["packageArch"],
            "rust_target": item["rustTarget"],
            "pkgtype": item["pkgtype"],
            "elf_machine": item.get("elfMachine", "AArch64"),
            "support_tier": item.get("supportTier", "p0-openwrt-package"),
        }
        for item in entries()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args()
    if args.matrix:
        print(json.dumps({"include": matrix()}, separators=(",", ":")))
    elif args.count:
        print(len(entries()))
    else:
        print(json.dumps(entries(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
