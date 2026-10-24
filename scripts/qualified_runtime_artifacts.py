#!/usr/bin/env python3
"""Fetch exact-attempt qualified Runtime bytes and reject provenance drift."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import zipfile

REPO='hello-yunshu/rill-openwrt-packages'
LIMIT=128*1024*1024


def api(path):
    return json.loads(subprocess.check_output(['gh','api',path],text=True,timeout=45))


def artifact_bytes(identifier):
    # gh handles authenticated GitHub redirects without writing a token to disk.
    data=subprocess.check_output(['gh','api',f'repos/{REPO}/actions/artifacts/{identifier}/zip'],timeout=180)
    if len(data)>LIMIT:raise ValueError('qualification artifact exceeds size limit')
    return data


def member(raw,name):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        matches=[item for item in archive.infolist() if Path(item.filename).name==name and not item.is_dir()]
        if len(matches)!=1:raise ValueError('expected exactly one artifact member: '+name)
        item=matches[0]
        if item.file_size>LIMIT or stat.S_ISLNK(item.external_attr>>16):raise ValueError('invalid artifact member')
        return archive.read(item)


def require_run(run,package_commit,attempt):
    if run.get('head_sha')!=package_commit or run.get('status')!='completed' or run.get('conclusion')!='success':
        raise ValueError('package qualification run is not successful for the exact commit')
    if run.get('run_attempt')!=attempt or str(run.get('path','')).split('@')[0]!='.github/workflows/qualify.yml':
        raise ValueError('qualification attempt/workflow mismatch')


def artifacts(run_id):
    result=[];page=1
    while True:
        data=api(f'repos/{REPO}/actions/runs/{run_id}/artifacts?per_page=100&page={page}')
        rows=data.get('artifacts',[]);result.extend(rows)
        if len(rows)<100:break
        page+=1
        if page>10:raise ValueError('unexpected qualification artifact count')
    return result


def find_artifact(rows,name):
    matches=[row for row in rows if row.get('name')==name and not row.get('expired')]
    if len(matches)!=1:raise ValueError('missing, expired or duplicate exact-attempt artifact: '+name)
    size=matches[0].get('size_in_bytes')
    if type(size) is not int or not 0<size<=LIMIT:raise ValueError('invalid or oversized artifact')
    return matches[0]['id']


def fetch_manifest(run_id,attempt,package_commit,package_dir):
    run=api(f'repos/{REPO}/actions/runs/{run_id}')
    require_run(run,package_commit,attempt)
    rows=artifacts(run_id)
    identifier=find_artifact(rows,f'qualification-evidence-{run_id}-{attempt}')
    raw=member(artifact_bytes(identifier),'qualification.json')
    data=json.loads(raw)
    if data.get('schemaVersion')!=3 or data.get('runId')!=run_id or data.get('runAttempt')!=attempt:
        raise ValueError('qualification manifest identity mismatch')
    verifier=package_dir/'scripts/verify_qualification.py'
    with tempfile.TemporaryDirectory(prefix='rill-manifest-') as directory:
        path=Path(directory)/'qualification.json';path.write_bytes(raw)
        subprocess.run(['python3','-B',str(verifier),str(path),'--channel','preview','--package-commit',package_commit],check=True,capture_output=True,timeout=60)
    return data,raw,rows


def fetch_qualified(contract,package_dir,openwrt_version,architecture,pkgtype,output,apk="apk",channel="preview"):
    if channel not in ('stable','preview'):raise ValueError('unsupported Runtime channel')
    qualification=contract['qualification'];run_id=qualification['runId'];attempt=qualification.get('runAttempt')
    if type(attempt) is not int or attempt<=0:raise ValueError('contract has no qualified run attempt')
    data,raw,rows=fetch_manifest(run_id,attempt,contract['openwrtPackage']['commit'],package_dir)
    if hashlib.sha256(raw).hexdigest()!=qualification.get('manifestSha256'):
        raise ValueError('qualification manifest digest differs from contract')
    preview=data['previewPackage'] if channel=='preview' else data['package']
    upstream=preview['upstream'] if channel=='preview' else data['upstream']
    expected_commit=contract['preview']['commit'] if channel=='preview' else contract['resolved']['upstreamCommit']
    if upstream['commit']!=expected_commit:
        raise ValueError('qualified Preview source differs from consumer contract')
    package=contract['openwrtPackage']
    if any(preview[key]!=package[field] for key,field in [('name','package'),('version','packageVersion'),('release','packageRelease')]):
        raise ValueError('qualified Preview package differs from consumer contract')
    targets=preview['targets'] if channel=='preview' else data['targets']
    matches=[row for row in targets if row['openwrtVersion']==openwrt_version and row['packageArch']==architecture and row['pkgtype']==pkgtype]
    if len(matches)!=1:raise ValueError('qualified target does not resolve uniquely')
    target=matches[0]
    identifier=find_artifact(rows,f"{'rill-runtime-preview' if channel=='preview' else 'rill-runtime'}-{pkgtype}-v{openwrt_version}-{architecture}-{run_id}-{attempt}")
    payload=member(artifact_bytes(identifier),target['artifact'])
    if hashlib.sha256(payload).hexdigest()!=target['sha256']:
        raise ValueError('downloaded qualified package digest mismatch')
    with tempfile.TemporaryDirectory(prefix='qualified-preview-') as directory:
        candidate=Path(directory)/target['artifact'];candidate.write_bytes(payload)
        inspected=json.loads(subprocess.check_output(['python3','-B',str(package_dir/'scripts/inspect_runtime_package.py'),
            str(candidate),'--name',preview['name'],'--architecture',architecture,
            '--version',f"{preview['version']}-r{preview['release']}",'--apk',apk],text=True,timeout=60))
        for field in ('binarySha256','sha256','packageMetadata','elfClass','endianness','elfMachine'):
            if inspected[field]!=target[field]:raise ValueError('actual qualified payload differs: '+field)
    output.mkdir(parents=True,exist_ok=True)
    path=output/target['artifact']
    if path.exists() and path.read_bytes()!=payload:raise ValueError('refusing to overwrite different existing package bytes')
    manifest=output/'qualification.json'
    if manifest.exists() and manifest.read_bytes()!=raw:raise ValueError('refusing to overwrite different qualification manifest')
    path.write_bytes(payload)
    manifest.write_bytes(raw)
    return path,target


def fetch_preview(*args, **kwargs):
    return fetch_qualified(*args, **kwargs, channel="preview")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--channel',choices=['stable','preview'],required=True)
    parser.add_argument('--package-dir',type=Path,required=True)
    parser.add_argument('--openwrt-version',required=True)
    parser.add_argument('--architecture',required=True)
    parser.add_argument('--pkgtype',choices=['ipk','apk'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apk',default='apk')
    args=parser.parse_args()
    path,target=fetch_qualified(json.loads(args.contract.read_text()),args.package_dir,args.openwrt_version,args.architecture,args.pkgtype,args.output,args.apk,args.channel)
    print(json.dumps({'package':str(path),'qualifiedTarget':target},indent=2))


if __name__=='__main__':main()
