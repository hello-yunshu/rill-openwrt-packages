#!/usr/bin/env python3
"""Resolve the reviewed full-runtime compiler from one metadata source."""
import json
from pathlib import Path
import re


def version():
    data=json.loads((Path(__file__).resolve().parents[1]/'metadata/build-toolchain.json').read_text())
    value=data.get('rustToolchain','')
    if data.get('schemaVersion')!=1 or not re.fullmatch(r'\d+\.\d+\.\d+',value):
        raise ValueError('invalid build toolchain metadata')
    if data.get('runtimeDefaultFeatures') is not True or 'wasm' not in data.get('runtimeFeatures',[]):
        raise ValueError('default WASM runtime must remain enabled')
    return value


if __name__=='__main__':
    print(version())
