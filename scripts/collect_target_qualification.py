#!/usr/bin/env python3
"""Inspect an SDK package and record its real source/feature/compiler inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from inspect_runtime_package import inspect
from openwrt_targets import entries
from build_toolchain import version
from verify_sdk_feeds import inspect as inspect_feeds
from source_patch_identity import inspect as inspect_patches
from verify_source_inputs import verify as verify_source

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--channel',choices=['stable','preview'],required=True)
    parser.add_argument('--openwrt-version',required=True)
    parser.add_argument('--architecture',required=True)
    parser.add_argument('--pkgtype',choices=['ipk','apk'],required=True)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--sdk-dir',type=Path,required=True)
    parser.add_argument('--sdk-archive-sha256',required=True)
    parser.add_argument('--config-log',type=Path,required=True)
    parser.add_argument('--source-cache',type=Path,default=Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))/'rill-qualified-source.git')
    parser.add_argument('--apk',default='apk')
    parser.add_argument('--cargo-audit',default='cargo-audit')
    parser.add_argument('--audit-db',type=Path,default=Path(tempfile.gettempdir())/'rill-rustsec-db')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    targets=[row for row in entries() if row['openwrtVersion']==args.openwrt_version and row['packageArch']==args.architecture and row['pkgtype']==args.pkgtype]
    if len(targets)!=1:raise ValueError('SDK target must resolve uniquely from registry')
    target=targets[0]
    filename='rill-runtime' if args.channel=='stable' else 'rill-runtime-preview'
    metadata=json.loads((ROOT/'metadata'/(filename+'.json')).read_text())
    package={**metadata['package'],'recipe':metadata['package']['canonicalRecipe']};upstream=dict(metadata['upstream'])
    if upstream.get('repository')!='https://github.com/hello-yunshu/rill-ml':raise ValueError('noncanonical upstream repository')
    upstream['repository']='hello-yunshu/rill-ml'
    if args.channel=='preview':package['channel']=metadata['channel']
    actual=inspect(args.package,package['name'],args.architecture,f"{package['version']}-r{package['release']}",args.apk)
    compiler=subprocess.check_output(['rustc','--version'],text=True).strip()
    if compiler.split()[1]!=version():raise ValueError('actual compiler differs from reviewed toolchain')
    cargo_env={**os.environ,'CARGO_HOME':str(args.sdk_dir/'dl/cargo')}
    tree=subprocess.check_output(['cargo','tree','--locked','--edges','normal,build','-p','rill-runtime','--target',target['rustTarget'],'--prefix','none','--format','{p}|{f}'],cwd=args.source_dir,text=True,env=cargo_env)
    engine={line.removesuffix(' (*)') for line in tree.splitlines() if line.startswith('wasmtime v')}
    if len(engine)!=1:raise ValueError('expected one resolved WASM engine')
    engine_name,features=engine.pop().split('|');features=set(features.split(','))
    if not {'component-model','runtime','pulley','cranelift'}<=features or 'component-model-async' in features:
        raise ValueError('default runtime WASM security boundary changed')
    patches=inspect_patches(ROOT,metadata,args.source_dir)
    source_identity=verify_source(ROOT,metadata,args.source_dir,args.source_cache)
    inventory=json.loads(subprocess.check_output(['cargo','metadata','--locked','--no-deps','--format-version','1'],cwd=args.source_dir,text=True,env=cargo_env))
    versions=[item['version'] for item in inventory['packages'] if item['name']=='rill-runtime']
    if versions!=[package['version']]:raise ValueError('actual source Runtime version differs from package metadata')
    lock=args.source_dir/'Cargo.lock'
    lock_digest=hashlib.sha256(lock.read_bytes()).hexdigest()
    audit_env={key:value for key,value in cargo_env.items() if key!='CARGO_NET_OFFLINE'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    audit_stem='security-audit-'+args.output.stem
    command=[args.cargo_audit,'audit','--db',str(args.audit_db),'--file',str(lock),'--json']
    try:
        audited=subprocess.run(command,text=True,capture_output=True,env=audit_env,timeout=180)
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
        args.output.with_name(audit_stem+'.json').write_text(decoded(error.stdout))
        args.output.with_name(audit_stem+'.stderr.log').write_text(decoded(error.stderr)+'\nsecurity audit timed out\n')
        raise ValueError('security audit timed out; partial evidence retained') from error
    args.output.with_name(audit_stem+'.json').write_text(audited.stdout)
    args.output.with_name(audit_stem+'.stderr.log').write_text(audited.stderr)
    audit=json.loads(audited.stdout)
    if audited.returncode or re.search(r'(?m)^error:',audited.stderr):
        raise ValueError('security audit failed or could not inspect the dependency index; raw evidence retained')
    if audit.get('vulnerabilities',{}).get('count')!=0 or audit.get('warnings') or audit.get('settings',{}).get('ignore'):
        raise ValueError('source lock has unresolved or ignored security findings')
    if hashlib.sha256(lock.read_bytes()).hexdigest()!=lock_digest:
        raise ValueError('source lock changed during audit')
    security={'sourceLockSha256':lock_digest,'database':audit['database'],
              'vulnerabilityCount':0,'warnings':{},'ignoredAdvisories':[]}
    if not re.fullmatch('[a-f0-9]{64}',args.sdk_archive_sha256):raise ValueError('missing SDK archive identity')
    config=args.config_log.read_bytes()
    if re.search(rb'(^|[\s])error:|recursive dependency detected',config):raise ValueError('SDK configuration evidence contains an error')
    sdk={'configurationLogSha256':hashlib.sha256(config).hexdigest(),'archiveSha256':args.sdk_archive_sha256,'openwrtVersion':args.openwrt_version,'feeds':inspect_feeds(args.sdk_dir)}
    result={'schemaVersion':1,'channel':args.channel,**target,**actual,
            'package':package,'upstream':upstream,'qualificationState':'PASS',
            'build':{'rustToolchain':compiler.split()[1],
                     'sourceLockSha256':hashlib.sha256((args.source_dir/'Cargo.lock').read_bytes()).hexdigest(),
                     'runtimeFeatures':['wasm'],'defaultFeatures':True,'sourcePatches':patches,'verifiedSource':source_identity},
            'sdk':sdk,'securityAudit':security,
            'resolvedWasmtime':{'engine':engine_name,'features':sorted(features)}}
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
