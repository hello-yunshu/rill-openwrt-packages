import unittest

from scripts.resolve_sdk_identity import resolve


class SdkIdentityTests(unittest.TestCase):
    filename = "openwrt-sdk-24.10.8-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst"
    digest = "a" * 64

    def test_official_checksum_formats_and_unrelated_entries(self):
        for marker in ("*", ""):
            text = f"{'b' * 64} *config.buildinfo\n{self.digest} {marker}{self.filename}\n"
            self.assertEqual(resolve(text, "24.10.8", "x86-64"), (self.filename, self.digest))

    def test_missing_duplicate_malformed_and_unsafe_entries_reject(self):
        line = f"{self.digest} *{self.filename}\n"
        for text in ("", line + line, line.replace(self.digest, "bad"),
                     line.replace("*openwrt", "*../openwrt"),
                     line.replace("24.10.8", "25.12.5"),
                     line.replace("x86-64_", "armsr-armv8_")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                resolve(text, "24.10.8", "x86-64")


if __name__ == "__main__":
    unittest.main()
