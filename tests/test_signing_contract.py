import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_feed import verify
from tests.test_feed import make_feed


class SigningContractTests(unittest.TestCase):
    def test_production_manifest_cannot_claim_signed_without_signatures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_feed(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schemaVersion": 2, "package": "rill-runtime", "packageVersion": "1.5.6", "packageRelease": 1,
                "packageCommit": "a" * 40, "qualificationManifestSha256": "b" * 64, "releaseTag": "v1.5.6-r1",
                "signing": {"status": "unsigned"}, "leaves": [],
            }), encoding="utf-8")
            errors = verify(root, channel="production", manifest_path=manifest)
            self.assertTrue(any("signing.status=signed" in error for error in errors))
            self.assertTrue(any("productionFeedEligible" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
