from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_feed import verify
from scripts.openwrt_targets import entries


def make_feed(root: Path, *, corrupt: str | None = None, package_name: str = "rill-runtime", release: int = 1) -> None:
    for item in entries():
        version = str(item["openwrtVersion"])
        pkgtype = str(item["pkgtype"])
        arch = str(item["packageArch"])
        package_version = f"1.5.6-{release}" if pkgtype == "ipk" else f"1.5.6-r{release}"
        leaf = root / version / str(item["target"]) / str(item["subtarget"]) / arch
        leaf.mkdir(parents=True)
        package = leaf / f"{package_name}_{package_version}_{arch}.{pkgtype}"
        package.write_bytes(b"qualified-package")
        metadata = {**item, "package": package_name, "packageVersion": package_version, "packageRelease": release, "signing": "unsigned"}
        (leaf / "feed-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        if pkgtype == "ipk":
            import hashlib
            index = "\n".join((f"Package: {package_name}", f"Version: {package_version}", f"Architecture: {arch}", f"Filename: {package.name}", f"Size: {package.stat().st_size}", f"SHA256sum: {hashlib.sha256(package.read_bytes()).hexdigest()}", ""))
            (leaf / "Packages").write_text(index, encoding="utf-8")
            (leaf / "Packages.gz").write_bytes(gzip.compress(index.encode()))
        else:
            (leaf / "packages.adb").write_bytes(b"qualified-index")
    if corrupt == "gzip":
        (root / "24.10.8/x86/64/x86_64/Packages.gz").write_bytes(b"broken")
    if corrupt == "sha":
        path = root / "24.10.8/x86/64/x86_64/Packages"
        path.write_text(path.read_text(encoding="utf-8").replace("SHA256sum: ", "SHA256sum: " + "0"), encoding="utf-8")


class FeedTests(unittest.TestCase):
    def test_valid_registry_feed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root)
            self.assertEqual(verify(root), [])

    def test_semantic_ipk_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root, corrupt="sha")
            self.assertTrue(any("SHA256sum mismatch" in error for error in verify(root)))

    def test_corrupt_gzip_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root, corrupt="gzip")
            self.assertTrue(any("Packages.gz" in error for error in verify(root)))

    def test_production_unsigned_feed_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root)
            self.assertTrue(any("Packages.sig" in error for error in verify(root, channel="production")))

    def test_missing_index_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root)
            (root / "24.10.8/x86/64/x86_64/Packages").unlink()
            errors = verify(root)
            self.assertTrue(any("missing IPK index" in error for error in errors))

    def test_preview_unsigned_feed_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root, package_name="rill-runtime-preview", release=6)
            errors = verify(root, channel="preview")
            self.assertTrue(all("package mismatch" not in error for error in errors))
            self.assertTrue(any("Packages.sig" in error for error in errors))

    def test_preview_channel_rejects_stable_package_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root)
            errors = verify(root, channel="preview")
            self.assertTrue(any("package mismatch" in error for error in errors))

    def test_preview_manifest_cannot_be_production_eligible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root, package_name="rill-runtime-preview", release=6)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schemaVersion": 3, "package": "rill-runtime-preview", "packageCommit": "a" * 40,
                "qualificationManifestSha256": "b" * 64, "qualificationRunAttempt": 1,
                "qualificationState": "automated-qualification", "releaseTag": "v1.5.6-r4",
                "productionFeedEligible": True,
                "signing": {"status": "signed", "publicKeySha256": {"usign": "c" * 64, "apk": "d" * 64}},
                "leaves": [],
            }), encoding="utf-8")
            errors = verify(root, channel="preview", manifest_path=manifest)
            self.assertTrue(any("must not be production-eligible" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
