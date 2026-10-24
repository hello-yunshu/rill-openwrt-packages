import argparse
import copy
import unittest
from scripts.verify_qualification import verify
from scripts.openwrt_targets import entries


def arguments(channel='preview'):
    return argparse.Namespace(package_commit=None, version=None, release=None,
        upstream_repository=None, upstream_tag=None, upstream_commit=None,
        openwrt_version=None, package_arch=None, pkgtype=None, channel=channel)


class QualificationChannelTests(unittest.TestCase):
    def test_legacy_preview_summary_without_binary_identity_is_not_qualification(self):
        data={'schemaVersion':2,'qualificationState':'automated-qualification','releaseEligible':True,
              'package':{'name':'rill-runtime','recipe':'package/rill-runtime/Makefile'},
              'upstream':{'commit':'a'*40,'archiveSha256':'b'*64},
              'previewPackage':{'qualificationState':'PASS','upstreamCommit':'c'*40},
              'targets':[{'qualificationState':'PASS','sha256':'d'*64,'openwrtVersion':'24.10.8',
                          'packageArch':'x86_64','pkgtype':'ipk','binary':'/usr/bin/rill-runtime'}]}
        self.assertTrue(verify(data,arguments()),'summary cannot qualify Preview bytes')

    def test_historical_stable_reader_requires_explicit_opt_in(self):
        data={'schemaVersion':2,'qualificationState':'automated-qualification','releaseEligible':True,
              'package':{'name':'rill-runtime','recipe':'package/rill-runtime/Makefile'},
              'upstream':{'commit':'a'*40,'archiveSha256':'b'*64},
              'targets':[{'qualificationState':'PASS','sha256':'c'*64,'openwrtVersion':'24.10.8',
                          'packageArch':'x86_64','pkgtype':'ipk','binary':'/usr/bin/rill-runtime'}]}
        args=arguments('stable')
        self.assertTrue(verify(data,args))
        args.allow_legacy_stable=True
        self.assertEqual(verify(data,args),[])
        args.channel='preview'
        self.assertTrue(verify(data,args))

    def evidence(self):
        channels=[]
        for name in ('rill-runtime','rill-runtime-preview'):
            rows=[]
            for item in entries():
                rows.append({**item,'artifact':f"{name}-v{item['openwrtVersion']}-{item['packageArch']}.{item['pkgtype']}",
                    'sha256':'d'*64,'binarySha256':'e'*64,'qualificationState':'PASS',
                    'sdk':{'openwrtVersion':item['openwrtVersion'],'archiveSha256':'a'*64,'configurationLogSha256':'b'*64,
                        'feeds':{'base':{'source':'official-base-tag','commit':'a'*40},'packages':{'source':'official-packages-commit','commit':'b'*40}}},
                    'resolvedWasmtime':{'engine':'wasmtime v99.2.3','features':['component-model','runtime','cranelift','pulley']},
                    'securityAudit':{'sourceLockSha256':'c'*64,'vulnerabilityCount':0,'warnings':{},'ignoredAdvisories':[],
                        'database':{'last-commit':'a'*40,'last-updated':'2026-10-15T00:00:00Z'}},
                    'binary':'/usr/bin/rill-runtime','interpreter':'/lib/ld-musl-'+('x86_64' if item['packageArch']=='x86_64' else 'aarch64')+'.so.1','elfClass':'ELF64','endianness':'little',
                    'packageMetadata':{'name':name,'version':'1.5.6-r3','architecture':item['packageArch']}})
            channels.append({'name':name,'recipe':f'package/{name}/Makefile','binary':'/usr/bin/rill-runtime',
                'version':'1.5.6','release':3,'channel':'preview-exact-commit' if name.endswith('-preview') else 'stable',
                'upstream':{'commit':'a'*40,'archiveSha256':'b'*64,'repository':'hello-yunshu/rill-ml',
                    'version':'1.5.6','tag':'preview-exact-commit' if name.endswith('-preview') else 'v1.5.6'},
                'build':{'sourceLockSha256':'c'*64,'rustToolchain':'1.96.0','runtimeFeatures':['wasm'],'defaultFeatures':True,
                    'verifiedSource':{'baseCommit':'a'*40,'gitTree':'b'*40,'patchedTreeSha256':'c'*64}},
                'targets':rows})
        stable,preview=channels
        return {'schemaVersion':3,'qualificationState':'automated-qualification','releaseEligible':True,
                'packageCommit':'f'*40,'runId':123,'runAttempt':2,'package':stable,
                'upstream':stable['upstream'],'build':stable['build'],'targets':stable['targets'],
                'previewPackage':preview}

    def test_complete_two_channel_registry_passes(self):
        self.assertEqual(verify(self.evidence(),arguments()),[])

    def test_rejects_missing_or_replaced_channel_evidence(self):
        mutations=[
            lambda d:d['previewPackage']['targets'].pop(),
            lambda d:d['previewPackage']['targets'].append(copy.deepcopy(d['previewPackage']['targets'][0])),
            lambda d:d['previewPackage']['targets'][0].pop('binarySha256'),
            lambda d:d['previewPackage']['targets'][0].update(qualificationState='SKIPPED'),
            lambda d:d['previewPackage']['targets'][0]['packageMetadata'].update(architecture='wrong'),
            lambda d:d['previewPackage']['targets'][0].update(elfMachine='wrong'),
            lambda d:d['previewPackage']['build'].update(defaultFeatures=False),
            lambda d:d['previewPackage']['build'].pop('sourceLockSha256'),
            lambda d:d['previewPackage']['build'].pop('verifiedSource'),
            lambda d:d['previewPackage']['targets'][0].pop('securityAudit'),
            lambda d:d['previewPackage']['targets'][0]['securityAudit'].update(vulnerabilityCount=1),
            lambda d:d['previewPackage']['targets'][0]['securityAudit'].update(ignoredAdvisories=['RUSTSEC-test']),
            lambda d:d['previewPackage']['upstream'].update(repository='wrong/owner'),
            lambda d:d['previewPackage']['targets'][0].pop('sdk'),
            lambda d:d['previewPackage']['targets'][0].pop('resolvedWasmtime'),
            lambda d:d['previewPackage']['targets'][0]['resolvedWasmtime']['features'].append('component-model-async'),
            lambda d:d.update(runAttempt=0),
            lambda d:d.update(releaseEligible=False),
        ]
        for mutation in mutations:
            data=self.evidence();mutation(data)
            with self.subTest(mutation=mutation):self.assertTrue(verify(data,arguments()))

    def test_immutable_identity_includes_preview_binary_source_and_toolchain(self):
        from scripts.release_identity import semantic_identity
        original=self.evidence()
        expected=semantic_identity(original)
        for mutate in [
            lambda d:d['previewPackage']['targets'][0].update(binarySha256='f'*64),
            lambda d:d['previewPackage']['upstream'].update(commit='f'*40),
            lambda d:d['previewPackage']['build'].update(rustToolchain='1.97.0'),
        ]:
            changed=copy.deepcopy(original);mutate(changed)
            self.assertNotEqual(semantic_identity(changed),expected)
        repeat=copy.deepcopy(original);repeat.update(runId=987,runAttempt=9)
        self.assertEqual(semantic_identity(repeat),expected)
