#!/usr/bin/env python3
"""Compare immutable package Release identity without dynamic qualification fields."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class IdentityMismatch(ValueError):
    """The candidate cannot be promoted to an existing immutable Release."""


IDENTITY_TARGET_FIELDS = (
    "artifact",
    "sha256",
    "openwrtVersion",
    "target",
    "subtarget",
    "packageArch",
    "rustTarget",
    "pkgtype",
    "binary",
    "elfClass",
    "endianness",
    "elfMachine",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IdentityMismatch(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: _sha256(path)
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix in {".ipk", ".apk"}
    }


def _sha256sums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        digest, separator, filename = line.partition("  ")
        if not separator or len(digest) != 64 or not filename:
            raise IdentityMismatch(f"invalid SHA256SUMS entry: {raw_line!r}")
        result[filename] = digest
    return result


def _target_identity(target: dict[str, Any]) -> dict[str, Any]:
    return {field: target.get(field) for field in IDENTITY_TARGET_FIELDS}


def semantic_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return only immutable identity; run IDs and generation metadata are excluded."""

    package = evidence.get("package")
    upstream = evidence.get("upstream")
    targets = evidence.get("targets")
    if not isinstance(package, dict) or not isinstance(upstream, dict) or not isinstance(targets, list):
        raise IdentityMismatch("qualification evidence is missing package, upstream, or targets")
    return {
        "package": {
            "name": package.get("name"),
            "version": package.get("version"),
            "release": package.get("release"),
            "binary": package.get("binary"),
        },
        "upstream": {
            "repository": upstream.get("repository"),
            "tag": upstream.get("tag"),
            "commit": upstream.get("commit"),
            "archiveSha256": upstream.get("archiveSha256"),
        },
        "targets": sorted((_target_identity(target) for target in targets), key=lambda item: str(item["artifact"])),
    }


def release_tag(evidence: dict[str, Any]) -> str:
    package = evidence.get("package")
    if not isinstance(package, dict):
        raise IdentityMismatch("qualification evidence is missing package identity")
    return f"v{package.get('version')}-r{package.get('release')}"


def compare_existing_release(existing_dir: Path, evidence_path: Path, assets_dir: Path) -> None:
    """Raise IdentityMismatch unless the existing Release is a byte-identical no-op."""

    existing_evidence = _load_json(existing_dir / "qualification.json")
    candidate_evidence = _load_json(evidence_path)
    existing_assets = _package_hashes(existing_dir)
    candidate_assets = _package_hashes(assets_dir)
    if existing_assets.keys() != candidate_assets.keys():
        raise IdentityMismatch("immutable release asset names changed; missing or extra asset")
    existing_sums = _sha256sums(existing_dir / "SHA256SUMS")
    if existing_sums != existing_assets:
        raise IdentityMismatch("existing immutable release SHA256SUMS does not match its package bytes")
    if candidate_assets != existing_assets:
        raise IdentityMismatch(
            "Package bytes changed for an existing immutable package release. "
            "Bump PKG_RELEASE or upstream SemVer."
        )
    if semantic_identity(existing_evidence) != semantic_identity(candidate_evidence):
        raise IdentityMismatch("immutable release package/upstream/target identity changed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-dir", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        compare_existing_release(args.existing_dir, args.evidence, args.assets_dir)
    except (OSError, json.JSONDecodeError, IdentityMismatch) as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Existing immutable release has identical package bytes and identity.")
    print("Promotion is a no-op.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
