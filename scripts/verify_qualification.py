#!/usr/bin/env python3
"""Verify canonical rill-runtime qualification evidence for consumers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")


def verify(data: dict, args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    schema = data.get("schemaVersion")
    if schema not in (1, 2):
        errors.append(f"unsupported schemaVersion={schema!r}")
        return errors
    if data.get("qualificationState") != "automated-qualification":
        errors.append("qualificationState is not automated-qualification")
    if data.get("releaseEligible") is not True:
        errors.append("releaseEligible is not true")

    package = data.get("package", {})
    if package.get("name") != "rill-runtime":
        errors.append("package.name is not rill-runtime")
    if package.get("recipe") != "package/rill-runtime/Makefile":
        errors.append("package.recipe is not canonical")
    if args.package_commit and data.get("packageCommit") != args.package_commit:
        errors.append("package commit mismatch")
    if args.version and package.get("version") != args.version:
        errors.append("package version mismatch")
    if args.release and str(package.get("release")) != args.release:
        errors.append("package release mismatch")

    upstream = data.get("upstream", {})
    for key, expected in (
        ("repository", args.upstream_repository),
        ("tag", args.upstream_tag),
        ("commit", args.upstream_commit),
    ):
        if expected and upstream.get(key) != expected:
            errors.append(f"upstream.{key} mismatch")
    if not SHA1.fullmatch(str(upstream.get("commit", ""))):
        errors.append("upstream.commit is not a SHA-1")
    if not SHA256.fullmatch(str(upstream.get("archiveSha256", ""))):
        errors.append("upstream.archiveSha256 is not SHA-256")

    targets = data.get("targets") if schema == 2 else data.get("artifacts")
    if not isinstance(targets, list) or not targets:
        errors.append("qualification targets are missing")
        return errors
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            errors.append(f"target[{index}] is not an object")
            continue
        if schema == 2 and target.get("qualificationState") != "PASS":
            errors.append(f"target[{index}] is not PASS")
        if not SHA256.fullmatch(str(target.get("sha256", ""))):
            errors.append(f"target[{index}].sha256 is invalid")
        if schema == 2:
            for key in ("openwrtVersion", "packageArch", "pkgtype", "binary"):
                if not target.get(key):
                    errors.append(f"target[{index}].{key} is missing")
        elif not target.get("path"):
            errors.append(f"target[{index}].path is missing")

    if args.openwrt_version or args.package_arch or args.pkgtype:
        matching = [
            target
            for target in targets
            if (not args.openwrt_version or target.get("openwrtVersion") == args.openwrt_version)
            and (not args.package_arch or target.get("packageArch") == args.package_arch)
            and (not args.pkgtype or target.get("pkgtype") == args.pkgtype)
        ]
        if not matching:
            errors.append("no target matches requested identity")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--package-commit")
    parser.add_argument("--version")
    parser.add_argument("--release")
    parser.add_argument("--upstream-repository")
    parser.add_argument("--upstream-tag")
    parser.add_argument("--upstream-commit")
    parser.add_argument("--openwrt-version")
    parser.add_argument("--package-arch")
    parser.add_argument("--pkgtype")
    args = parser.parse_args()
    try:
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
        errors = verify(data, args)
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
