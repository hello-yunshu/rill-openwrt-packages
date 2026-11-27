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
# CI configuration cannot change the packaged runtime, so editing it must not
# force a re-pin of the immutable upstream commit.
CI_ONLY_PREFIXES = (".github/",)
COMPARE_FILE_LIMIT = 300


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


def latest_main_commit() -> str:
    result = api(f"repos/{REPO}/commits/main")
    commit = str(result.get("sha", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("upstream main did not resolve to an immutable commit")
    return commit


def build_relevant_changes(paths: list[str]) -> list[str]:
    """Changed paths that can affect the packaged runtime."""
    return [path for path in paths if not path.startswith(CI_ONLY_PREFIXES)]


def changed_files(base: str, head: str) -> list[str]:
    """Files that differ between the pinned commit and upstream main."""
    if base == head:
        return []
    comparison = api(f"repos/{REPO}/compare/{base}...{head}")
    if comparison.get("status") == "diverged":
        raise RuntimeError(f"pinned commit {base} is not an ancestor of upstream {head}")
    files = [str(item.get("filename", "")) for item in comparison.get("files") or []]
    if comparison.get("truncated") or len(files) >= COMPARE_FILE_LIMIT:
        raise RuntimeError(f"upstream diff since {base} is too large to classify")
    return files


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
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    version_assignment = re.search(r"(?m)^PKG_VERSION:=.*$", text)
    release = re.search(r"(?m)^PKG_RELEASE:=(\S+)$", text)
    digest = re.search(r"(?m)^PKG_HASH:=(\S+)$", text)
    if not version_assignment or "$(RILL_VERSION_FILE)" not in version_assignment.group():
        raise RuntimeError("rill-runtime Makefile must read PKG_VERSION from VERSION")
    if stable_version(f"v{version}") is None or not release:
        raise RuntimeError("invalid rill-runtime VERSION or missing PKG_RELEASE")
    return version, release.group(1), digest.group(1) if digest else ""


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
    del release  # Stable promotion is pinned to upstream main's exact reviewed commit.
    package_version, package_release, _ = package_fields()
    metadata_version, metadata_tag, metadata_commit, _ = metadata_fields()
    upstream_commit = latest_main_commit()
    drift = build_relevant_changes(changed_files(metadata_commit, upstream_commit))
    assessment = {
        "sameVersion": package_version == metadata_version,
        "mutatedStable": False,
        "provenanceInSync": metadata_tag.startswith("stable-main-") and not drift,
        "rollback": False,
    }
    return {
        "upstreamStable": metadata_version,
        "upstreamTag": metadata_tag,
        "upstreamCommit": upstream_commit,
        "releaseUrl": f"https://github.com/{REPO}/commit/{upstream_commit}",
        "packageVersion": package_version,
        "packageRelease": package_release,
        **assessment,
        "inSync": package_version == metadata_version and assessment["provenanceInSync"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit one JSON report")
    parser.add_argument("--allow-outdated", action="store_true", help="report drift without failing")
    args = parser.parse_args()
    try:
        report = describe({})
    except Exception as error:  # noqa: BLE001 - CLI must expose a useful failure
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if not report["provenanceInSync"]:
        print(
            "SOURCE_DRIFT: upstream main has build-relevant commits after the pinned commit; "
            "review and pin its exact commit before qualification",
            file=sys.stderr,
        )
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("UP_TO_DATE" if report["inSync"] else f"OUTDATED: upstream stable = {report['upstreamStable']}, package = {report['packageVersion']}")
    return 0 if report["inSync"] or args.allow_outdated else 1


if __name__ == "__main__":
    raise SystemExit(main())
