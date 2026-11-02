#!/usr/bin/env python3
"""Compare built source bytes with an immutable Git tree plus declared patches."""
from __future__ import annotations
import hashlib
import io
import os
import re
from pathlib import Path
import subprocess
import tarfile
import tempfile

URL='https://github.com/hello-yunshu/rill-ml.git'


def verify(repo_root,metadata,actual_source,cache):
    commit=metadata['upstream']['commit']
    if not re.fullmatch('[a-f0-9]{40}',str(commit)):raise ValueError('source commit must be immutable SHA-1')
    if not cache.exists():
        subprocess.run(['git','init','--bare',str(cache)],check=True,capture_output=True)
    if subprocess.run(['git','--git-dir',str(cache),'cat-file','-e',commit+'^{commit}'],capture_output=True).returncode:
        subprocess.run(['git','--git-dir',str(cache),'fetch','--depth','1','--no-tags',URL,
                        commit+':refs/qualified/'+commit],check=True,capture_output=True,timeout=180)
    tree=subprocess.check_output(['git','--git-dir',str(cache),'rev-parse',commit+'^{tree}'],text=True).strip()
    raw=subprocess.check_output(['git','--git-dir',str(cache),'archive','--format=tar',commit])
    with tempfile.TemporaryDirectory(prefix='rill-source-proof-') as directory:
        expected=Path(directory)
        base_files=[]
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
            for member in archive.getmembers():
                relative=Path(member.name)
                if relative.is_absolute() or '..' in relative.parts:raise ValueError('invalid Git source path')
                path=expected/relative
                if member.isdir():path.mkdir(parents=True,exist_ok=True);continue
                if not member.isfile() or member.size>128*1024*1024:raise ValueError('unsupported Git source member')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
                base_files.append(relative)
        for patch in metadata['upstream'].get('sourcePatches',[]):
            subprocess.run(['git','apply',str((repo_root/patch['path']).resolve())],cwd=expected,
                           check=True,capture_output=True)
        for relative in base_files:
            if not (expected/relative).exists() and (actual_source/relative).exists():
                raise ValueError('source patch deletion was not applied: '+str(relative))
        digest=hashlib.sha256()
        expected_files=set()
        for path in sorted(expected.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(expected)
            expected_files.add(relative.as_posix())
            actual=actual_source/relative
            content=path.read_bytes()
            if not actual.is_file() or actual.is_symlink() or actual.read_bytes()!=content:
                raise ValueError('SDK built source differs from immutable Git tree + patches: '+str(relative))
            digest.update(str(relative).encode()+b'\0'+hashlib.sha256(content).digest())
        # SDK/Cargo outputs are outside the source identity. Other extra input
        # files (especially .cargo/config.toml or auto-discovered Rust modules)
        # must not be accepted merely because all original files still match.
        generated={'target','.pc','.pkgdir','ipkg-install'}
        stamp=re.compile(r'\.(?:prepared_[a-f0-9]{32,64}(?:_[a-f0-9]{32,64})?(?:_check)?|configured_[a-f0-9]{32,64}|built(?:_check)?)')
        for directory,dirs,files in os.walk(actual_source,followlinks=False):
            parent=Path(directory)
            for name in list(dirs):
                path=parent/name
                if path.is_symlink():raise ValueError('unexpected SDK source symlink: '+str(path.relative_to(actual_source)))
                if parent==actual_source and (name in generated or re.fullmatch(r'(?:ipkg|apk)-[a-z0-9_+.-]+',name)):
                    dirs.remove(name)
            for name in files:
                path=parent/name;relative=path.relative_to(actual_source).as_posix()
                if path.is_symlink() or not path.is_file():raise ValueError('unexpected SDK source member: '+relative)
                if relative in expected_files:continue
                # OpenWrt package.mk/rdep writes its dependency-list output here.
                if parent==actual_source and (name=='.dep_files' or stamp.fullmatch(name)):continue
                # SDK 25 package-defaults.mk writes the source timestamp.
                if parent==actual_source and name=='version.date' and re.fullmatch(rb'[0-9]+\n',path.read_bytes()):continue
                raise ValueError('unexpected SDK source input outside immutable tree + patches: '+relative)
    return {'baseCommit':commit,'gitTree':tree,'patchedTreeSha256':digest.hexdigest()}
