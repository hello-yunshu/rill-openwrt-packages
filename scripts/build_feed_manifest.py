#!/usr/bin/env python3
"""Create durable feed provenance from one qualification manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed", type=Path)
    parser.add_argument("qualification", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--channel", choices=("development", "production"), required=True)
    parser.add_argument("--release-url", default="")
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--apk-public-key", type=Path)
    parser.add_argument("--key-id", default="")
    args = parser.parse_args()
    qualification = json.loads(args.qualification.read_text(encoding="utf-8"))
    leaves = []
    for metadata_path in sorted(args.feed.glob("*/*/*/*/feed-metadata.json")):
        leaf = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        packages = sorted(leaf.glob(f"*.{metadata['pkgtype']}"))
        if len(packages) != 1:
            raise SystemExit(f"expected one package in {leaf}")
        # Keep the manifest index digest aligned with verify_feed.py's
        # semantic IPK index contract; Packages.gz is checked separately.
        index_name = "Packages" if metadata["pkgtype"] == "ipk" else "packages.adb"
        index = leaf / index_name
        relative = "/".join(leaf.relative_to(args.feed).parts)
        leaves.append({
            "path": relative, "openwrtVersion": metadata["openwrtVersion"],
            "target": metadata["target"], "subtarget": metadata["subtarget"],
            "packageArch": metadata["packageArch"], "pkgtype": metadata["pkgtype"],
            "package": packages[0].name, "packageSha256": digest(packages[0]),
            "packageSize": packages[0].stat().st_size, "index": index_name,
            "indexSha256": digest(index), "feedMetadataSha256": digest(metadata_path),
            "signing": metadata.get("signing", "unsigned"),
        })
    if len(leaves) != 6:
        raise SystemExit(f"expected six feed leaves, found {len(leaves)}")
    signing_status = "signed" if args.channel == "production" else "unsigned"
    if signing_status == "signed" and (not args.public_key or not args.public_key.is_file() or not args.apk_public_key or not args.apk_public_key.is_file()):
        raise SystemExit("production manifest requires both public keys")
    package = qualification["package"]
    manifest = {
        "schemaVersion": 2, "channel": args.channel,
        "productionFeedEligible": signing_status == "signed",
        "package": package["name"], "packageVersion": package["version"],
        "packageRelease": package["release"], "packageVersionRelease": f"{package['version']}-r{package['release']}",
        "packageCommit": qualification["packageCommit"], "qualificationRun": qualification["runId"],
        "qualificationManifestSha256": digest(args.qualification),
        "releaseTag": f"v{package['version']}-r{package['release']}", "releaseUrl": args.release_url,
        "upstream": qualification["upstream"],
        "signing": {
            "status": signing_status,
            "scheme": "usign-Packages-and-apk-v3-index" if signing_status == "signed" else "none",
            "keyId": args.key_id,
            "publicKeySha256": {
                "usign": digest(args.public_key) if args.public_key and args.public_key.is_file() else "",
                "apk": digest(args.apk_public_key) if args.apk_public_key and args.apk_public_key.is_file() else "",
            },
            "publicKeyPath": {
                "usign": "keys/rill-openwrt-feed-usign.pub",
                "apk": "keys/rill-openwrt-feed-apk.pub",
            } if signing_status == "signed" else {},
        },
        "leaves": sorted(leaves, key=lambda item: item["path"]),
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
