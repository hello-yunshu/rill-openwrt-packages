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

    def test_mainstream_architecture_set_is_consistent_across_package_formats(self):
        targets = entries()
        expected = {
            "x86_64",
            "aarch64_generic",
            "aarch64_cortex-a53",
            "aarch64_cortex-a72",
            "aarch64_cortex-a76",
            "arm_cortex-a7_neon-vfpv4",
        }
        for version, pkgtype in (("24.10.8", "ipk"), ("25.12.6", "apk")):
            release_targets = [item for item in targets if item["openwrtVersion"] == version]
            self.assertEqual({item["packageArch"] for item in release_targets}, expected)
            self.assertEqual({item["pkgtype"] for item in release_targets}, {pkgtype})

    def test_registry_declares_only_the_verified_elf_abi_contracts(self):
        contracts = {
            "x86_64": ("x86_64-unknown-linux-musl", "ELF64", "Advanced Micro Devices X86-64", None, None),
            "aarch64_generic": ("aarch64-unknown-linux-musl", "ELF64", "AArch64", None, None),
            "aarch64_cortex-a53": ("aarch64-unknown-linux-musl", "ELF64", "AArch64", None, None),
            "aarch64_cortex-a72": ("aarch64-unknown-linux-musl", "ELF64", "AArch64", None, None),
            "aarch64_cortex-a76": ("aarch64-unknown-linux-musl", "ELF64", "AArch64", None, None),
            "arm_cortex-a7_neon-vfpv4": (
                "armv7-unknown-linux-musleabihf", "ELF32", "ARM",
                "EABI5 hard-float", "/lib/ld-musl-armhf.so.1",
            ),
        }
        for row in entries():
            rust_target, elf_class, machine, abi, loader = contracts[row["packageArch"]]
            self.assertEqual(row["rustTarget"], rust_target)
            self.assertEqual(row.get("elfClass", "ELF64"), elf_class)
            self.assertEqual(row["elfMachine"], machine)
            self.assertEqual(row.get("elfABI"), abi)
            self.assertEqual(row.get("elfInterpreter"), loader)


if __name__ == "__main__":
    unittest.main()
