import unittest

from scripts import check_upstream_version as guard


class UpstreamGuardTests(unittest.TestCase):
    COMMON = dict(
        upstream_version="1.5.6",
        upstream_tag="v1.5.6",
        upstream_commit="a" * 40,
        upstream_hash="b" * 64,
        package_version="1.5.6",
        package_hash="b" * 64,
        metadata_version="1.5.6",
        metadata_tag="v1.5.6",
        metadata_commit="a" * 40,
        metadata_hash="b" * 64,
    )

    def test_same_version_same_provenance_passes(self):
        result = guard.assess_provenance(**self.COMMON)
        self.assertFalse(result["mutatedStable"])
        self.assertFalse(result["rollback"])
        self.assertTrue(result["provenanceInSync"])

    def test_newer_stable_is_updateable(self):
        result = guard.assess_provenance(
            **{**self.COMMON, "upstream_version": "1.5.7", "upstream_tag": "v1.5.7"}
        )
        self.assertFalse(result["mutatedStable"])
        self.assertFalse(result["rollback"])

    def test_same_version_changed_tag_commit_fails_closed(self):
        result = guard.assess_provenance(**{**self.COMMON, "metadata_commit": "c" * 40})
        self.assertTrue(result["mutatedStable"])

    def test_same_version_changed_archive_hash_fails_closed(self):
        result = guard.assess_provenance(**{**self.COMMON, "metadata_hash": "d" * 64})
        self.assertTrue(result["mutatedStable"])

    def test_prerelease_is_not_stable(self):
        self.assertIsNone(guard.stable_version("v1.5.7-rc.1"))

    def test_stable_selector_accepts_only_major_one(self):
        self.assertEqual(guard.stable_1x_version("v1.10.0"), (1, 10, 0))
        self.assertIsNone(guard.stable_1x_version("v2.0.0"))

    def test_latest_selector_prefers_newest_published_stable_1x(self):
        releases = [
            {"tag_name": "v1.9.9", "draft": False, "prerelease": False},
            {"tag_name": "v1.10.0", "draft": False, "prerelease": False},
            {"tag_name": "v2.0.0", "draft": False, "prerelease": False},
            {"tag_name": "v1.11.0-rc.1", "draft": False, "prerelease": True},
        ]
        self.assertEqual(guard.select_latest_release(releases)["tag_name"], "v1.10.0")

    def test_major_policy_block_message_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, "major-policy-block"):
            guard.select_latest_release([
                {"tag_name": "v2.0.0", "draft": False, "prerelease": False},
            ])

    def test_newer_package_version_is_rollback(self):
        result = guard.assess_provenance(**{**self.COMMON, "package_version": "1.5.7"})
        self.assertTrue(result["rollback"])


if __name__ == "__main__":
    unittest.main()
