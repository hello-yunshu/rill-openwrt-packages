import sys
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts import update_rill_version as updater


class UpdateTransactionTests(unittest.TestCase):
    def run_update(self, root, version):
        release = {'tag_name': 'v'+version, 'html_url': 'https://example.test/release',
                   'published_at': '2026-10-15T00:00:00Z'}
        with patch.object(updater, 'ROOT', root), patch.object(updater.guard, 'ROOT', root), \
             patch.object(updater.guard, 'latest_release', return_value=release), \
             patch.object(updater.guard, 'resolve_tag_commit', return_value='a'*40), \
             patch.object(updater, 'archive_sha256', return_value='b'*64), \
             patch('sys.argv', ['update_rill_version.py']):
            return updater.main()

    def fixture(self, root):
        (root/'package/rill-runtime').mkdir(parents=True)
        (root/'metadata').mkdir()
        text='PKG_VERSION:=1.5.6\nPKG_RELEASE:=3\nPKG_HASH:='+'b'*64+'\n'
        (root/'package/rill-runtime/Makefile').write_text(text)
        data={'schemaVersion':1,'extension':{'keep':True},
              'upstream':{'version':'1.5.6','tag':'v1.5.6','commit':'a'*40,'archiveSha256':'b'*64,'extension':42},
              'package':{'name':'rill-runtime','version':'1.5.6','release':3,'extension':43}}
        (root/'metadata/rill-runtime.json').write_text(json.dumps(data))
        return data

    def test_current_release_is_byte_preserving_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.run_update(root,'1.5.6')
            self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_new_version_preserves_unowned_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            self.run_update(root,'1.5.7')
            data=json.loads((root/'metadata/rill-runtime.json').read_text())
            self.assertEqual(data['extension'],{'keep':True})
            self.assertEqual(data['upstream']['extension'],42)
            self.assertEqual(data['package']['extension'],43)
            self.assertEqual(data['package']['release'],1)

class AtomicWriteTests(unittest.TestCase):
    def test_second_replace_failure_restores_first_and_keeps_originals(self):
        import atomic_update
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            one=root/'one'; two=root/'two'
            one.write_bytes(b'old one'); two.write_bytes(b'old two')
            original=atomic_update.os.replace
            calls=0
            def fail_second(source,target):
                nonlocal calls
                calls+=1
                if calls==2:
                    raise OSError('injected metadata replacement failure')
                return original(source,target)
            with patch.object(atomic_update.os,'replace',side_effect=fail_second):
                with self.assertRaises(OSError):
                    atomic_update.replace_files({one:b'new one',two:b'new two'})
            self.assertEqual(one.read_bytes(),b'old one')
            self.assertEqual(two.read_bytes(),b'old two')
            self.assertEqual({p.name for p in root.iterdir()},{'one','two'})

    def test_detected_concurrent_edit_is_preserved_on_rollback(self):
        import atomic_update
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);one=root/'one';two=root/'two'
            one.write_bytes(b'old one');two.write_bytes(b'old two')
            original=atomic_update.os.replace;calls=0
            def conflict(source,target):
                nonlocal calls
                calls+=1
                if calls==2:
                    one.write_bytes(b'external edit')
                    raise OSError('injected failure')
                return original(source,target)
            with patch.object(atomic_update.os,'replace',side_effect=conflict):
                with self.assertRaisesRegex(RuntimeError,'concurrent edit prevents rollback'):
                    atomic_update.replace_files({one:b'new one',two:b'new two'})
            self.assertEqual(one.read_bytes(),b'external edit')
            self.assertEqual(two.read_bytes(),b'old two')
