import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureCapabilityTests(unittest.TestCase):
    def test_recipe_does_not_turn_matrix_into_an_architecture_whitelist(self):
        makefile = (ROOT / "package/rill-runtime/Makefile").read_text(encoding="utf-8")
        self.assertIn("DEPENDS:=+libc", makefile)
        self.assertNotIn("@(x86_64||aarch64)", makefile)
        self.assertNotIn("RILL_ARCH_DEPENDS", makefile)

    def test_capability_and_qualification_are_separate(self):
        data = json.loads(
            (ROOT / "metadata/architecture-capability.json").read_text(encoding="utf-8")
        )
        families = set(data["buildCapability"]["architectureFamilies"])
        self.assertTrue({"x86_64", "aarch64", "arm", "riscv64", "mips"} <= families)
        self.assertTrue(data["buildCapability"]["defaultFeatures"])
        self.assertEqual(data["automatedQualification"]["status"], "pass")
        self.assertEqual(data["deviceQualification"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
