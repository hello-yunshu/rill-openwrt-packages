#!/usr/bin/env python3
"""Fail-closed transport and immutable-attempt binding regressions."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('qualified',ROOT/'scripts/qualified_runtime_artifacts.py')
qualified=importlib.util.module_from_spec(spec);spec.loader.exec_module(qualified)


def zipped(name,content):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:archive.writestr(name,content)
    return buffer.getvalue()


class QualifiedBytes(unittest.TestCase):
    def fixture(self):
        payload=b'opaque package fixture; real payload parser is separately exercised'
        target={'artifact':'rill-runtime-preview-v24.10.8-x86_64.ipk','sha256':hashlib.sha256(payload).hexdigest(),
                'binarySha256':'e'*64,'openwrtVersion':'24.10.8','packageArch':'x86_64','pkgtype':'ipk',
                'packageMetadata':{'name':'rill-runtime-preview','version':'1.5.6-r3','architecture':'x86_64'},
                'elfClass':'ELF64','endianness':'little','elfMachine':'Advanced Micro Devices X86-64'}
        proof={'schemaVersion':3,'runId':123,'runAttempt':2,'packageCommit':'a'*40,
               'previewPackage':{'name':'rill-runtime-preview','version':'1.5.6','release':3,
                   'upstream':{'commit':'b'*40},'targets':[target]}}
        raw=json.dumps(proof).encode()
        contract={'preview':{'commit':'b'*40},'openwrtPackage':{'commit':'a'*40,'package':'rill-runtime-preview',
            'packageVersion':'1.5.6','packageRelease':3},
            'qualification':{'runId':123,'runAttempt':2,'manifestSha256':hashlib.sha256(raw).hexdigest()}}
        rows=[{'id':1,'name':'qualification-evidence-123-2','size_in_bytes':1024,'expired':False},
              {'id':2,'name':'rill-runtime-preview-ipk-v24.10.8-x86_64-123-2','size_in_bytes':1024,'expired':False}]
        run={'head_sha':'a'*40,'status':'completed','conclusion':'success','run_attempt':2,'path':'.github/workflows/qualify.yml'}
        return contract,proof,raw,rows,run,payload,target

    def test_matching_qualified_bytes_and_actual_binary_digest_are_required(self):
        contract,proof,raw,rows,run,payload,target=self.fixture()
        def api(path):return {'artifacts':rows} if '/artifacts?' in path else run
        def artifact(identifier):return zipped('qualification.json',raw) if identifier==1 else zipped(target['artifact'],payload)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'out'
            with patch.object(qualified,'api',api),patch.object(qualified,'artifact_bytes',artifact), \
                 patch.object(qualified.subprocess,'run'), \
                 patch.object(qualified.subprocess,'check_output',return_value=json.dumps(target)):
                path,_=qualified.fetch_preview(contract,Path(directory),'24.10.8','x86_64','ipk',output)
                self.assertEqual(path.read_bytes(),payload)
                bad=dict(target,binarySha256='f'*64)
                with patch.object(qualified.subprocess,'check_output',return_value=json.dumps(bad)):
                    with self.assertRaisesRegex(ValueError,'binarySha256'):
                        qualified.fetch_preview(contract,Path(directory),'24.10.8','x86_64','ipk',Path(directory)/'bad')
                self.assertFalse((Path(directory)/'bad').exists())

    def test_stable_consumer_uses_its_own_qualified_package_and_binary(self):
        contract,proof,raw,rows,run,payload,target=self.fixture()
        target['artifact']=target['artifact'].replace('rill-runtime-preview','rill-runtime')
        target['packageMetadata']['name']='rill-runtime'
        proof['package']={key:value for key,value in proof['previewPackage'].items() if key not in ('upstream','targets')}
        proof['package']['name']='rill-runtime';proof['upstream']={'commit':'c'*40};proof['targets']=[target]
        raw=json.dumps(proof).encode();contract['qualification']['manifestSha256']=hashlib.sha256(raw).hexdigest()
        contract['openwrtPackage']['package']='rill-runtime';contract['resolved']={'upstreamCommit':'c'*40}
        rows[1]['name']=rows[1]['name'].replace('rill-runtime-preview','rill-runtime')
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(qualified,'fetch_manifest',return_value=(proof,raw,rows)), \
                 patch.object(qualified,'artifact_bytes',return_value=zipped(target['artifact'],payload)), \
                 patch.object(qualified.subprocess,'check_output',return_value=json.dumps(target)):
                path,_=qualified.fetch_qualified(contract,Path(directory),'24.10.8','x86_64','ipk',Path(directory)/'out',channel='stable')
                self.assertEqual(path.read_bytes(),payload)

    def test_rejects_wrong_run_attempt_workflow_and_package_before_output(self):
        contract,proof,raw,rows,run,payload,target=self.fixture()
        mutations=[lambda r:r.update(head_sha='c'*40),lambda r:r.update(run_attempt=1),
                   lambda r:r.update(conclusion='failure'),lambda r:r.update(status='in_progress'),
                   lambda r:r.update(path='.github/workflows/other.yml')]
        for mutation in mutations:
            bad=copy.deepcopy(run);mutation(bad)
            with self.assertRaises(ValueError):qualified.require_run(bad,'a'*40,2)
        for mutate in [lambda r:r[0].update(expired=True),lambda r:r[0].update(size_in_bytes=qualified.LIMIT+1),
                       lambda r:r.append(copy.deepcopy(r[0]))]:
            bad=copy.deepcopy(rows);mutate(bad)
            with self.assertRaises(ValueError):qualified.find_artifact(bad,'qualification-evidence-123-2')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'bad'
            with patch.object(qualified,'fetch_manifest',return_value=(proof,raw,rows)), \
                 patch.object(qualified,'artifact_bytes',return_value=zipped(target['artifact'],b'tampered')):
                with self.assertRaisesRegex(ValueError,'digest mismatch'):
                    qualified.fetch_preview(contract,Path(directory),'24.10.8','x86_64','ipk',output)
                self.assertFalse(output.exists())

    def test_bad_manifest_digest_or_missing_attempt_never_writes(self):
        contract,proof,raw,rows,*_=self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            for mutate in [lambda d:d['qualification'].pop('runAttempt'),
                           lambda d:d['qualification'].update(manifestSha256='f'*64)]:
                bad=copy.deepcopy(contract);mutate(bad)
                output=Path(directory)/'out'
                with patch.object(qualified,'fetch_manifest',return_value=(proof,raw,rows)):
                    with self.assertRaises(ValueError):
                        qualified.fetch_preview(bad,Path(directory),'24.10.8','x86_64','ipk',output)
                self.assertFalse(output.exists())


if __name__=='__main__':unittest.main(verbosity=2)
