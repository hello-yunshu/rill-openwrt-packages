import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.source_patch_identity import inspect

ROOT=Path(__file__).resolve().parents[1]


class SourcePatchIdentity(unittest.TestCase):
    def test_declared_channel_patches_bind_their_immutable_upstream_base(self):
        for name in ['rill-runtime','rill-runtime-preview']:
            meta=json.loads((ROOT/'metadata'/(name+'.json')).read_text())
            records=inspect(ROOT,meta)
            for record in records:
                self.assertEqual(record['baseCommit'],meta['upstream']['commit'])

    def test_replaced_patch_base_and_lock_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);patch=root/'package/rill-runtime/patches/010.patch';patch.parent.mkdir(parents=True)
            patch.write_bytes(b'reviewed source patch')
            source=root/'source';source.mkdir();(source/'Cargo.lock').write_bytes(b'reviewed lock')
            record={'path':'package/rill-runtime/patches/010.patch','sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
                    'baseCommit':'a'*40,'patchedSourceLockSha256':hashlib.sha256((source/'Cargo.lock').read_bytes()).hexdigest()}
            meta={'package':{'name':'rill-runtime'},'upstream':{'commit':'a'*40,'sourcePatches':[record]}}
            self.assertEqual(inspect(root,meta,source),[record])
            for field,value in [('baseCommit','b'*40),('sha256','c'*64),('patchedSourceLockSha256','d'*64),('path','../outside.patch')]:
                old=record[field];record[field]=value
                with self.assertRaises(ValueError):inspect(root,meta,source)
                record[field]=old
            (patch.parent/'999.patch').write_bytes(b'undeclared')
            with self.assertRaises(ValueError):inspect(root,meta,source)
