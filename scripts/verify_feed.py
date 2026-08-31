#!/usr/bin/env python3
"""Verify an OpenWrt feed, its indexes, provenance, and signatures.

APKv3 parsing and signature checking are delegated to the OpenWrt apk binary;
this verifier does not reverse engineer the binary index format.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Any

EXPECTED = {("24.10.8", "ipk"), ("25.12.5", "apk")}
EXPECTED_LEAVES = {
    ("24.10.8", "x86", "64", "x86_64"),
    ("24.10.8", "armsr", "armv8", "aarch64_generic"),
    ("24.10.8", "mediatek", "filogic", "aarch64_cortex-a53"),
    ("25.12.5", "x86", "64", "x86_64"),
    ("25.12.5", "armsr", "armv8", "aarch64_generic"),
    ("25.12.5", "mediatek", "filogic", "aarch64_cortex-a53"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if not line.strip():
            current = None
            continue
        if line[:1].isspace() and current:
            result[current] += "\n" + line.strip()
            continue
        name, separator, value = line.partition(":")
        if separator:
            current = name
            result[name] = value.lstrip()
    return result


def _run_apk(apk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(apk), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _json_objects(value: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(value, dict):
        objects.append(value)
        for child in value.values():
            objects.extend(_json_objects(child))
    elif isinstance(value, list):
        for child in value:
            objects.extend(_json_objects(child))
    return objects


def _apk_dump(apk: Path, path: Path) -> tuple[list[dict[str, Any]], str | None]:
    result = _run_apk(apk, ["adbdump", "--format", "json", str(path)])
    if result.returncode:
        return [], result.stderr.strip() or "apk adbdump failed"
    try:
        return _json_objects(json.loads(result.stdout)), None
    except json.JSONDecodeError as exc:
        return [], f"apk adbdump returned invalid JSON: {exc}"


def _check_apk_repository(apk: Path, leaf: Path, public_key: Path) -> str | None:
    with tempfile.TemporaryDirectory(prefix="rill-apk-verify-") as temporary:
        root = Path(temporary)
        key_dir = root / "etc/apk/keys"
        key_dir.mkdir(parents=True)
        database = root / "lib/apk/db"
        database.mkdir(parents=True)
        (database / "installed").touch()
        # apk treats a missing world file as a missing database layer even when
        # the installed database is intentionally empty.  A newline is the
        # canonical empty world used by apk's own database writer.
        (root / "etc/apk/world").write_text("\n", encoding="utf-8")
        (key_dir / public_key.name).write_bytes(public_key.read_bytes())
        repositories = root / "repositories"
        repositories.write_text(f"file://{leaf / 'packages.adb'}\n", encoding="utf-8")
        # apk 25.12 accepts --usermode for package transactions but rejects it
        # for repository update; the temporary root is already user-writable.
        result = _run_apk(apk, ["--root", str(root), "--keys-dir", str(key_dir), "--repositories-file", str(repositories), "--no-cache", "update"])
        if result.returncode:
            return result.stderr.strip() or result.stdout.strip() or "APK repository signature verification failed"
    return None


def _manifest_index(root: Path, manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not manifest:
        return {}
    return {str(item["path"]): item for item in manifest.get("leaves", []) if isinstance(item, dict) and "path" in item}


def verify(
    root: Path,
    *,
    channel: str = "development",
    manifest_path: Path | None = None,
    apk_path: Path | None = None,
    usign_path: Path | None = None,
    public_key: Path | None = None,
    apk_public_key: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    manifest: dict[str, Any] | None = None
    if manifest_path:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"invalid feed manifest: {exc}"]
        if manifest.get("schemaVersion") != 2:
            errors.append("feed manifest schemaVersion must be 2")
        if manifest.get("package") != "rill-runtime":
            errors.append("feed manifest package must be rill-runtime")
        if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("packageCommit", ""))):
            errors.append("feed manifest packageCommit must be a 40-character SHA")
        if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("qualificationManifestSha256", ""))):
            errors.append("feed manifest qualificationManifestSha256 must be a SHA-256")
        if manifest.get("releaseTag") != f"v{manifest.get('packageVersion')}-r{manifest.get('packageRelease')}":
            errors.append("feed manifest releaseTag does not match package identity")
        signing = manifest.get("signing")
        if not isinstance(signing, dict):
            errors.append("feed manifest signing metadata is missing")
        elif channel == "production" and signing.get("status") != "signed":
            errors.append("production feed must have signing.status=signed")
        elif channel == "development" and signing.get("status") not in {"unsigned", "signed"}:
            errors.append("development feed has invalid signing status")
        if channel == "production" and isinstance(signing, dict):
            key_hashes = signing.get("publicKeySha256")
            if not isinstance(key_hashes, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(key_hashes.get("usign", ""))) or not re.fullmatch(r"[0-9a-f]{64}", str(key_hashes.get("apk", ""))):
                errors.append("production feed signing metadata must include both public-key SHA-256 values")

    leaves = sorted(path for path in root.glob("*/*/*/*") if path.is_dir())
    if not leaves:
        return ["feed has no version/target/subtarget/package-arch directories"]

    seen: set[tuple[str, str, str, str]] = set()
    manifest_entries: list[dict[str, Any]] = []
    expected_manifest = _manifest_index(root, manifest)
    for leaf in leaves:
        relative = leaf.relative_to(root).parts
        if len(relative) != 4:
            errors.append(f"invalid feed directory depth: {leaf}")
            continue
        version, target, subtarget, package_arch = relative
        pkgtype = "ipk" if version == "24.10.8" else "apk" if version == "25.12.5" else "unknown"
        identity = (version, target, subtarget, package_arch)
        if (version, pkgtype) not in EXPECTED:
            errors.append(f"unsupported feed version/type: {leaf}")
            continue
        if identity in seen:
            errors.append(f"duplicate feed leaf: {'/'.join(identity)}")
        seen.add(identity)
        if identity not in EXPECTED_LEAVES:
            errors.append(f"unexpected qualified feed leaf: {'/'.join(identity)}")

        metadata_path = leaf / "feed-metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid feed-metadata.json in {leaf}: {exc}")
        elif manifest_path:
            errors.append(f"missing feed-metadata.json in {leaf}")
        if metadata:
            expected_metadata = {
                "openwrtVersion": version, "target": target, "subtarget": subtarget,
                "packageArch": package_arch, "pkgtype": pkgtype, "package": "rill-runtime",
            }
            for field, expected in expected_metadata.items():
                if metadata.get(field) != expected:
                    errors.append(f"{field} mismatch in {leaf}")
            if channel == "production" and metadata.get("signing") != "signed":
                errors.append(f"production leaf is not signed: {leaf}")

        packages = sorted(leaf.glob(f"*.{pkgtype}"))
        if len(packages) != 1:
            errors.append(f"expected exactly one {pkgtype} package in {leaf}")
            continue
        package = packages[0]
        index: Path
        if pkgtype == "ipk":
            index = leaf / "Packages"
            compressed = leaf / "Packages.gz"
            if not index.is_file() or not compressed.is_file():
                errors.append(f"missing IPK index in {leaf}")
            else:
                try:
                    if gzip.decompress(compressed.read_bytes()) != index.read_bytes():
                        errors.append(f"Packages.gz does not match Packages in {leaf}")
                except (OSError, EOFError, zlib.error) as exc:
                    errors.append(f"invalid Packages.gz in {leaf}: {exc}")
                fields = _fields(index.read_text(encoding="utf-8"))
                expected = {"Package": "rill-runtime", "Filename": package.name, "Size": str(package.stat().st_size), "SHA256sum": sha256(package)}
                if metadata.get("packageVersion"):
                    expected["Version"] = str(metadata["packageVersion"])
                if metadata.get("packageArch"):
                    expected["Architecture"] = str(metadata["packageArch"])
                for field, value in expected.items():
                    if fields.get(field) != value:
                        errors.append(f"Packages {field} mismatch in {leaf}: expected {value!r}, got {fields.get(field)!r}")
            if channel == "production":
                signature = leaf / "Packages.sig"
                if not signature.is_file():
                    errors.append(f"missing Packages.sig in {leaf}")
                elif not usign_path or not public_key:
                    errors.append("production IPK verification requires usign and public key")
                else:
                    result = subprocess.run([str(usign_path), "-V", "-m", str(index), "-p", str(public_key), "-x", str(signature), "-q"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    if result.returncode:
                        errors.append(f"invalid Packages.sig in {leaf}")
        else:
            index = leaf / "packages.adb"
            if not index.is_file() or index.stat().st_size == 0:
                errors.append(f"missing or empty APK packages.adb in {leaf}")
            elif metadata.get("packageVersion") and apk_path:
                objects, dump_error = _apk_dump(apk_path, index)
                if dump_error:
                    errors.append(f"APK index inspection failed in {leaf}: {dump_error}")
                matches = [obj for obj in objects if obj.get("name") == "rill-runtime"]
                if not matches:
                    errors.append(f"APK index has no rill-runtime entry in {leaf}")
                elif not any(str(obj.get("version")) == str(metadata["packageVersion"]) and str(obj.get("arch")) == package_arch for obj in matches):
                    errors.append(f"APK index rill-runtime version/architecture mismatch in {leaf}")
                package_objects, package_error = _apk_dump(apk_path, package)
                if package_error:
                    errors.append(f"APK package inspection failed in {leaf}: {package_error}")
                elif not any(str(obj.get("name")) == "rill-runtime" and str(obj.get("version")) == str(metadata["packageVersion"]) and str(obj.get("arch")) == package_arch for obj in package_objects):
                    errors.append(f"APK package metadata mismatch in {leaf}")
            if channel == "production":
                if not apk_path or not (apk_public_key or public_key):
                    errors.append("production APK verification requires apk and public key")
                else:
                    error = _check_apk_repository(apk_path, leaf, apk_public_key or public_key)
                    if error:
                        errors.append(f"invalid packages.adb signature in {leaf}: {error}")

        entry = {"path": "/".join(relative), "package": package.name, "packageSha256": sha256(package), "packageSize": package.stat().st_size, "index": index.name, "indexSha256": sha256(index) if index.is_file() else None}
        manifest_entries.append(entry)
        if expected_manifest:
            expected = expected_manifest.get(entry["path"])
            if not expected:
                errors.append(f"feed leaf missing from manifest: {entry['path']}")
            else:
                for field in ("package", "packageSha256", "packageSize", "index", "indexSha256"):
                    if expected.get(field) != entry[field]:
                        errors.append(f"manifest {field} mismatch in {entry['path']}")

    if len(manifest_entries) != 6:
        errors.append(f"expected 6 qualified feed leaves, found {len(manifest_entries)}")
    if manifest and len(manifest.get("leaves", [])) != 6:
        errors.append("feed manifest must contain six leaves")
    if channel == "production" and manifest and manifest.get("productionFeedEligible") is not True:
        errors.append("production feed manifest must set productionFeedEligible=true")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--channel", choices=("development", "production"), default="development")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--usign", type=Path)
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--apk-public-key", type=Path)
    args = parser.parse_args()
    errors = verify(args.root, channel=args.channel, manifest_path=args.manifest, apk_path=args.apk, usign_path=args.usign, public_key=args.public_key, apk_public_key=args.apk_public_key)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
