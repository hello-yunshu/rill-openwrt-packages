#!/usr/bin/env python3
"""Exercise the canonical Runtime APK's real ownership lifecycle with apk-tools."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess
from pathlib import Path
from inspect_runtime_package import apk, runtime_payload


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(tool, stable, output):
    tool=tool.resolve();package=stable.resolve();record=json.loads(subprocess.check_output([str(tool),'--allow-untrusted','adbdump','--format','json',str(package)],text=True))
    identity,payload=apk(package,str(tool),'rill-runtime');binary,_=runtime_payload(payload,'rill-runtime','apk')
    assert '!rill-runtime-preview>=0' in record['info'].get('depends',[]),'Stable APK must conflict with the retired Preview package'
    arch=identity['architecture'];output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    empty=output/'empty-payload';empty.mkdir();libc=output/'libc-fixture.apk'
    subprocess.run([str(tool),'mkpkg','--info','name:libc','--info','version:1-r0','--info','arch:noarch','--info','license:MIT','--files',str(empty),'--output',str(libc)],check=True,capture_output=True)
    root=output/'root';(root/'etc/apk/keys').mkdir(parents=True);(root/'etc/apk/repositories').write_text('');(root/'etc/apk/world').write_text('\n')
    state=root/'etc/rill/ownership-test-state';state.parent.mkdir();state.write_bytes(b'preserve user state\n')
    usermode=[] if os.geteuid()==0 else ['--usermode']
    base=[str(tool),*usermode,'--root',str(root),'--arch',arch,'--allow-untrusted','--no-network','--cache=no','--repositories-file',str(root/'etc/apk/repositories'),'--keys-dir',str(root/'etc/apk/keys')]
    def run(*args):
        cmd=[*base,'--no-scripts',*map(str,args)];p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if p.returncode:raise AssertionError(p.stdout+p.stderr)
    run('add','--initdb',libc);binary_path=root/'usr/bin/rill-runtime'
    run('add',package);assert sha(binary_path)==hashlib.sha256(binary).hexdigest() and state.read_bytes()==b'preserve user state\n'
    run('del','rill-runtime');assert not binary_path.exists() and state.read_bytes()==b'preserve user state\n'
    run('add',package);assert sha(binary_path)==hashlib.sha256(binary).hexdigest()
    result={'scope':'stable-apk-ownership','packageSha256':sha(package),'binarySha256':hashlib.sha256(binary).hexdigest(),
            'installUninstallReinstallPassed':True,'userStatePreserved':True,'scriptsRun':False,'routerValidated':False}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',required=True,type=Path);parser.add_argument('--stable',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.apk,args.stable,args.output),indent=2))
if __name__=='__main__':main()
