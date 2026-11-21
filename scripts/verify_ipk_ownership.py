#!/usr/bin/env python3
"""Exercise the canonical Runtime IPK's real ownership lifecycle with opkg."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess
from pathlib import Path
from inspect_runtime_package import ipk


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(opkg, stable, output):
    package=stable.resolve(); info,contents=ipk(package.read_bytes())
    assert info['name']=='rill-runtime'
    arch=info['architecture']; binary=contents['usr/bin/rill-runtime']
    output=output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    empty=output/'empty-conf';empty.mkdir();env=dict(os.environ,OPKG_CONF_DIR=str(empty))
    root=output/'root';db=root/'usr/lib/opkg';(db/'info').mkdir(parents=True)
    (db/'info/libc.list').write_text('')
    (db/'status').write_text(f'Package: libc\nVersion: 1\nArchitecture: {arch}\nStatus: install ok installed\n\n')
    state=root/'etc/rill/ownership-test-state';state.parent.mkdir(parents=True);state.write_bytes(b'preserve user state\n')
    config=root/'opkg.conf';config.write_text(f'arch all 1\narch {arch} 10\ndest root {root}\nlists_dir ext {root}/usr/lib/opkg/lists\n')
    (root/'tmp').mkdir();log=output/'commands.jsonl'
    def run(*args):
        cmd=[str(opkg.resolve()),'-f',str(config),*map(str,args)]
        result=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=120)
        with log.open('a') as stream:stream.write(json.dumps({'command':cmd,'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})+'\n')
        assert result.returncode==0,result.stdout+result.stderr
    target=root/'usr/bin/rill-runtime'
    run('install',package);assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(binary).digest()
    installed=run('list-installed')
    run('remove','rill-runtime');assert not target.exists() and state.read_bytes()==b'preserve user state\n'
    run('install',package);assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(binary).digest()
    result={'scope':'stable-ipk-ownership','packageSha256':digest(package),'binarySha256':hashlib.sha256(binary).hexdigest(),
            'installUninstallReinstallPassed':True,'userStatePreserved':True,'routerValidated':False}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opkg',required=True,type=Path);parser.add_argument('--stable',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.opkg,args.stable,args.output),indent=2))
if __name__=='__main__':main()
