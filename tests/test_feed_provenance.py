import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_feed_manifest import main as build_manifest
from tests.test_feed import make_feed


class FeedProvenanceTests(unittest.TestCase):
    def test_manifest_binds_all_leaves_and_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feed = root / "feed"
            make_feed(feed)
            qualification = root / "qualification.json"
            qualification.write_text(json.dumps({
                "packageCommit": "a" * 40, "runId": "123",
                "package": {"name": "rill-runtime", "version": "1.5.6", "release": 1},
                "upstream": {"tag": "v1.5.6", "commit": "b" * 40, "archiveSha256": "c" * 64},
            }), encoding="utf-8")
            output = root / "manifest.json"
            import sys
            old = sys.argv
            try:
                sys.argv = ["build_feed_manifest.py", str(feed), str(qualification), str(output), "--channel", "development"]
                self.assertEqual(build_manifest(), 0)
            finally:
                sys.argv = old
            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schemaVersion"], 2)
            self.assertEqual(len(manifest["leaves"]), 6)
            self.assertFalse(manifest["productionFeedEligible"])
            self.assertEqual(manifest["qualificationManifestSha256"], hashlib.sha256(qualification.read_bytes()).hexdigest())
            self.assertEqual({leaf["index"] for leaf in manifest["leaves"]}, {"Packages", "packages.adb"})


if __name__ == "__main__":
    unittest.main()
