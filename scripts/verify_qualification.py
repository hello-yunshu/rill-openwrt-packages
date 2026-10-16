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


def verify_v3(data: dict, args: argparse.Namespace) -> list[str]:
    """Both channels must cover the exact registry, with binary and build identity."""
    try:
        from .openwrt_targets import entries
    except ImportError:
        from openwrt_targets import entries
    errors = []
    if data.get("qualificationState") != "automated-qualification" or data.get("releaseEligible") is not True:
        errors.append("qualification is not release eligible")
    if not SHA1.fullmatch(str(data.get("packageCommit", ""))):
        errors.append("invalid packageCommit")
    for key in ("runId", "runAttempt"):
        if type(data.get(key)) is not int or data[key] <= 0:
            errors.append(f"invalid {key}")
    if args.package_commit and data.get("packageCommit") != args.package_commit:
        errors.append("package commit mismatch")
    identity_keys = ("openwrtVersion", "target", "subtarget", "packageArch", "rustTarget", "pkgtype")
    registry = {tuple(str(item[key]) for key in identity_keys): item for item in entries()}
    artifacts = set()
    for channel in ("stable", "preview"):
        preview = data.get("previewPackage", {})
        package = data.get("package", {}) if channel == "stable" else preview
        upstream = data.get("upstream", {}) if channel == "stable" else preview.get("upstream", {})
        build = data.get("build", {}) if channel == "stable" else preview.get("build", {})
        rows = data.get("targets") if channel == "stable" else preview.get("targets")
        expected_name = "rill-runtime" if channel == "stable" else "rill-runtime-preview"
        if package.get("name") != expected_name or package.get("recipe") != f"package/{expected_name}/Makefile":
            errors.append(f"{channel}: incorrect package owner/recipe")
        if package.get("binary") != "/usr/bin/rill-runtime":
            errors.append(f"{channel}: incorrect binary path")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(package.get("version", ""))) or type(package.get("release")) is not int or package["release"] <= 0:
            errors.append(f"{channel}: invalid package version/release")
        if upstream.get("repository") != "hello-yunshu/rill-ml" or upstream.get("version") != package.get("version"):
            errors.append(f"{channel}: source repository/version mismatch")
        if channel == "stable" and upstream.get("tag") != "v" + str(package.get("version")):
            errors.append("stable: source tag/version mismatch")
        if channel == "preview" and (package.get("channel") != "preview-exact-commit" or upstream.get("tag") != "preview-exact-commit"):
            errors.append("preview: channel semantics mismatch")
        if not SHA1.fullmatch(str(upstream.get("commit", ""))):
            errors.append(f"{channel}: invalid source commit")
        if channel == "stable" and not SHA256.fullmatch(str(upstream.get("archiveSha256", ""))):
            errors.append("stable: missing source archive hash")
        if not SHA256.fullmatch(str(build.get("sourceLockSha256", ""))):
            errors.append(f"{channel}: missing source lock digest")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(build.get("rustToolchain", ""))):
            errors.append(f"{channel}: missing Rust toolchain identity")
        if build.get("defaultFeatures") is not True or "wasm" not in build.get("runtimeFeatures", []):
            errors.append(f"{channel}: full default WASM capability not qualified")
        source_identity=build.get("verifiedSource", {})
        if source_identity.get("baseCommit") != upstream.get("commit") or not SHA1.fullmatch(str(source_identity.get("gitTree", ""))) or not SHA256.fullmatch(str(source_identity.get("patchedTreeSha256", ""))):
            errors.append(f"{channel}: immutable Git tree plus patched source proof missing")
        patches = build.get("sourcePatches", [])
        if not isinstance(patches, list) or patches != upstream.get("sourcePatches", []):
            errors.append(f"{channel}: source patch set differs from upstream/build identity")
        elif any(not isinstance(patch, dict) or patch.get("baseCommit") != upstream.get("commit") or patch.get("patchedSourceLockSha256") != build.get("sourceLockSha256") or not SHA256.fullmatch(str(patch.get("sha256", ""))) for patch in patches):
            errors.append(f"{channel}: invalid source patch/base/lock binding")
        if not isinstance(rows, list):
            errors.append(f"{channel}: target evidence missing")
            continue
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"{channel}: invalid target object")
                continue
            identity = tuple(str(row.get(key, "")) for key in identity_keys)
            if identity not in registry or identity in seen:
                errors.append(f"{channel}: unknown or duplicate target {identity}")
            seen.add(identity)
            for key in ("sha256", "binarySha256"):
                if not SHA256.fullmatch(str(row.get(key, ""))):
                    errors.append(f"{channel}: missing/invalid {key}")
            artifact = row.get("artifact", "")
            if not isinstance(artifact, str) or Path(artifact).name != artifact or not artifact or artifact in artifacts:
                errors.append(f"{channel}: invalid/duplicate artifact")
            artifacts.add(str(artifact))
            if not str(artifact).endswith('.' + str(row.get("pkgtype", ""))):
                errors.append(f"{channel}: artifact format mismatch")
            if row.get("qualificationState") != "PASS" or row.get("binary") != "/usr/bin/rill-runtime":
                errors.append(f"{channel}: target not qualified")
            target = registry.get(identity, {})
            if row.get("elfClass") != "ELF64" or row.get("endianness") != "little" or row.get("elfMachine") != target.get("elfMachine"):
                errors.append(f"{channel}: ELF identity mismatch")
            sdk = row.get("sdk", {})
            if sdk.get("openwrtVersion") != row.get("openwrtVersion") or any(not SHA256.fullmatch(str(sdk.get(key, ""))) for key in ("archiveSha256", "configurationLogSha256")):
                errors.append(f"{channel}: SDK archive/configuration identity missing")
            feeds = sdk.get("feeds", {})
            if set(feeds) != {"base", "packages"} or any(not isinstance(feed, dict) or not SHA1.fullmatch(str(feed.get("commit", ""))) or not feed.get("source") for feed in feeds.values()):
                errors.append(f"{channel}: SDK feed identities missing")
            engine = row.get("resolvedWasmtime", {})
            features = set(engine.get("features", []))
            if not re.fullmatch(r"wasmtime v\d+\.\d+\.\d+", str(engine.get("engine", ""))) or not {"component-model", "runtime", "cranelift", "pulley"} <= features or "component-model-async" in features:
                errors.append(f"{channel}: resolved WASM engine feature boundary missing or changed")
            security = row.get("securityAudit", {})
            if security.get("sourceLockSha256") != build.get("sourceLockSha256") or security.get("vulnerabilityCount") != 0 or security.get("warnings") != {} or security.get("ignoredAdvisories") != []:
                errors.append(f"{channel}: missing or unresolved source security audit")
            database = security.get("database", {})
            if not SHA1.fullmatch(str(database.get("last-commit", ""))) or not database.get("last-updated"):
                errors.append(f"{channel}: missing advisory database identity")
            artifact_dir = getattr(args, "artifacts_dir", None)
            if artifact_dir and isinstance(artifact, str) and artifact and Path(artifact).name == artifact:
                try:
                    try:
                        from .inspect_runtime_package import inspect
                    except ImportError:
                        from inspect_runtime_package import inspect
                    path = Path(artifact_dir) / artifact
                    inspected = inspect(path, expected_name, str(row.get("packageArch", "")),
                        f"{package.get('version')}-r{package.get('release')}", getattr(args, "apk", "apk"))
                    for field in ("sha256", "binarySha256", "elfClass", "endianness", "elfMachine", "interpreter", "packageMetadata"):
                        if inspected[field] != row.get(field):
                            errors.append(f"{channel}: actual artifact {field} differs from evidence")
                except (OSError, ValueError, KeyError) as error:
                    errors.append(f"{channel}: actual artifact inspection failed: {error}")
            expected_loader = "/lib/ld-musl-" + ("x86_64" if row.get("packageArch") == "x86_64" else "aarch64") + ".so.1"
            if "interpreter" not in row or row["interpreter"] not in (None, expected_loader):
                errors.append(f"{channel}: ELF loader identity mismatch")
            actual = row.get("packageMetadata", {})
            expected_version = f"{package.get('version')}-r{package.get('release')}"
            if actual.get("name") != expected_name or actual.get("architecture") != row.get("packageArch") or actual.get("version") != expected_version:
                errors.append(f"{channel}: actual package metadata mismatch")
        if seen != set(registry):
            errors.append(f"{channel}: target set differs from registry")
    selected = data.get("previewPackage", {}) if getattr(args, "channel", "stable") == "preview" else data.get("package", {})
    for key, expected in (("version", args.version), ("release", args.release)):
        if expected and str(selected.get(key)) != str(expected):
            errors.append(f"selected channel {key} mismatch")
    selected_upstream = data.get("previewPackage", {}).get("upstream", {}) if getattr(args, "channel", "stable") == "preview" else data.get("upstream", {})
    for key, expected in (("repository", args.upstream_repository), ("tag", args.upstream_tag), ("commit", args.upstream_commit)):
        if expected and selected_upstream.get(key) != expected:
            errors.append(f"selected upstream.{key} mismatch")
    if args.openwrt_version or args.package_arch or args.pkgtype:
        rows = data.get("previewPackage", {}).get("targets", []) if getattr(args, "channel", "stable") == "preview" else data.get("targets", [])
        if not any((not args.openwrt_version or row.get("openwrtVersion") == args.openwrt_version) and (not args.package_arch or row.get("packageArch") == args.package_arch) and (not args.pkgtype or row.get("pkgtype") == args.pkgtype) for row in rows):
            errors.append("no target matches requested identity")
    return errors


def verify(data: dict, args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    schema = data.get("schemaVersion")
    if schema == 3:
        return verify_v3(data, args)
    if getattr(args, "channel", "stable") == "preview":
        return ["Preview requires schemaVersion 3 with per-target binary identity"]
    if schema in (1, 2) and not getattr(args, "allow_legacy_stable", False):
        return ["legacy Stable evidence requires explicit --allow-legacy-stable; it cannot qualify a new promotion"]
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
    parser.add_argument("--artifacts-dir", type=Path, help="verify real package and binary bytes")
    parser.add_argument("--apk", default="apk", help="SDK apk executable for actual APK inspection")
    parser.add_argument("--allow-legacy-stable", action="store_true", help="read historical Stable structure only; never Preview/new promotion")
    parser.add_argument("--channel", choices=("stable", "preview"), default="stable")
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
    print("PASS" if data.get("schemaVersion")==3 else "PASS historical Stable structure only; not new promotion/Preview qualification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
