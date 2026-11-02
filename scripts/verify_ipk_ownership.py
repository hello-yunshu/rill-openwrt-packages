#!/usr/bin/env python3
"""Exercise real Runtime IPKs with opkg in fresh, retained isolated roots.

The libc DB entry is an explicit dependency fixture: this verifies package
ownership and state preservation, not libc installation or router operation.
No force-overwrite, force-depends, or package maintainer scripts are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from inspect_runtime_package import ipk


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(opkg, stable, preview, output):
    packages = {'stable': stable.resolve(), 'preview': preview.resolve()}
    identities = {channel: ipk(path.read_bytes()) for channel, path in packages.items()}
    assert identities['stable'][0]['name'] == 'rill-runtime'
    assert identities['preview'][0]['name'] == 'rill-runtime-preview'
    arch = identities['stable'][0]['architecture']
    assert identities['preview'][0]['architecture'] == arch
    output.mkdir(parents=True, exist_ok=False)
    empty = output / 'empty-conf'
    empty.mkdir()
    env = dict(os.environ, OPKG_CONF_DIR=str(empty))
    results = []
    for channel in packages:
        other = 'preview' if channel == 'stable' else 'stable'
        root = output / (channel + '-first')
        info = root / 'usr/lib/opkg/info'
        info.mkdir(parents=True)
        (info / 'libc.list').write_text('')
        (root / 'usr/lib/opkg/status').write_text(
            'Package: libc\nVersion: 1\nArchitecture: ' + arch +
            '\nStatus: install ok installed\n\n')
        state = root / 'etc/rill/ownership-test-state'
        state.parent.mkdir(parents=True)
        state.write_bytes(b'preserve user state\n')
        config = root / 'opkg.conf'
        config.write_text(f'arch all 1\narch {arch} 10\ndest root {root}\n'
                          f'lists_dir ext {root}/usr/lib/opkg/lists\n')
        (root / 'tmp').mkdir()
        log = root / 'commands.jsonl'

        def run(*args, reject=False):
            command = [str(opkg.resolve()), '-f', str(config), *map(str, args)]
            p = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
            with log.open('a') as stream:
                stream.write(json.dumps({'command': command, 'exitCode': p.returncode,
                                         'stdout': p.stdout, 'stderr': p.stderr}) + '\n')
            if reject:
                assert p.returncode != 0, 'incompatible package unexpectedly accepted'
            else:
                assert p.returncode == 0, p.stdout + p.stderr
            return p

        name = identities[channel][0]['name']
        binary = root / 'usr/bin/rill-runtime'
        expected = hashlib.sha256(identities[channel][1]['usr/bin/rill-runtime']).hexdigest()
        run('install', packages[channel])
        assert digest(binary) == expected
        run('remove', name)
        assert not binary.exists() and state.read_bytes() == b'preserve user state\n'
        run('install', packages[channel])
        assert digest(binary) == expected
        run('install', packages[other], reject=True)
        assert digest(binary) == expected and state.read_bytes() == b'preserve user state\n'
        installed = run('list-installed').stdout
        assert name + ' - ' in installed
        assert identities[other][0]['name'] + ' - ' not in installed
        (root / 'status-after-rejection').write_bytes((root / 'usr/lib/opkg/status').read_bytes())
        # A file-clash failure can leave an opkg desired/not-installed record.
        # Complete a supported explicit switch, then remove it before returning.
        # This never overwrites a binary owned by another installed package.
        run('remove', name)
        assert not binary.exists()
        run('install', packages[other])
        other_hash = hashlib.sha256(identities[other][1]['usr/bin/rill-runtime']).hexdigest()
        assert digest(binary) == other_hash
        run('remove', identities[other][0]['name'])
        assert not binary.exists()
        run('install', packages[channel])
        assert digest(binary) == expected and state.read_bytes() == b'preserve user state\n'
        results.append({'first': channel, 'packageSha256': digest(packages[channel]),
                        'binarySha256': expected, 'rejectionPreservedOwner': True,
                        'removeReinstallPreservedState': True, 'explicitSwitchRecovery': True})
    result = {'scope': 'real-ipk-opkg-ownership', 'libc': 'dependency-db-fixture',
              'routerValidated': False, 'results': results}
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['opkg', 'stable', 'preview', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.opkg, args.stable, args.preview, args.output.resolve()), indent=2))


if __name__ == '__main__':
    main()
