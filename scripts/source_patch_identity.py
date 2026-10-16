#!/usr/bin/env python3
"""Bind downstream security patches to the exact immutable upstream base."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re


def inspect(root,metadata,source_dir=None):
    upstream=metadata['upstream'];name=metadata['package']['name']
    records=upstream.get('sourcePatches',[])
    if not isinstance(records,list):raise ValueError('source patches must be a list')
    actual={str(path.relative_to(root)) for path in (root/'package'/name/'patches').rglob('*') if path.is_file() or path.is_symlink()}
    declared=set()
    for item in records:
        path=item.get('path','')
        relative=Path(path)
        if relative.is_absolute() or '..' in relative.parts or relative.suffix!='.patch' or not path.startswith(f'package/{name}/patches/'):
            raise ValueError('source patch is outside its canonical recipe')
        if path in declared:raise ValueError('duplicate source patch identity')
        declared.add(path)
        if item.get('baseCommit')!=upstream['commit']:raise ValueError('source patch requires explicit requalification for a new upstream base')
        if (root/relative).is_symlink():raise ValueError('source patch must be a regular recipe-owned file')
        digest=hashlib.sha256((root/relative).read_bytes()).hexdigest()
        if digest!=item.get('sha256'):raise ValueError('source patch digest mismatch')
        lock_digest=item.get('patchedSourceLockSha256','')
        if not re.fullmatch('[a-f0-9]{64}',lock_digest):raise ValueError('source patch has no qualified post-patch lock digest')
        if source_dir and hashlib.sha256((source_dir/'Cargo.lock').read_bytes()).hexdigest()!=lock_digest:
            raise ValueError('actual patched source lock differs from qualified source patch')
    if declared!=actual:raise ValueError('recipe patch set differs from declared source patch identities')
    return records
