#!/usr/bin/env python3
"""Advance the canonical package pin to upstream rill-ml automatically.

The feed pins an immutable rill-ml commit instead of following main at build
time, so every upstream change needs a reviewed commit that moves the pin and
bumps the package release.  That review is mechanical: reuse the same
build-relevant classification as the drift guard, rewrite the recipe,
metadata and the two version tables, and let the normal qualification and
release pipeline publish the result.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # executed as a script
    from check_upstream_version import (
        build_relevant_changes,
        changed_files,
        latest_main_commit,
        latest_release,
    )
except ImportError:  # imported as scripts.pin_upstream from tests
    from scripts.check_upstream_version import (
        build_relevant_changes,
        changed_files,
        latest_main_commit,
        latest_release,
    )

ROOT = Path(__file__).resolve().parents[1]
METADATA = Path("metadata/rill-runtime.json")
RECIPE = Path("package/rill-runtime/Makefile")
READMES = (Path("README.md"), Path("README.en.md"))


def read_metadata(root: Path) -> dict[str, object]:
    return json.loads((root / METADATA).read_text(encoding="utf-8"))


def plan(root: Path) -> dict[str, object]:
    metadata = read_metadata(root)
    upstream = metadata["upstream"]
    package = metadata["package"]
    assert isinstance(upstream, dict) and isinstance(package, dict)
    commit = latest_main_commit()
    drift = build_relevant_changes(changed_files(str(upstream["commit"]), commit))
    version = str(latest_release()["tag_name"]).lstrip("v")
    if not drift:
        return {"changed": False, "commit": commit, "version": version}
    current_version = str(package["version"])
    if version != current_version and _version_key(version) <= _version_key(current_version):
        raise RuntimeError(f"upstream Stable {version} does not advance {current_version}")
    release = 1 if version != current_version else int(str(package["release"])) + 1
    return {
        "changed": True,
        "commit": commit,
        "version": version,
        "release": release,
        "drift": drift,
        "previousVersion": current_version,
        "previousRelease": int(str(package["release"])),
    }


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def apply(root: Path, change: dict[str, object]) -> list[str]:
    """Rewrite recipe, metadata and README version tables in place."""
    version = str(change["version"])
    release = int(change["release"])
    commit = str(change["commit"])
    previous_version = str(change["previousVersion"])
    previous_release = int(change["previousRelease"])

    recipe = (root / RECIPE).read_text(encoding="utf-8")
    replacements = {
        r"^PKG_VERSION:=.*$": f"PKG_VERSION:={version}",
        r"^PKG_RELEASE:=.*$": f"PKG_RELEASE:={release}",
        r"^PKG_SOURCE_VERSION:=.*$": f"PKG_SOURCE_VERSION:={commit}",
    }
    for pattern, line in replacements.items():
        recipe, count = re.subn(pattern, line, recipe, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"{RECIPE}: expected exactly one {pattern}")
    (root / RECIPE).write_text(recipe, encoding="utf-8")

    metadata = read_metadata(root)
    upstream = metadata["upstream"]
    package = metadata["package"]
    assert isinstance(upstream, dict) and isinstance(package, dict)
    upstream.update(
        {
            "tag": f"stable-main-{commit[:7]}",
            "version": version,
            "commit": commit,
            "releaseUrl": f"https://github.com/hello-yunshu/rill-ml/commit/{commit}",
            "archiveUrl": f"https://github.com/hello-yunshu/rill-ml/archive/{commit}.tar.gz",
        }
    )
    package.update({"version": version, "release": release})
    (root / METADATA).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    old_package = f"{previous_version}-r{previous_release}"
    new_package = f"{version}-r{release}"
    touched = [str(RECIPE), str(METADATA)]
    for readme in READMES:
        path = root / readme
        text = path.read_text(encoding="utf-8")
        updated = text.replace(old_package, new_package)
        if version != previous_version:
            updated = updated.replace(previous_version, version)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            touched.append(str(readme))
    return touched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    change = plan(args.root)
    if not change["changed"]:
        print(f"upstream pin is current (build-relevant commit {change['commit']})")
    else:
        print(
            "advancing pin to "
            f"{change['previousVersion']}-r{change['previousRelease']} -> "
            f"{change['version']}-r{change['release']} at {change['commit']}"
        )
        for path in change["drift"]:
            print(f"  drift: {path}")
        if not args.dry_run:
            touched = apply(args.root, change)
            print("updated: " + ", ".join(touched))
        else:
            print("dry run: no files written")

    if args.github_output:
        lines = {
            "changed": str(change["changed"]).lower(),
            "version": change["version"],
            "release": change.get("release", ""),
            "commit": change["commit"],
        }
        with open(args.github_output, "a", encoding="utf-8") as output:
            for key, value in lines.items():
                output.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)
