#!/usr/bin/env python3
"""Tests for the automatic upstream pin rewrite."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import pin_upstream

RECIPE = """include $(TOPDIR)/rules.mk

PKG_NAME:=rill-runtime
PKG_VERSION:=1.5.6
PKG_RELEASE:=9
PKG_SOURCE_VERSION:=1e962a82443088229714877eee98617f1596eee8
"""

METADATA = {
    "schemaVersion": 1,
    "upstream": {
        "repository": "https://github.com/hello-yunshu/rill-ml",
        "tag": "stable-main-1e962a8",
        "version": "1.5.6",
        "commit": "1e962a82443088229714877eee98617f1596eee8",
        "sourceType": "immutable-git-commit",
        "releaseUrl": "https://github.com/hello-yunshu/rill-ml/commit/1e962a8",
        "archiveUrl": "https://github.com/hello-yunshu/rill-ml/archive/1e962a8.tar.gz",
        "sourcePatches": [],
    },
    "package": {"name": "rill-runtime", "version": "1.5.6", "release": 9},
}


class ApplyPinTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "metadata").mkdir()
        (self.root / "package/rill-runtime").mkdir(parents=True)
        (self.root / pin_upstream.RECIPE).write_text(RECIPE, encoding="utf-8")
        (self.root / pin_upstream.METADATA).write_text(
            json.dumps(METADATA, indent=2) + "\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text(
            "| 当前来源版本 | <code>1.5.6</code> |\n| 当前包版本 | <code>1.5.6-r9</code> |\n",
            encoding="utf-8",
        )
        (self.root / "README.en.md").write_text(
            "| Upstream Runtime version | `1.5.6` |\n| OpenWrt package version | `1.5.6-r9` |\n",
            encoding="utf-8",
        )
        self.change = {
            "changed": True,
            "commit": "a" * 40,
            "version": "1.5.6",
            "release": 10,
            "previousVersion": "1.5.6",
            "previousRelease": 9,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_version_bumps_release_only(self):
        pin_upstream.apply(self.root, self.change)
        recipe = (self.root / pin_upstream.RECIPE).read_text(encoding="utf-8")
        self.assertIn("PKG_RELEASE:=10", recipe)
        self.assertIn(f"PKG_SOURCE_VERSION:={'a' * 40}", recipe)
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("1.5.6-r10", readme)
        self.assertNotIn("1.5.6-r9", readme)

    def test_new_version_rewrites_metadata(self):
        change = {**self.change, "version": "1.5.7", "release": 1}
        pin_upstream.apply(self.root, change)
        metadata = json.loads((self.root / pin_upstream.METADATA).read_text())
        self.assertEqual(metadata["upstream"]["tag"], "stable-main-aaaaaaa")
        self.assertEqual(metadata["upstream"]["version"], "1.5.7")
        self.assertEqual(metadata["upstream"]["commit"], "a" * 40)
        self.assertEqual(metadata["package"], {
            "name": "rill-runtime", "version": "1.5.7", "release": 1,
        })
        readme = (self.root / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("1.5.7-r1", readme)


if __name__ == "__main__":
    unittest.main()
