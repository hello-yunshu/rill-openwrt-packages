#!/usr/bin/env python3
"""Update rill-runtime to a published Stable tag and its real archive hash."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

import check_upstream_version as guard
from atomic_update import replace_files
from source_patch_identity import inspect as inspect_patches

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_BASE = "https://github.com/hello-yunshu/rill-ml/archive/refs/tags/"


def archive_sha256(url: str) -> str:
    request = Request(url, headers={"User-Agent": "rill-openwrt-packages"})
    digest = hashlib.sha256()
    with urlopen(request, timeout=120) as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Stable X.Y.Z; defaults to latest Stable")
    parser.add_argument("--json", action="store_true", help="emit the updated provenance")
    args = parser.parse_args()

    release = guard.latest_release() if args.version is None else guard.release_for_tag(f"v{args.version.lstrip('v')}")
    tag = str(release["tag_name"])
    version_tuple = guard.stable_version(tag)
    if version_tuple is None:
        raise SystemExit(f"ERROR: {tag} is not a stable SemVer tag")
    version = ".".join(str(part) for part in version_tuple)
    tag_commit = guard.resolve_tag_commit(tag)
    archive_url = f"{ARCHIVE_BASE}{tag}.tar.gz"
    archive_hash = archive_sha256(archive_url)

    current_version, current_release, current_hash = guard.package_fields()
    metadata_version, metadata_tag, metadata_commit, metadata_hash = guard.metadata_fields()
    assessment = guard.assess_provenance(
        upstream_version=version,
        upstream_tag=tag,
        upstream_commit=tag_commit,
        upstream_hash=archive_hash,
        package_version=current_version,
        package_hash=current_hash,
        metadata_version=metadata_version,
        metadata_tag=metadata_tag,
        metadata_commit=metadata_commit,
        metadata_hash=metadata_hash,
    )
    if assessment["mutatedStable"]:
        raise SystemExit(
            "ERROR: MUTATED_STABLE: same Stable SemVer has changed tag commit or archive hash; "
            "publish a new upstream version before updating this package"
        )
    if assessment["rollback"]:
        raise SystemExit("ERROR: ROLLBACK: refusing to move the package to a lower Stable version")

    metadata_path = ROOT / "metadata/rill-runtime.json"
    old_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if str(old_metadata.get("package", {}).get("release")) != current_release:
        raise SystemExit("ERROR: package release and metadata disagree")
    if old_metadata["upstream"].get("sourcePatches") and tag_commit != old_metadata["upstream"].get("commit"):
        raise SystemExit("ERROR: source security backport requires review/requalification before changing its upstream base")
    inspect_patches(ROOT, old_metadata)
    if assessment["sameVersion"] and assessment["provenanceInSync"]:
        if args.json:
            print(json.dumps(old_metadata, indent=2, ensure_ascii=False))
        else:
            print(f"No Stable package update required for {tag}.")
        return 0

    makefile = ROOT / "package/rill-runtime/Makefile"
    text = makefile.read_text(encoding="utf-8")
    text, version_count = re.subn(r"(?m)^PKG_VERSION:=\S+$", f"PKG_VERSION:={version}", text)
    text, release_count = re.subn(r"(?m)^PKG_RELEASE:=\S+$", "PKG_RELEASE:=1", text)
    text, hash_count = re.subn(r"(?m)^PKG_HASH:=\S+$", f"PKG_HASH:={archive_hash}", text)
    if (version_count, release_count, hash_count) != (1, 1, 1):
        raise SystemExit("ERROR: expected exactly one PKG_VERSION/PKG_RELEASE/PKG_HASH")

    owned = {
        "schemaVersion": 1,
        "upstream": {
            "repository": f"https://github.com/{guard.REPO}",
            "tag": tag,
            "version": version,
            "commit": tag_commit,
            "releaseUrl": release["html_url"],
            "archiveUrl": archive_url,
            "archiveSha256": archive_hash,
            "publishedAt": release["published_at"],
        },
        "package": {
            "name": "rill-runtime",
            "version": version,
            "release": 1,
            "canonicalRecipe": "package/rill-runtime/Makefile",
            "binary": "/usr/bin/rill-runtime",
        },
    }
    metadata = copy.deepcopy(old_metadata)
    for key, value in owned.items():
        if isinstance(value, dict):
            if not isinstance(metadata.get(key), dict):
                raise SystemExit(f"ERROR: invalid metadata section {key}")
            metadata[key].update(value)
        else:
            metadata[key] = value
    raw = json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
    # Both representations are prepared and validated before either is replaced.
    if json.loads(raw)["package"]["version"] != version:
        raise SystemExit("ERROR: serialized package version mismatch")
    replace_files({makefile: text.encode(), metadata_path: raw.encode()})
    if args.json:
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
    else:
        print(f"updated rill-runtime to {tag} ({archive_hash})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
