#!/usr/bin/env python3
"""Reject stale SDK feeds even when the feeds updater returns success."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess


def inspect(sdk):
    result={}
    for line in (sdk/'feeds.conf.default').read_text().splitlines():
        fields=shlex.split(line,comments=True)
        if not fields:continue
        # New SDKs place feed options before the feed name. They must not be
        # mistaken for the name, silently omitting base from provenance.
        while len(fields)>1 and fields[1].startswith('--'):
            option=fields.pop(1)
            if option!='--root=package':raise ValueError('unsupported SDK feed option: '+option)
        if len(fields)<3 or fields[1] not in ('base','packages'):continue
        name=fields[1];source=fields[2];checkout=sdk/'feeds'/name
        head=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
        if '^' in source:
            expected=source.rsplit('^',1)[1]
            if not re.fullmatch('[a-f0-9]{40}',expected):raise ValueError('feed has no exact commit')
        elif ';' in source:
            tag=source.rsplit(';',1)[1]
            if not re.fullmatch(r'v\d+\.\d+\.\d+',tag):raise ValueError('base feed must use an immutable SDK release tag')
            expected=subprocess.check_output(['git','-C',str(checkout),'rev-parse','refs/tags/'+tag+'^{commit}'],text=True).strip()
        else:raise ValueError('unversioned SDK feed')
        if head!=expected:raise ValueError('SDK feed HEAD differs from its pinned identity: '+name)
        result[name]={'source':source,'commit':head}
    if set(result)!= {'base','packages'}:raise ValueError('SDK base/packages feed provenance missing')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('sdk',type=Path)
    args=parser.parse_args();print(json.dumps(inspect(args.sdk),indent=2))


if __name__=='__main__':main()
