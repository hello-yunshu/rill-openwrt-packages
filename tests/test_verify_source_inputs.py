from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.verify_source_inputs import verify


class ImmutableSourceInputs(unittest.TestCase):
    def test_exact_tree_passes_but_mutated_source_and_non_sha_input_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);repo=root/'repo';repo.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True,stderr=subprocess.DEVNULL).strip()
            git('init');git('config','user.name','fixture');git('config','user.email','fixture@example.test')
            (repo/'source.rs').write_text('reviewed source\n');git('add','source.rs');git('commit','-m','fixture')
            commit=git('rev-parse','HEAD');cache=root/'cache.git'
            subprocess.run(['git','clone','--bare',str(repo),str(cache)],check=True,capture_output=True)
            actual=root/'actual';actual.mkdir();shutil.copyfile(repo/'source.rs',actual/'source.rs')
            metadata={'upstream':{'commit':commit}}
            result=verify(root,metadata,actual,cache)
            self.assertEqual(result['baseCommit'],commit)
            self.assertEqual(result['gitTree'],git('rev-parse','HEAD^{tree}'))
            (actual/'target').mkdir();(actual/'target/cache').write_text('generated output')
            (actual/'.built').touch()
            (actual/'.dep_files').write_text('SDK dependency list\n')
            (actual/'version.date').write_text('1788239434\n')
            self.assertEqual(verify(root,metadata,actual,cache),result)
            cargo=actual/'.cargo';cargo.mkdir();(cargo/'config.toml').write_text('[build]\nrustc-wrapper="injected"\n')
            with self.assertRaisesRegex(ValueError,'unexpected SDK source input'):verify(root,metadata,actual,cache)
            shutil.rmtree(cargo)
            (actual/'source.rs').write_text('injected source\n')
            with self.assertRaisesRegex(ValueError,'differs'):verify(root,metadata,actual,cache)
            with self.assertRaisesRegex(ValueError,'immutable'):verify(root,{'upstream':{'commit':'--unsafe'}},actual,cache)
