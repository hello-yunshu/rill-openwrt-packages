#!/usr/bin/env python3
"""Create a scoped automation PR without rewriting an existing remote branch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(*command, capture=True):
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='main')
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--title',required=True)
    parser.add_argument('--body-file',required=True,type=Path)
    parser.add_argument('--qualification-workflow',help='dispatch the required check once for an exact candidate SHA')
    parser.add_argument('paths',nargs='+')
    args=parser.parse_args()
    if args.qualification_workflow and args.qualification_workflow not in {'qualify.yml','ci.yml'}:
        parser.error('only the reviewed qualification/consumer CI workflows may be dispatched')
    paths=args.paths
    if subprocess.run(['git','diff','--quiet','HEAD','--',*paths]).returncode==0:
        print('No dependency change; no branch, commit, push or PR required.')
        return 0
    changed=set(run('git','diff','--name-only','HEAD').splitlines()) | set(run('git','diff','--cached','--name-only').splitlines())
    if changed-set(paths):raise RuntimeError('unrelated tracked changes; sync requires a scoped clean checkout')
    run('git','check-ref-format','refs/heads/'+args.base)
    run('git','ls-remote','--exit-code','origin','refs/heads/'+args.base)
    digest=hashlib.sha256()
    for name in sorted(paths):
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('owned paths must be repository relative')
        digest.update(name.encode()+b'\0'+path.read_bytes()+b'\0')
    branch=args.prefix+'-'+digest.hexdigest()[:20]
    run('git','check-ref-format','refs/heads/'+branch)
    # Read PR state before any remote mutation, including closed unmerged PRs.
    pulls=json.loads(run('gh','pr','list','--base',args.base,'--head',branch,
        '--state','all','--json','number,state,mergedAt'))
    if any(p['state']=='CLOSED' and not p.get('mergedAt') for p in pulls):
        raise RuntimeError('automation PR was closed unmerged; manual review required')
    remote=run('git','ls-remote','origin','refs/heads/'+branch)
    if remote:
        run('git','fetch','--no-tags','origin','refs/heads/'+branch)
        if subprocess.run(['git','diff','--quiet','FETCH_HEAD','--',*paths]).returncode:
            raise RuntimeError('existing automation branch differs; refusing to overwrite it')
    else:
        run('git','config','--local','user.name','github-actions[bot]')
        run('git','config','--local','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        run('git','switch','-c',branch)
        run('git','add','--',*paths)
        run('git','commit','-m',args.title)
        # gh supplies the step-scoped token; never persist it in the repository.
        run('git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential',
            'push','origin','HEAD:refs/heads/'+branch)
    if not any(p['state']=='OPEN' for p in pulls):
        run('gh','pr','create','--base',args.base,'--head',branch,'--title',args.title,
            '--body-file',str(args.body_file),capture=False)
    if args.qualification_workflow:
        remote_head=run('git','ls-remote','origin','refs/heads/'+branch).split()[0]
        runs=json.loads(run('gh','run','list','--workflow',args.qualification_workflow,
            '--branch',branch,'--limit','100','--json','headSha,status,conclusion'))
        matching=[item for item in runs if item['headSha']==remote_head]
        if not matching:
            run('gh','workflow','run',args.qualification_workflow,'--ref',branch,capture=False)
        elif not any(item['status'] in ('queued','in_progress','waiting','pending') or item.get('conclusion')=='success' for item in matching):
            raise RuntimeError('candidate qualification failed; review it before retrying')
    print('Dependency PR prepared. Required qualification/consumer checks must run before merge.')
    print('PR creation/dispatch is not qualification; the exact-SHA checks must reach success before merge.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
