#!/usr/bin/env python3
"""Resolve one SDK from the official checksum list, without HTML directory scraping."""
import argparse
from pathlib import Path
import re


def resolve(text, version, prefix):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("invalid release version")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", prefix):
        raise ValueError("invalid SDK target prefix")
    pattern = re.compile(r"openwrt-sdk-" + re.escape(version) + "-" +
                         re.escape(prefix) + r"_[A-Za-z0-9_.+-]+\.Linux-x86_64\.tar\.zst")
    matches = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        digest, filename = fields
        filename = filename.removeprefix("*")
        if pattern.fullmatch(filename):
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid SDK checksum")
            matches.append((filename, digest))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one SDK checksum entry, found {len(matches)}")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checksums", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    try:
        filename, digest = resolve(args.checksums.read_text(), args.version, args.prefix)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"SDK identity rejected: {exc}\n")
    print(filename, digest)


if __name__ == "__main__":
    main()
