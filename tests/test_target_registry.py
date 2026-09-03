import json
import unittest

from scripts.openwrt_targets import entries, matrix


class TargetRegistryTests(unittest.TestCase):
    def test_enabled_entries_are_unique_and_renderable(self):
        targets = entries()
        self.assertGreater(len(targets), 0)
        self.assertEqual(len({tuple(item[key] for key in ("openwrtVersion", "target", "subtarget", "packageArch")) for item in targets}), len(targets))
        self.assertEqual(len(matrix()), len(targets))

    def test_registry_is_machine_readable(self):
        with open("metadata/openwrt-targets.json", encoding="utf-8") as stream:
            data = json.load(stream)
        self.assertEqual(data["schemaVersion"], 1)
        self.assertTrue(all(item["enabled"] for item in data["targets"]))


if __name__ == "__main__":
    unittest.main()
