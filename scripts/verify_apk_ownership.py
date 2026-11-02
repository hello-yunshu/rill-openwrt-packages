#!/usr/bin/env python3
"""Verify actual Runtime APK ownership in isolated APK roots.

The unsigned empty libc APK is a declared dependency fixture. No scripts run;
this is ownership/state verification, independently of signed-repository gates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from inspect_runtime_package import apk, runtime_payload


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(tool, stable, preview, output):
    if not __debug__:
        raise RuntimeError('ownership verification requires assertions enabled')
    tool=tool.resolve();packages={'stable':stable.resolve(),'preview':preview.resolve()}
    output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    identities={};payloads={};metadata={}
    for channel,path in packages.items():
        name='rill-runtime' if channel=='stable' else 'rill-runtime-preview'
        record=json.loads(subprocess.check_output([str(tool),'--allow-untrusted','adbdump','--format','json',str(path)],text=True))
        metadata[channel]=record['info']
        identity,payload=apk(path,str(tool),name)
        binary,_=runtime_payload(payload,name,'apk')
        identities[channel]=identity;payloads[channel]=binary
    (output/'package-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    arch=identities['stable']['architecture']
    assert identities['preview']['architecture']==arch
    assert '!rill-runtime>=0' in metadata['preview'].get('depends',[]), 'Preview APK has no explicit Stable negative dependency'
    empty=output/'empty-payload';empty.mkdir()
    libc=output/'libc-fixture.apk'
    subprocess.run([str(tool),'mkpkg','--info','name:libc','--info','version:1-r0',
                    '--info','arch:noarch','--info','license:MIT',
                    '--info','description:Dependency-only ownership test fixture',
                    '--files',str(empty),'--output',str(libc)],check=True,capture_output=True)
    results=[]
    for channel in packages:
        other='preview' if channel=='stable' else 'stable'
        root=output/(channel+'-first');(root/'etc/apk/keys').mkdir(parents=True)
        (root/'etc/apk/repositories').write_text('')
        state=root/'etc/rill/ownership-test-state';state.parent.mkdir();state.write_bytes(b'preserve user state\n')
        usermode=[] if os.geteuid()==0 else ['--usermode']
        base=[str(tool),*usermode,'--root',str(root),'--arch',arch,'--allow-untrusted',
              '--no-network','--cache=no','--repositories-file',str(root/'etc/apk/repositories'),
              '--keys-dir',str(root/'etc/apk/keys')]
        def run(*args,reject=False):
            flags=['--no-scripts'] if args[0] in {'add','del','fix','upgrade'} else []
            command=[*base,*flags,*map(str,args)]
            p=subprocess.run(command,capture_output=True,text=True,timeout=120)
            with (root/'commands.jsonl').open('a') as stream:
                stream.write(json.dumps({'command':command,'exitCode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})+'\n')
            if reject:assert p.returncode!=0,'incompatible APK unexpectedly accepted'
            else:assert p.returncode==0,p.stdout+p.stderr
            return p.stdout
        run('add','--initdb',libc)
        name=identities[channel]['name'];other_name=identities[other]['name']
        binary=root/'usr/bin/rill-runtime'
        expected=hashlib.sha256(payloads[channel]).hexdigest()
        run('add',packages[channel]);assert sha(binary)==expected
        run('del',name);assert not binary.exists() and state.read_bytes()==b'preserve user state\n'
        run('add',packages[channel]);assert sha(binary)==expected
        world=(root/'etc/apk/world').read_bytes()
        run('add',packages[other],reject=True)
        assert sha(binary)==expected and state.read_bytes()==b'preserve user state\n'
        assert (root/'etc/apk/world').read_bytes()==world,'rejected install mutated APK world'
        installed=run('info').splitlines();assert name in installed and other_name not in installed
        (root/'installed-after-rejection.txt').write_text('\n'.join(installed)+'\n')
        run('del',name);assert not binary.exists()
        run('add',packages[other]);assert binary.read_bytes()==payloads[other]
        run('del',other_name);assert not binary.exists()
        run('add',packages[channel]);assert sha(binary)==expected
        assert state.read_bytes()==b'preserve user state\n'
        results.append({'first':channel,'packageSha256':sha(packages[channel]),'binarySha256':expected,
                        'rejectedInstallPreservedOwnerAndWorld':True,'removeReinstallAndExplicitSwitchPreservedState':True})
    result={'scope':'real-apk-ownership','libc':'unsigned-empty-dependency-fixture','scriptsRun':False,
            'signatureQualification':False,'routerValidated':False,'results':results}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['apk','stable','preview','output']:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.apk,args.stable,args.preview,args.output),indent=2))


if __name__=='__main__':main()
