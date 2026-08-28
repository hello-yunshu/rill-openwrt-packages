#!/usr/bin/env python3
"""Check the canonical package against the latest published Rill Stable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = "hello-yunshu/rill-ml"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def api(path: str) -> object:
    request = Request(
        f"https://api.github.com/{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "rill-openwrt-packages"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def stable_version(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER.fullmatch(tag)
    return tuple(int(part) for part in match.groups()) if match else None


def release_for_tag(tag: str) -> dict[str, object]:
    release = api(f"repos/{REPO}/releases/tags/{tag}")
    if release.get("draft") or release.get("prerelease") or stable_version(tag) is None:
        raise RuntimeError(f"{tag} is not a published Stable release")
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


def latest_release() -> dict[str, object]:
    releases = api(f"repos/{REPO}/releases?per_page=100")
    candidates = [
        release
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and stable_version(str(release.get("tag_name", ""))) is not None
    ]
    if not candidates:
        raise RuntimeError("no published Stable Rill release was found")
    return max(candidates, key=lambda item: stable_version(str(item["tag_name"])))


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


def describe(release: dict[str, object]) -> dict[str, object]:
    tag = str(release["tag_name"])
    version = stable_version(tag)
    assert version is not None
    package_version, package_release, package_hash = package_fields()
    upstream_hash = archive_sha256(tag)
    return {
        "upstreamStable": ".".join(str(part) for part in version),
        "upstreamTag": tag,
        "upstreamCommit": resolve_tag_commit(tag),
        "releaseUrl": release["html_url"],
        "publishedAt": release["published_at"],
        "upstreamArchiveSha256": upstream_hash,
        "packageVersion": package_version,
        "packageRelease": package_release,
        "packageHash": package_hash,
        "hashInSync": package_hash == upstream_hash,
        "inSync": package_version == ".".join(str(part) for part in version) and package_hash == upstream_hash,
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
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("UP_TO_DATE" if report["inSync"] else f"OUTDATED: upstream stable = {report['upstreamStable']}, package = {report['packageVersion']}")
    return 0 if report["inSync"] or args.allow_outdated else 1


if __name__ == "__main__":
    raise SystemExit(main())
