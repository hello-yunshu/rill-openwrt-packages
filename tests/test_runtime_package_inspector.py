import io
from pathlib import Path
import os
import struct
import subprocess
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


def fixture(extra=False,machine=62,mode=0o755,architecture='x86_64',binary=None,name='rill-runtime-preview'):
    if binary is None:
        binary=bytearray(160);binary[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<H',binary,18,machine);struct.pack_into('<Q',binary,32,64)
        struct.pack_into('<HH',binary,54,56,1)
        interpreter=b'/lib/ld-musl-x86_64.so.1\0'
        struct.pack_into('<I',binary,64,3)
        struct.pack_into('<Q',binary,72,120)
        struct.pack_into('<Q',binary,96,len(interpreter))
        struct.pack_into('<Q',binary,104,len(interpreter))
        binary[120:120+len(interpreter)]=interpreter
    else:
        binary=bytearray(binary)
    channel='stable' if name=='rill-runtime' else 'preview'
    other='rill-runtime-preview' if name=='rill-runtime' else 'rill-runtime'
    items=[('usr/bin/rill-runtime',bytes(binary),mode),
           ('usr/share/rill/runtime-channel',(channel+'\n').encode(),0o644)]
    if extra:items.append(('usr/bin/rill-pack',b'unexpected tool',0o755))
    preinst=f'''#!/bin/sh
[ -n "${{IPKG_INSTROOT}}" ] && exit 0
[ "${{PKG_UPGRADE:-0}}" = 1 ] && exit 0
if [ -e /usr/bin/rill-runtime ] || [ -L /usr/bin/rill-runtime ]; then
 if command -v apk >/dev/null 2>&1; then
  apk info -e {name} >/dev/null 2>&1 && exit 0
 elif command -v opkg >/dev/null 2>&1; then
  opkg status {name} 2>/dev/null | grep -q '^Status:.*installed' && exit 0
 fi
 echo "{name}: refusing to overwrite /usr/bin/rill-runtime with an unknown package owner" >&2
 exit 1
fi
exit 0
'''
    conflict = f'Conflicts: {other}\n' if name == 'rill-runtime' else ''
    control=archive([('control',f'Package: {name}\nVersion: 1.5.6-r3\nArchitecture: {architecture}\n{conflict}'.encode(),0o644),
                     ('preinst',preinst.encode(),0o755)])
    return archive([('control.tar.gz',control,0o644),('data.tar.gz',archive(items),0o644)])


def arm_elf(interpreter='/lib/ld-musl-armhf.so.1',flags=0x05000400,machine=40):
    raw=bytearray(160)
    raw[:6]=b'\x7fELF\x01\x01'
    struct.pack_into('<H',raw,16,2)
    struct.pack_into('<H',raw,18,machine)
    struct.pack_into('<I',raw,20,1)
    struct.pack_into('<I',raw,28,52)
    struct.pack_into('<I',raw,36,flags)
    struct.pack_into('<HH',raw,40,52,32)
    struct.pack_into('<H',raw,44,1)
    if interpreter is None:
        struct.pack_into('<H',raw,44,0)
    else:
        encoded=interpreter.encode()+b'\0'
        struct.pack_into('<I',raw,52,3)
        struct.pack_into('<I',raw,56,84)
        struct.pack_into('<I',raw,68,len(encoded))
        raw[84:84+len(encoded)]=encoded
    return bytes(raw)


class RealPackageInspector(unittest.TestCase):
    def test_preview_ipk_inspection_rejects_missing_ownership_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime.ipk'
            raw=fixture()
            control=archive([('control',b'Package: rill-runtime-preview\nVersion: 1.5.6-r3\nArchitecture: x86_64\nConflicts: rill-runtime\n',0o644)])
            # Rebuild the package with the same payload but no preinst member.
            with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as outer:
                contents={item.name:outer.extractfile(item).read() for item in outer.getmembers()}
            contents['control.tar.gz']=control
            path.write_bytes(archive([(name,data,0o644) for name,data in contents.items()]))
            with self.assertRaisesRegex(ValueError,'ownership pre-install guard'):
                inspect(path,'rill-runtime-preview','x86_64','1.5.6-r3')

    def test_apk_owner_metadata_cannot_hide_an_additional_owner(self):
        marker='usr/share/rill/runtime-channel'
        binary={'usr/bin/rill-runtime':b'payload',marker:b'stable\n'}
        owner='lib/apk/packages/rill-runtime.list'
        owners=b'/usr/bin/rill-runtime\n/usr/share/rill/runtime-channel\n'
        self.assertEqual(runtime_payload({**binary,owner:owners},'rill-runtime','apk'),
                         (b'payload',[owner]))
        for payload,kind in [
            ({**binary,owner:owners+b'/etc/config/user\n'},'apk'),
            ({**binary,'lib/apk/packages/other.list':owners},'apk'),
            ({**binary,owner:owners,'usr/bin/extra':b'bad'},'apk'),
            ({**binary,owner:owners},'ipk'),
            ({**binary,marker:b'preview\n',owner:owners},'apk'),
            ({'usr/bin/rill-runtime':b'payload',owner:owners},'apk'),
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
            self.assertEqual(result['interpreter'],'/lib/ld-musl-x86_64.so.1')
            for name,arch,version in [('rill-runtime','x86_64','1.5.6-r3'),
                                      ('rill-runtime-preview','aarch64_generic','1.5.6-r3'),
                                      ('rill-runtime-preview','x86_64','1.5.6-r2')]:
                with self.assertRaises(ValueError):inspect(path,name,arch,version)

    def test_ipk_conflict_metadata_and_preinst_guards_prevent_cross_channel_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime.ipk'
            for name in ('rill-runtime','rill-runtime-preview'):
                path.write_bytes(fixture(name=name))
                result=inspect(path,name,'x86_64','1.5.6-r3')
                expected=['rill-runtime-preview'] if name=='rill-runtime' else []
                self.assertEqual(result['packageMetadata']['conflicts'],expected)

    def test_armv7_requires_eabi5_hard_float_and_armhf_loader(self):
        arch='arm_cortex-a7_neon-vfpv4'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime.ipk'
            path.write_bytes(fixture(architecture=arch,binary=arm_elf()))
            result=inspect(path,'rill-runtime-preview',arch,'1.5.6-r3')
            self.assertEqual(result['elfClass'],'ELF32')
            self.assertEqual(result['elfMachine'],'ARM')
            self.assertEqual(result['elfABI'],'EABI5 hard-float')
            self.assertEqual(result['interpreter'],'/lib/ld-musl-armhf.so.1')
            for binary in (
                arm_elf(flags=0x05000200),
                arm_elf(flags=0x05000000),
                arm_elf(interpreter='/lib/ld-musl-aarch64.so.1'),
                arm_elf(interpreter=None),
                arm_elf(machine=183),
            ):
                path.write_bytes(fixture(architecture=arch,binary=binary))
                with self.subTest(flags=hex(struct.unpack_from('<I',binary,36)[0]),machine=struct.unpack_from('<H',binary,18)[0]),self.assertRaises(ValueError):
                    inspect(path,'rill-runtime-preview',arch,'1.5.6-r3')


class StablePreinstallGuard(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).parents[1]
        self.script=self.script_for('rill-runtime')

    def script_for(self,name):
        source=self.root/f'package/{name}/Makefile'
        text=source.read_text()
        key=f'define Package/{name}/preinst\n'
        start=text.index(key)+len(key)
        end=text.index('\nendef',start)
        return text[start:end].replace('$$','$')

    def run_guard(self, root, path, extra_path=(), name='rill-runtime', **env):
        binary=Path(root)/'usr/bin/rill-runtime'
        binary.parent.mkdir(parents=True,exist_ok=True)
        binary.touch(exist_ok=True)
        script=self.script_for(name).replace('/usr/bin/rill-runtime',str(binary))
        merged=os.environ.copy()
        merged.update(env)
        merged['PATH']=os.pathsep.join([*(str(p) for p in extra_path),'/usr/bin','/bin'])
        return subprocess.run(['/bin/sh','-c',script],env=merged,text=True,capture_output=True)

    def test_unknown_binary_is_refused_but_owned_stable_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bin_dir=root/'fakebin';bin_dir.mkdir()
            apk=bin_dir/'apk';apk.write_text('#!/bin/sh\nexit 1\n');apk.chmod(0o755)
            refused=self.run_guard(root,root/'usr/bin/rill-runtime',[bin_dir])
            self.assertEqual(refused.returncode,1)
            self.assertIn('refusing to overwrite',refused.stderr)
            apk.write_text('#!/bin/sh\nexit 0\n')
            allowed=self.run_guard(root,root/'usr/bin/rill-runtime',[bin_dir])
            self.assertEqual(allowed.returncode,0)

    def test_upgrade_and_offline_staging_skip_unknown_owner_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(self.run_guard(root,root/'usr/bin/rill-runtime',PKG_UPGRADE='1').returncode,0)
            self.assertEqual(self.run_guard(root,root/'usr/bin/rill-runtime',IPKG_INSTROOT='/staging').returncode,0)

    def test_opkg_stable_owner_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bin_dir=root/'fakebin';bin_dir.mkdir()
            (bin_dir/'opkg').write_text("#!/bin/sh\nprintf 'Status: install user installed\\n'\n")
            (bin_dir/'opkg').chmod(0o755)
            # Hide apk so the script takes the opkg ownership check.
            result=self.run_guard(root,root/'usr/bin/rill-runtime',[bin_dir])
            self.assertEqual(result.returncode,0,result.stderr)

    def test_stable_guard_also_refuses_unknown_binary_and_allows_its_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bin_dir=root/'fakebin';bin_dir.mkdir()
            apk=bin_dir/'apk';apk.write_text('#!/bin/sh\nexit 1\n');apk.chmod(0o755)
            refused=self.run_guard(root,root/'usr/bin/rill-runtime',[bin_dir],name='rill-runtime')
            self.assertEqual(refused.returncode,1)
            apk.write_text('#!/bin/sh\nexit 0\n')
            allowed=self.run_guard(root,root/'usr/bin/rill-runtime',[bin_dir],name='rill-runtime')
            self.assertEqual(allowed.returncode,0)
