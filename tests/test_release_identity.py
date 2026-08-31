import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.release_identity import IdentityMismatch, compare_existing_release, release_tag


def write_release_fixture(root: Path, *, run_id: str = "old-run", package_commit: str = "a" * 40) -> tuple[Path, Path, Path]:
    existing = root / "existing"
    candidate = root / "candidate"
    existing.mkdir()
    candidate.mkdir()
    packages = {
        "rill-runtime-v24.10.8-x86_64.ipk": b"ipk-bytes",
        "rill-runtime-v25.12.5-x86_64.apk": b"apk-bytes",
    }
    for name, data in packages.items():
        (existing / name).write_bytes(data)
        (candidate / name).write_bytes(data)
    evidence = {
        "schemaVersion": 2,
        "packageCommit": package_commit,
        "runId": run_id,
        "package": {"name": "rill-runtime", "version": "1.5.6", "release": 1, "binary": "/usr/bin/rill-runtime"},
        "upstream": {"repository": "hello-yunshu/rill-ml", "tag": "v1.5.6", "commit": "b" * 40, "archiveSha256": "c" * 64},
        "targets": [
            {"artifact": "rill-runtime-v24.10.8-x86_64.ipk", "sha256": "ignored-by-candidate-fixture", "openwrtVersion": "24.10.8", "target": "x86", "subtarget": "64", "packageArch": "x86_64", "rustTarget": "x86_64-unknown-linux-musl", "pkgtype": "ipk", "binary": "/usr/bin/rill-runtime", "elfClass": "ELF64", "endianness": "little", "elfMachine": "Advanced Micro Devices X86-64"},
            {"artifact": "rill-runtime-v25.12.5-x86_64.apk", "sha256": "ignored-by-candidate-fixture", "openwrtVersion": "25.12.5", "target": "x86", "subtarget": "64", "packageArch": "x86_64", "rustTarget": "x86_64-unknown-linux-musl", "pkgtype": "apk", "binary": "/usr/bin/rill-runtime", "elfClass": "ELF64", "endianness": "little", "elfMachine": "Advanced Micro Devices X86-64"},
        ],
    }
    existing_evidence = existing / "qualification.json"
    candidate_evidence = root / "candidate-qualification.json"
    existing_evidence.write_text(json.dumps(evidence), encoding="utf-8")
    candidate_evidence.write_text(json.dumps({**evidence, "runId": "new-run", "packageCommit": "d" * 40}), encoding="utf-8")
    sums = "\n".join(f"{hashlib.sha256(data).hexdigest()}  {name}" for name, data in sorted(packages.items())) + "\n"
    (existing / "SHA256SUMS").write_text(sums, encoding="utf-8")
    return existing, candidate, candidate_evidence


class ReleaseIdentityTests(unittest.TestCase):
    def test_same_bytes_different_run_metadata_is_noop(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing, candidate, evidence = write_release_fixture(Path(temporary))
            compare_existing_release(existing, evidence, candidate)

    def test_same_tag_changed_bytes_hard_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing, candidate, evidence = write_release_fixture(Path(temporary))
            (candidate / "rill-runtime-v24.10.8-x86_64.ipk").write_bytes(b"changed")
            with self.assertRaisesRegex(IdentityMismatch, "Bump PKG_RELEASE"):
                compare_existing_release(existing, evidence, candidate)

    def test_new_package_release_has_distinct_tag(self):
        evidence = {"package": {"version": "1.5.6", "release": 2}}
        self.assertEqual(release_tag(evidence), "v1.5.6-r2")

    def test_new_upstream_stable_is_distinct_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing, candidate, evidence = write_release_fixture(Path(temporary))
            changed = json.loads(evidence.read_text(encoding="utf-8"))
            changed["package"]["version"] = "1.5.7"
            changed["upstream"]["tag"] = "v1.5.7"
            evidence.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(IdentityMismatch):
                compare_existing_release(existing, evidence, candidate)

    def test_missing_or_extra_asset_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing, candidate, evidence = write_release_fixture(Path(temporary))
            (candidate / "rill-runtime-v25.12.5-x86_64.apk").unlink()
            with self.assertRaisesRegex(IdentityMismatch, "asset names"):
                compare_existing_release(existing, evidence, candidate)


if __name__ == "__main__":
    unittest.main()
