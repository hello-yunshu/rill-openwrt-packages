#!/usr/bin/env python3
"""Assemble dual-channel evidence from inspected SDK target records."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

try:
    from .openwrt_targets import entries
except ImportError:
    from openwrt_targets import entries

ROOT=Path(__file__).resolve().parents[1]
IDENTITY=('openwrtVersion','target','subtarget','packageArch','rustTarget','pkgtype')


def assemble(records,package_commit,run_id,run_attempt,local=False):
    expected={tuple(str(row[key]) for key in IDENTITY) for row in entries()}
    channels={}
    for channel in ('stable','preview'):
        selected=[record for record in records if record.get('channel')==channel]
        identities=[tuple(str(row.get(key,'')) for key in IDENTITY) for row in selected]
        if set(identities)!=expected or len(identities)!=len(expected):
            raise ValueError(channel+': missing, duplicate or unexpected SDK target record')
        build=selected[0]['build']
        upstream=selected[0]['upstream']
        package=selected[0]['package']
        for record in selected:
            if any(record[key]!=value for key,value in [('build',build),('upstream',upstream),('package',package)]):
                raise ValueError(channel+': inconsistent source/package/build identity')
        rows=[{key:value for key,value in row.items() if key not in {'channel','build','upstream','package','schemaVersion'}} for row in selected]
        channels[channel]={**package,'upstream':upstream,'build':build,'targets':rows,'qualificationState':'PASS'}
    if len(records)!=2*len(expected):raise ValueError('extra channel or target evidence')
    stable=channels['stable'];preview=channels['preview']
    preview['upstreamCommit']=preview['upstream']['commit']
    result={'schemaVersion':3,'packageCommit':package_commit,'runId':run_id,'runAttempt':run_attempt,
            'package':{key:value for key,value in stable.items() if key not in {'upstream','build','targets','qualificationState'}},
            'upstream':stable['upstream'],'build':stable['build'],'targets':stable['targets'],
            'previewPackage':preview,'qualificationState':'automated-qualification',
            'releaseEligible':True}
    if local:
        result.update(qualificationState='local-package-qualification',releaseEligible=False)
        result['localRunId']=str(run_id);result['runId']=None;result['runAttempt']=None
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=Path,required=True)
    parser.add_argument('--package-commit',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--run-attempt',type=int,required=True)
    parser.add_argument('--local',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--artifacts-dir',type=Path)
    parser.add_argument('--apk',default='apk')
    args=parser.parse_args()
    files=sorted(args.records.rglob('target-qualification-*.json'))
    records=[json.loads(path.read_text()) for path in files]
    result=assemble(records,args.package_commit,args.run_id if args.local else int(args.run_id),args.run_attempt,args.local)
    if not args.local:
        if not args.artifacts_dir:
            parser.error('published qualification requires --artifacts-dir for actual byte verification')
        try:
            from .verify_qualification import verify
        except ImportError:
            from verify_qualification import verify
        expected=argparse.Namespace(channel='preview',package_commit=args.package_commit,
            version=None,release=None,upstream_repository=None,upstream_tag=None,upstream_commit=None,
            openwrt_version=None,package_arch=None,pkgtype=None,artifacts_dir=args.artifacts_dir,apk=args.apk)
        errors=verify(result,expected)
        if errors:raise ValueError('; '.join(errors))
    descriptor,name=tempfile.mkstemp(prefix='.qualification-',dir=args.output.parent)
    try:
        with os.fdopen(descriptor,'w') as stream:
            stream.write(json.dumps(result,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,args.output)
    finally:
        Path(name).unlink(missing_ok=True)


if __name__=='__main__':main()
