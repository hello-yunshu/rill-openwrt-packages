import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_feed import verify


ARCHES = ("x86_64", "aarch64_generic", "aarch64_cortex-a53")


def make_feed(root: Path, *, corrupt: str | None = None) -> None:
    for version, pkgtype, package_version in (("24.10.8", "ipk", "1.5.6-1"), ("25.12.5", "apk", "1.5.6-r1")):
        for arch in ARCHES:
            target, subtarget = ("x86", "64") if arch == "x86_64" else ("armsr", "armv8") if arch == "aarch64_generic" else ("mediatek", "filogic")
            leaf = root / version / target / subtarget / arch
            leaf.mkdir(parents=True)
            suffix = "ipk" if pkgtype == "ipk" else "apk"
            package = leaf / f"rill-runtime_{package_version}_{arch}.{suffix}"
            package.write_bytes(b"qualified-package")
            metadata = {"openwrtVersion": version, "target": target, "subtarget": subtarget, "packageArch": arch, "pkgtype": pkgtype, "package": "rill-runtime", "packageVersion": package_version, "packageRelease": 1, "signing": "unsigned"}
            (leaf / "feed-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            if pkgtype == "ipk":
                import hashlib
                index = "\n".join(("Package: rill-runtime", f"Version: {package_version}", f"Architecture: {arch}", f"Filename: {package.name}", f"Size: {package.stat().st_size}", f"SHA256sum: {hashlib.sha256(package.read_bytes()).hexdigest()}", ""))
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
    def test_valid_six_leaf_feed(self):
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


if __name__ == "__main__":
    unittest.main()
