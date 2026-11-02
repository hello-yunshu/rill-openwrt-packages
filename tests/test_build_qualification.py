import copy
import unittest
from scripts.build_qualification import assemble
from tests import test_qualification_channels as fixtures
from scripts.verify_qualification import verify


class EvidenceAssembly(unittest.TestCase):
    def records(self):
        evidence=fixtures.QualificationChannelTests().evidence()
        result=[]
        for channel in ('stable','preview'):
            package=evidence['package'] if channel=='stable' else evidence['previewPackage']
            upstream=evidence['upstream'] if channel=='stable' else package['upstream']
            build=evidence['build'] if channel=='stable' else package['build']
            rows=evidence['targets'] if channel=='stable' else package['targets']
            for row in rows:
                result.append({**row,'channel':channel,'upstream':upstream,'build':build,
                               'package':{key:value for key,value in package.items() if key in ['name','recipe','binary','version','release','channel']}})
        return result

    def test_complete_real_inspection_records_form_strict_manifest(self):
        self.assertEqual(verify(assemble(self.records(),'f'*40,123,2),fixtures.arguments()),[])

    def test_missing_duplicate_unknown_or_mixed_build_fails(self):
        base=self.records()
        mixed=copy.deepcopy(base);mixed[-1]['build']={**mixed[-1]['build'],'sourceLockSha256':'9'*64}
        for records in [base[:-1],base+[base[0]],base+[{'channel':'unknown'}],mixed]:
            with self.assertRaises(ValueError):assemble(records,'f'*40,123,2)

    def test_local_evidence_cannot_satisfy_release_verifier(self):
        candidate=assemble(self.records(),'f'*40,'local-proof',1,local=True)
        self.assertFalse(candidate['releaseEligible'])
        self.assertTrue(verify(candidate,fixtures.arguments()))
