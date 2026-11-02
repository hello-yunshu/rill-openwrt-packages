import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/open_sync_pr.py'

class SyncPrTests(unittest.TestCase):
    def test_local_git_reuse_noop_closed_pr_and_permission_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); remote=root/'remote.git'; work=root/'work'
            def git(*args,cwd=None):
                return subprocess.check_output(['git',*args],cwd=cwd,text=True,stderr=subprocess.DEVNULL).strip()
            git('init','--bare',str(remote))
            git('clone',str(remote),str(work));git('switch','-c','main',cwd=work)
            git('config','user.name','fixture',cwd=work);git('config','user.email','fixture@example.test',cwd=work)
            (work/'contract.json').write_text('old\n');git('add','contract.json',cwd=work)
            git('commit','-m','base',cwd=work);git('push','origin','main',cwd=work)
            tools=root/'tools';tools.mkdir();state=root/'prs.json';state.write_text('[]')
            gh=tools/'gh';gh.write_text('''#!/usr/bin/env python3
import json,os,sys,subprocess
from pathlib import Path
if os.environ.get('FAIL_GH'):raise SystemExit(22)
p=Path(os.environ['PR_STATE'])
if sys.argv[1:3]==['pr','list']:print(p.read_text())
elif sys.argv[1:3]==['pr','create']:p.write_text(json.dumps([{'number':1,'state':'OPEN','mergedAt':None}]))
elif sys.argv[1:3]==['run','list']:
 state=Path(os.environ['RUN_STATE']);print(state.read_text() if state.exists() else '[]')
elif sys.argv[1:3]==['workflow','run']:
 head=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+sys.argv[-1]],text=True).split()[0]
 Path(os.environ['RUN_STATE']).write_text(json.dumps([{'headSha':head,'status':'queued','conclusion':None}]))
 log=Path(os.environ['DISPATCH_LOG']);log.write_text(log.read_text()+'dispatch\\n' if log.exists() else 'dispatch\\n')
else:raise SystemExit(23)
''');gh.chmod(0o755)
            body=root/'body.md';body.write_text('Must pass exact candidate checks.\n')
            env={**os.environ,'PATH':str(tools)+os.pathsep+os.environ['PATH'],'PR_STATE':str(state),'RUN_STATE':str(root/'runs.json'),'DISPATCH_LOG':str(root/'dispatch.log')}
            def invoke(cwd=work,extra=None,dispatch=False):
                return subprocess.run(['python3','-B',str(SCRIPT),'--base','main','--prefix','automation/test',
                    '--title','fixture sync','--body-file',str(body),*(['--qualification-workflow','qualify.yml'] if dispatch else []),'contract.json'],cwd=cwd,env={**env,**(extra or {})},capture_output=True,text=True)
            config=(work/'.git/config').read_bytes()
            self.assertEqual(invoke(extra={'FAIL_GH':'1'}).returncode,0,'no-op must not call gh')
            self.assertEqual(config,(work/'.git/config').read_bytes())
            (work/'contract.json').write_text('new\n')
            failed=invoke(extra={'FAIL_GH':'1'});self.assertNotEqual(failed.returncode,0)
            self.assertEqual(len(git('ls-remote','--heads','origin',cwd=work).splitlines()),1)
            result=invoke();self.assertEqual(result.returncode,0,result.stderr)
            heads=git('ls-remote','--heads','origin',cwd=work)
            fresh=root/'fresh';git('clone','--branch','main',str(remote),str(fresh))
            (fresh/'contract.json').write_text('new\n')
            again=invoke(fresh);self.assertEqual(again.returncode,0,again.stderr)
            self.assertEqual(heads,git('ls-remote','--heads','origin',cwd=work))
            dispatched=invoke(fresh,dispatch=True);self.assertEqual(dispatched.returncode,0,dispatched.stderr)
            self.assertEqual((root/'dispatch.log').read_text().count('dispatch'),1)
            reused=invoke(fresh,dispatch=True);self.assertEqual(reused.returncode,0,reused.stderr)
            self.assertEqual((root/'dispatch.log').read_text().count('dispatch'),1)
            runs=json.loads((root/'runs.json').read_text());runs[0].update(status='completed',conclusion='failure')
            (root/'runs.json').write_text(json.dumps(runs))
            rejected=invoke(fresh,dispatch=True);self.assertNotEqual(rejected.returncode,0)
            self.assertIn('qualification failed',rejected.stderr)
            self.assertEqual((root/'dispatch.log').read_text().count('dispatch'),1)
            # A human edit on the existing bot branch must never be force-replaced.
            (work/'contract.json').write_text('external edit\n')
            git('add','contract.json',cwd=work);git('commit','-m','external edit',cwd=work)
            branch=git('branch','--show-current',cwd=work);git('push','origin','HEAD:refs/heads/'+branch,cwd=work)
            heads=git('ls-remote','--heads','origin',cwd=work)
            refused=invoke(fresh);self.assertNotEqual(refused.returncode,0)
            self.assertIn('refusing to overwrite',refused.stderr)
            self.assertEqual(heads,git('ls-remote','--heads','origin',cwd=work))
            state.write_text(json.dumps([{'number':1,'state':'CLOSED','mergedAt':None}]))
            closed=invoke(fresh);self.assertNotEqual(closed.returncode,0)
            self.assertIn('closed unmerged',closed.stderr)
            self.assertEqual(heads,git('ls-remote','--heads','origin',cwd=work))
