import gzip
import tempfile
import unittest
from pathlib import Path

from scripts.verify_feed import verify


class FeedTests(unittest.TestCase):
    def test_valid_six_leaf_feed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for version, pkgtype in (("24.10.8", "ipk"), ("25.12.5", "apk")):
                for arch in ("x86_64", "aarch64_generic", "aarch64_cortex-a53"):
                    leaf = root / version / "x86" / "64" / arch
                    leaf.mkdir(parents=True)
                    package = leaf / f"rill-runtime-{version}-{arch}.{pkgtype}"
                    package.write_bytes(b"qualified-package")
                    if pkgtype == "ipk":
                        index = f"Package: rill-runtime\nFilename: {package.name}\n"
                        (leaf / "Packages").write_text(index, encoding="utf-8")
                        (leaf / "Packages.gz").write_bytes(gzip.compress(index.encode()))
                    else:
                        (leaf / "packages.adb").write_bytes(b"qualified-index")
            self.assertEqual(verify(root), [])

    def test_missing_index_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            leaf = Path(temporary) / "24.10.8" / "x86" / "64" / "x86_64"
            leaf.mkdir(parents=True)
            (leaf / "rill-runtime.ipk").write_bytes(b"package")
            errors = verify(Path(temporary))
            self.assertTrue(any("missing IPK index" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
