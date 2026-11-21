#!/usr/bin/env python3
"""Read real OpenWrt package metadata and hash its exact runtime payload."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile
import tempfile

LIMIT=128*1024*1024


def sha(raw):return hashlib.sha256(raw).hexdigest()


def tar_members(raw):
    if raw.startswith(b'\x28\xb5\x2f\xfd'):
        raw=subprocess.run(['zstd','-d','-c'],input=raw,capture_output=True,check=True).stdout
    result={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as archive:
        for item in archive.getmembers():
            name=item.name.removeprefix('./')
            if item.isdir():continue
            if not item.isfile() or name in result or item.size>LIMIT:
                raise ValueError('invalid/duplicate/non-regular package member')
            if name=='usr/bin/rill-runtime' and item.mode & 0o7777 != 0o755:
                raise ValueError('runtime payload must have exact mode 0755')
            stream=archive.extractfile(item)
            result[name]=stream.read()
    return result


def ipk(raw):
    if raw.startswith(b'!<arch>\n'):
        members={};offset=8
        while offset<len(raw):
            header=raw[offset:offset+60]
            if len(header)!=60 or header[58:]!=b'`\n':raise ValueError('invalid ar header')
            name=header[:16].decode().strip().rstrip('/');size=int(header[48:58]);offset+=60
            if size<0 or name in members or offset+size>len(raw):raise ValueError('invalid ar member')
            members[name]=raw[offset:offset+size];offset+=size+(size%2)
    else:members=tar_members(raw)
    selected=[]
    for kind in ['control','data']:
        matches=[content for name,content in members.items() if name.startswith(kind+'.tar')]
        if len(matches)!=1:raise ValueError('expected exactly one '+kind+' archive')
        selected.append(tar_members(matches[0]))
    controls,payload=selected
    if set(controls)-{'control','conffiles','postinst','prerm','postrm','preinst'}:
        raise ValueError('unexpected control member')
    fields={}
    for line in controls['control'].decode().splitlines():
        if not line or line[0].isspace():continue
        key,sep,value=line.partition(':')
        if not sep or key in fields:raise ValueError('invalid/duplicate package metadata')
        fields[key]=value.strip()
    if fields.get('Package') in {'rill-runtime','rill-runtime-preview'}:
        owner=fields['Package']
        preinst=controls.get('preinst',b'').decode(errors='replace')
        required=('IPKG_INSTROOT','PKG_UPGRADE','/usr/bin/rill-runtime',
                  'apk info -e '+owner,
                  'opkg status '+owner,
                  'refusing to overwrite /usr/bin/rill-runtime')
        if any(token not in preinst for token in required):
            raise ValueError('Preview package must contain its Runtime ownership pre-install guard')
    conflicts=sorted(filter(None,re.split(r'[\s,]+',fields.get('Conflicts','').strip())))
    return {'name':fields['Package'],'version':fields['Version'],'architecture':fields['Architecture'],'conflicts':conflicts},payload


def apk(path,tool,expected_name):
    record=json.loads(subprocess.check_output([tool,'--allow-untrusted','adbdump','--format','json',str(path)],text=True))
    found=[]
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,dict):
            if value.get('name')==expected_name and 'version' in value and ('arch' in value or 'architecture' in value):
                depends=value.get('depends',value.get('dependencies',[]))
                if isinstance(depends,str):depends=[depends]
                conflicts=[]
                for dependency in depends if isinstance(depends,list) else []:
                    if isinstance(dependency,str) and dependency.startswith('!'):
                        conflict=re.split(r'[<=>~]',dependency[1:],maxsplit=1)[0]
                        if conflict:conflicts.append(conflict)
                found.append({'name':expected_name,'version':value['version'],'architecture':value.get('architecture',value.get('arch')),'conflicts':sorted(set(conflicts))})
            for item in value.values():visit(item)
    visit(record)
    if len(found)!=1:raise ValueError('expected exactly one APK package identity')
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run([tool,'--allow-untrusted','extract','--destination',directory,str(path)],check=True,capture_output=True)
        payload={}
        for file in Path(directory).rglob('*'):
            if file.is_symlink():raise ValueError('APK payload cannot contain symlinks')
            if file.is_dir():continue
            if not file.is_file() or file.is_symlink() or file.stat().st_size>LIMIT:raise ValueError('invalid APK payload')
            if file.name=='rill-runtime' and file.stat().st_mode & 0o7777 != 0o755:
                raise ValueError('runtime payload must have exact mode 0755')
            payload[str(file.relative_to(directory))]=file.read_bytes()
    return found[0],payload


def runtime_payload(payload,expected_name,pkgtype):
    channel='stable' if expected_name=='rill-runtime' else 'preview'
    marker='usr/share/rill/runtime-channel'
    marker_bytes=(channel+'\n').encode()
    metadata_files=[]
    if pkgtype=='apk':
        # OpenWrt APK recipes ship a package-manager ownership list as data.
        # Admit only this package's exact generated list with the runtime and
        # channel marker paths; another list, additional owner, or arbitrary
        # file stays fatal.
        owner_list='lib/apk/packages/'+expected_name+'.list'
        if owner_list not in payload:
            raise ValueError('APK ownership list missing')
        expected_owners={b'/usr/bin/rill-runtime',b'/usr/share/rill/runtime-channel'}
        if set(payload[owner_list].splitlines())!=expected_owners:
            raise ValueError('APK ownership list differs from runtime payload')
        metadata_files.append(owner_list)
    if payload.get(marker)!=marker_bytes:
        raise ValueError('runtime channel marker missing or mismatched')
    if set(payload)!={'usr/bin/rill-runtime',marker,*metadata_files}:
        raise ValueError('runtime package must own only its runtime, channel marker and exact APK ownership metadata')
    return payload['usr/bin/rill-runtime'],metadata_files


def inspect(path,expected_name,expected_arch,expected_version,tool='apk'):
    if path.stat().st_size>LIMIT:raise ValueError('package exceeds inspection limit')
    raw=path.read_bytes()
    metadata,payload=ipk(raw) if path.suffix=='.ipk' else apk(path.resolve(),tool,expected_name)
    expected_conflict = (
        ['rill-runtime-preview']
        if expected_name == 'rill-runtime'
        else (['rill-runtime'] if path.suffix == '.apk' else [])
    )
    if metadata!={'name':expected_name,'version':expected_version,'architecture':expected_arch,'conflicts':expected_conflict}:
        raise ValueError('real package metadata mismatch: '+repr(metadata))
    binary,metadata_files=runtime_payload(payload,expected_name,path.suffix.removeprefix('.'))
    arch_contract={
        'x86_64':{'class':2,'machine':62,'loader':'/lib/ld-musl-x86_64.so.1','elfClass':'ELF64','elfMachine':'Advanced Micro Devices X86-64'},
        'aarch64_generic':{'class':2,'machine':183,'loader':'/lib/ld-musl-aarch64.so.1','elfClass':'ELF64','elfMachine':'AArch64'},
        'aarch64_cortex-a53':{'class':2,'machine':183,'loader':'/lib/ld-musl-aarch64.so.1','elfClass':'ELF64','elfMachine':'AArch64'},
        'aarch64_cortex-a72':{'class':2,'machine':183,'loader':'/lib/ld-musl-aarch64.so.1','elfClass':'ELF64','elfMachine':'AArch64'},
        'aarch64_cortex-a76':{'class':2,'machine':183,'loader':'/lib/ld-musl-aarch64.so.1','elfClass':'ELF64','elfMachine':'AArch64'},
        'arm_cortex-a7_neon-vfpv4':{'class':1,'machine':40,'loader':'/lib/ld-musl-armhf.so.1','elfClass':'ELF32','elfMachine':'ARM','elfABI':'EABI5 hard-float'},
    }
    contract=arch_contract.get(expected_arch)
    if contract is None:raise ValueError('unsupported ELF target architecture')
    elf_class=struct.unpack_from('B',binary,4)[0] if len(binary)>=5 else 0
    if len(binary)<52 or binary[:4]!=b'\x7fELF' or binary[5]!=1 or elf_class!=contract['class']:
        raise ValueError('ELF class or endianness mismatch')
    machine=struct.unpack_from('<H',binary,18)[0]
    if machine!=contract['machine']:raise ValueError('ELF machine mismatch')
    if elf_class==1:
        flags=struct.unpack_from('<I',binary,36)[0]
        # ARM Linux must use EABI version 5 and the hard-float procedure-call
        # standard selected by OpenWrt's CONFIG_HAS_FPU Rust target mapping.
        if flags & 0xff000000 != 0x05000000 or not flags & 0x400 or flags & 0x200:
            raise ValueError('ARM ELF ABI is not EABI5 hard-float')
        program_offset=struct.unpack_from('<I',binary,28)[0]
        entry_size,entry_count=struct.unpack_from('<HH',binary,42)
        minimum_entry_size=32
    else:
        program_offset=struct.unpack_from('<Q',binary,32)[0]
        entry_size,entry_count=struct.unpack_from('<HH',binary,54)
        minimum_entry_size=56
    interpreters=[]
    if entry_size<minimum_entry_size or program_offset+entry_size*entry_count>len(binary):
        raise ValueError('invalid ELF program header table')
    for index in range(entry_count):
        offset=program_offset+index*entry_size
        if struct.unpack_from('<I',binary,offset)[0]==3:
            if elf_class==1:
                start=struct.unpack_from('<I',binary,offset+4)[0]
                size=struct.unpack_from('<I',binary,offset+16)[0]
            else:
                start=struct.unpack_from('<Q',binary,offset+8)[0]
                size=struct.unpack_from('<Q',binary,offset+32)[0]
            if size>256 or start+size>len(binary):raise ValueError('invalid ELF interpreter')
            interpreters.append(binary[start:start+size].rstrip(b'\0').decode())
    if len(interpreters)!=1 or interpreters[0]!=contract['loader']:
        raise ValueError('ELF interpreter mismatch')
    result={'artifact':path.name,'sha256':sha(raw),'binary':'/usr/bin/rill-runtime',
        'binarySha256':sha(binary),'binarySize':len(binary),'interpreter':interpreters[0] if interpreters else None,'packageMetadata':metadata,
        'packageMetadataFiles':metadata_files,
        'elfClass':contract['elfClass'],'endianness':'little','elfMachine':contract['elfMachine']}
    if 'elfABI' in contract:result['elfABI']=contract['elfABI']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('--name',required=True,choices=['rill-runtime','rill-runtime-preview'])
    parser.add_argument('--architecture',required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--apk',default='apk')
    args=parser.parse_args()
    print(json.dumps(inspect(args.package,args.name,args.architecture,args.version,args.apk),indent=2))


if __name__=='__main__':main()
