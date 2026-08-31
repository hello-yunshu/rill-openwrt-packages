#!/usr/bin/env python3
"""Check the canonical package against the latest published Rill Stable."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = "hello-yunshu/rill-ml"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def api(path: str) -> object:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rill-openwrt-packages",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"https://api.github.com/{path}",
        headers=headers,
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def stable_version(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER.fullmatch(tag)
    return tuple(int(part) for part in match.groups()) if match else None


def stable_1x_version(tag: str) -> tuple[int, int, int] | None:
    version = stable_version(tag)
    return version if version is not None and version[0] == 1 else None


def release_for_tag(tag: str) -> dict[str, object]:
    release = api(f"repos/{REPO}/releases/tags/{tag}")
    if release.get("draft") or release.get("prerelease") or stable_1x_version(tag) is None:
        raise RuntimeError(f"{tag} is not a published Stable 1.x release")
    return release


def resolve_tag_commit(tag: str) -> str:
    ref = api(f"repos/{REPO}/git/ref/tags/{tag}")
    obj = ref["object"]
    if obj["type"] == "commit":
        return obj["sha"]
    if obj["type"] != "tag":
        raise RuntimeError(f"unexpected tag object type for {tag}: {obj['type']}")
    tag_object = api(f"repos/{REPO}/git/tags/{obj['sha']}")
    if tag_object["object"]["type"] != "commit":
        raise RuntimeError(f"annotated tag {tag} does not resolve to a commit")
    return tag_object["object"]["sha"]


def select_latest_release(releases: list[dict[str, object]]) -> dict[str, object]:
    published_stable = [
        release
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and stable_version(str(release.get("tag_name", ""))) is not None
    ]
    candidates = [
        release
        for release in published_stable
        if stable_1x_version(str(release.get("tag_name", ""))) is not None
    ]
    if not candidates:
        if published_stable:
            raise RuntimeError("major-policy-block: published Stable releases contain no 1.x version")
        raise RuntimeError("no published Stable Rill release was found")
    return max(candidates, key=lambda item: stable_1x_version(str(item["tag_name"])))


def latest_release() -> dict[str, object]:
    releases = api(f"repos/{REPO}/releases?per_page=100")
    return select_latest_release(releases)


def archive_sha256(tag: str) -> str:
    request = Request(
        f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz",
        headers={"User-Agent": "rill-openwrt-packages"},
    )
    digest = hashlib.sha256()
    with urlopen(request, timeout=120) as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def package_fields() -> tuple[str, str, str]:
    text = (ROOT / "package/rill-runtime/Makefile").read_text(encoding="utf-8")
    version = re.search(r"(?m)^PKG_VERSION:=(\S+)$", text)
    release = re.search(r"(?m)^PKG_RELEASE:=(\S+)$", text)
    digest = re.search(r"(?m)^PKG_HASH:=(\S+)$", text)
    if not version or not release or not digest:
        raise RuntimeError("package Makefile is missing PKG_VERSION, PKG_RELEASE or PKG_HASH")
    return version.group(1), release.group(1), digest.group(1)


def metadata_fields() -> tuple[str, str, str, str]:
    metadata = json.loads((ROOT / "metadata/rill-runtime.json").read_text(encoding="utf-8"))
    upstream = metadata.get("upstream", {})
    return (
        str(upstream.get("version", "")),
        str(upstream.get("tag", "")),
        str(upstream.get("commit", "")),
        str(upstream.get("archiveSha256", "")),
    )


def assess_provenance(
    *,
    upstream_version: str,
    upstream_tag: str,
    upstream_commit: str,
    upstream_hash: str,
    package_version: str,
    package_hash: str,
    metadata_version: str,
    metadata_tag: str,
    metadata_commit: str,
    metadata_hash: str,
) -> dict[str, bool]:
    same_version = package_version == upstream_version
    mutated_stable = same_version and any(
        (
            package_hash != upstream_hash,
            metadata_version != upstream_version,
            metadata_tag != upstream_tag,
            metadata_commit != upstream_commit,
            metadata_hash != upstream_hash,
        )
    )
    package_tuple = stable_version(package_version)
    upstream_tuple = stable_version(upstream_version)
    return {
        "sameVersion": same_version,
        "mutatedStable": mutated_stable,
        "provenanceInSync": metadata_version == upstream_version
        and metadata_tag == upstream_tag
        and metadata_commit == upstream_commit
        and metadata_hash == upstream_hash,
        "rollback": package_tuple is not None
        and upstream_tuple is not None
        and package_tuple > upstream_tuple,
    }


def describe(release: dict[str, object]) -> dict[str, object]:
    tag = str(release["tag_name"])
    version = stable_version(tag)
    assert version is not None
    package_version, package_release, package_hash = package_fields()
    metadata_version, metadata_tag, metadata_commit, metadata_hash = metadata_fields()
    upstream_hash = archive_sha256(tag)
    upstream_version = ".".join(str(part) for part in version)
    upstream_commit = resolve_tag_commit(tag)
    assessment = assess_provenance(
        upstream_version=upstream_version,
        upstream_tag=tag,
        upstream_commit=upstream_commit,
        upstream_hash=upstream_hash,
        package_version=package_version,
        package_hash=package_hash,
        metadata_version=metadata_version,
        metadata_tag=metadata_tag,
        metadata_commit=metadata_commit,
        metadata_hash=metadata_hash,
    )
    return {
        "upstreamStable": upstream_version,
        "upstreamTag": tag,
        "upstreamCommit": upstream_commit,
        "releaseUrl": release["html_url"],
        "publishedAt": release["published_at"],
        "upstreamArchiveSha256": upstream_hash,
        "packageVersion": package_version,
        "packageRelease": package_release,
        "packageHash": package_hash,
        "hashInSync": package_hash == upstream_hash,
        **assessment,
        "inSync": package_version == upstream_version
        and package_hash == upstream_hash
        and assessment["provenanceInSync"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit one JSON report")
    parser.add_argument("--allow-outdated", action="store_true", help="report drift without failing")
    args = parser.parse_args()
    try:
        report = describe(latest_release())
    except Exception as error:  # noqa: BLE001 - CLI must expose a useful failure
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if report["mutatedStable"]:
        print(
            "MUTATED_STABLE: the published Stable SemVer has different tag commit "
            "or archive provenance; publish a new upstream version instead of rewriting the package",
            file=sys.stderr,
        )
        return 2
    if report["rollback"]:
        print("ROLLBACK: package version is newer than the latest Stable release", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("UP_TO_DATE" if report["inSync"] else f"OUTDATED: upstream stable = {report['upstreamStable']}, package = {report['packageVersion']}")
    return 0 if report["inSync"] or args.allow_outdated else 1


if __name__ == "__main__":
    raise SystemExit(main())
