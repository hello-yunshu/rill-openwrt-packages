import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

from scripts.inspect_runtime_package import inspect, runtime_payload


def archive(items):
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
        for name,data,mode in items:
            header=tarfile.TarInfo(name);header.size=len(data);header.mode=mode
            tar.addfile(header,io.BytesIO(data))
    return buffer.getvalue()


def fixture(extra=False,machine=62,mode=0o755):
    binary=bytearray(64);binary[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<H',binary,18,machine);struct.pack_into('<Q',binary,32,64)
    struct.pack_into('<HH',binary,54,56,0)
    items=[('usr/bin/rill-runtime',bytes(binary),mode)]
    if extra:items.append(('usr/bin/rill-pack',b'unexpected tool',0o755))
    control=archive([('control',b'Package: rill-runtime-preview\nVersion: 1.5.6-r3\nArchitecture: x86_64\n',0o644)])
    return archive([('control.tar.gz',control,0o644),('data.tar.gz',archive(items),0o644)])


class RealPackageInspector(unittest.TestCase):
    def test_apk_owner_metadata_cannot_hide_an_additional_owner(self):
        binary={'usr/bin/rill-runtime':b'payload'}
        owner='lib/apk/packages/rill-runtime.list'
        self.assertEqual(runtime_payload({**binary,owner:b'/usr/bin/rill-runtime\n'},'rill-runtime','apk'),
                         (b'payload',[owner]))
        for payload,kind in [
            ({**binary,owner:b'/usr/bin/rill-runtime\n/etc/config/user\n'},'apk'),
            ({**binary,'lib/apk/packages/other.list':b'/usr/bin/rill-runtime\n'},'apk'),
            ({**binary,owner:b'/usr/bin/rill-runtime\n','usr/bin/extra':b'bad'},'apk'),
            ({**binary,owner:b'/usr/bin/rill-runtime\n'},'ipk'),
        ]:
            with self.subTest(kind=kind,files=list(payload)),self.assertRaises(ValueError):
                runtime_payload(payload,'rill-runtime',kind)

    def test_valid_metadata_is_not_enough_for_wrong_machine_owner_or_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime.ipk'
            for raw in [fixture(extra=True),fixture(machine=183),fixture(mode=0o644),
                        fixture(mode=0o4755),fixture(mode=0o777),b'not an IPK']:
                path.write_bytes(raw)
                with self.subTest(size=len(raw)),self.assertRaises((ValueError,tarfile.TarError)):
                    inspect(path,'rill-runtime-preview','x86_64','1.5.6-r3')

    def test_expected_package_identity_is_checked_from_real_control(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime.ipk';path.write_bytes(fixture())
            result=inspect(path,'rill-runtime-preview','x86_64','1.5.6-r3')
            self.assertNotEqual(result['sha256'],result['binarySha256'])
            self.assertIsNone(result['interpreter'])
            for name,arch,version in [('rill-runtime','x86_64','1.5.6-r3'),
                                      ('rill-runtime-preview','aarch64_generic','1.5.6-r3'),
                                      ('rill-runtime-preview','x86_64','1.5.6-r2')]:
                with self.assertRaises(ValueError):inspect(path,name,arch,version)
