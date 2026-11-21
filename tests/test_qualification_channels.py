import argparse
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import inspect_runtime_package
from scripts.verify_qualification import verify
from scripts.openwrt_targets import entries


def arguments(channel='stable'):
    return argparse.Namespace(package_commit=None, version=None, release=None,
        upstream_repository=None, upstream_tag=None, upstream_commit=None,
        openwrt_version=None, package_arch=None, pkgtype=None, channel=channel)


class StableQualificationTests(unittest.TestCase):
    def evidence(self):
        rows=[]
        for item in entries():
            arm=item['packageArch']=='arm_cortex-a7_neon-vfpv4'
            loader=item.get('elfInterpreter') or ('/lib/ld-musl-x86_64.so.1' if item['packageArch']=='x86_64' else '/lib/ld-musl-aarch64.so.1')
            rows.append({**item,'artifact':f"rill-runtime-v{item['openwrtVersion']}-{item['packageArch']}.{item['pkgtype']}",
                'sha256':'d'*64,'binarySha256':'e'*64,'qualificationState':'PASS',
                'sdk':{'openwrtVersion':item['openwrtVersion'],'archiveSha256':'a'*64,'configurationLogSha256':'b'*64,
                    'feeds':{'base':{'source':'official-base-tag','commit':'a'*40},'packages':{'source':'official-packages-commit','commit':'b'*40}}},
                'resolvedWasmtime':{'engine':'wasmtime v49.0.6','features':['component-model','runtime','cranelift','pulley']},
                'securityAudit':{'sourceLockSha256':'c'*64,'vulnerabilityCount':0,'warnings':{},'ignoredAdvisories':[],
                    'database':{'last-commit':'a'*40,'last-updated':'2026-11-21T00:00:00Z'}},
                'binary':'/usr/bin/rill-runtime','interpreter':loader,'elfClass':'ELF32' if arm else 'ELF64','elfABI':item.get('elfABI'),'endianness':'little',
                'packageMetadata':{'name':'rill-runtime','version':'1.5.6-r8','architecture':item['packageArch'],'conflicts':['rill-runtime-preview']}})
        return {'schemaVersion':4,'qualificationState':'automated-qualification','releaseEligible':True,
            'packageCommit':'f'*40,'runId':123,'runAttempt':2,
            'package':{'name':'rill-runtime','recipe':'package/rill-runtime/Makefile','binary':'/usr/bin/rill-runtime','version':'1.5.6','release':8},
            'upstream':{'commit':'1e962a82443088229714877eee98617f1596eee8','sourceType':'immutable-git-commit',
                'repository':'hello-yunshu/rill-ml','version':'1.5.6','tag':'stable-main-1e962a8','sourcePatches':[]},
            'build':{'sourceLockSha256':'c'*64,'rustToolchain':'1.96.0','runtimeFeatures':['wasm'],'defaultFeatures':True,'sourcePatches':[],
                'verifiedSource':{'baseCommit':'1e962a82443088229714877eee98617f1596eee8','gitTree':'b'*40,'patchedTreeSha256':'c'*64}},'targets':rows}

    def test_stable_only_matrix_passes(self):
        self.assertEqual(verify(self.evidence(),arguments()),[])

    def test_actual_package_inspection_allows_missing_abi_for_non_arm_targets(self):
        data=self.evidence()
        by_arch={row['packageArch']:row for row in data['targets']}
        def inspected(path,name,architecture,version,tool='apk'):
            row=by_arch[architecture]
            fields=('sha256','binarySha256','elfClass','endianness','elfMachine','interpreter','packageMetadata')
            result={field:row.get(field) for field in fields}
            if architecture=='arm_cortex-a7_neon-vfpv4':
                result['elfABI']=row['elfABI']
            return result
        args=arguments();args.artifacts_dir=Path(tempfile.gettempdir());args.apk='apk'
        with patch.object(inspect_runtime_package,'inspect',side_effect=inspected):
            self.assertEqual(verify(data,args),[])

    def test_rejects_preview_and_malformed_stable_evidence(self):
        self.assertTrue(verify(self.evidence(),arguments('preview')))
        for mutation in (
            lambda d:d['targets'].pop(),
            lambda d:d['targets'][0].pop('binarySha256'),
            lambda d:d['targets'][0].update(qualificationState='SKIPPED'),
            lambda d:d['targets'][0]['packageMetadata'].update(architecture='wrong'),
            lambda d:d['targets'][0]['securityAudit'].update(vulnerabilityCount=1),
            lambda d:d.update(runAttempt=0),
            lambda d:d.update(releaseEligible=False),
        ):
            data=self.evidence();mutation(data)
            with self.subTest(mutation=mutation):self.assertTrue(verify(data,arguments()))

    def test_armv7_still_requires_hard_float_identity(self):
        data=self.evidence();row=next(x for x in data['targets'] if x['packageArch']=='arm_cortex-a7_neon-vfpv4')
        self.assertEqual(row['elfClass'],'ELF32');self.assertEqual(row['elfABI'],'EABI5 hard-float')
        row['elfABI']='EABI5 soft-float'
        self.assertTrue(verify(data,arguments()))

if __name__=='__main__':unittest.main()
