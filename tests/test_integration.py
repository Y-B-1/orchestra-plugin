"""Exercise a real local repository and release target through the public CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_packaging import PLUGIN

CLI=PLUGIN/'scripts/orchestra.py'
HOOK=PLUGIN/'scripts/run-hook.sh'
CATEGORIES=['requirements','correctness','security','tests','architecture','standards','cleanup']


class WorkflowIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Orchestra integration spaces ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.repo=self.root/'project with spaces'
        self.repo.mkdir()
        self.state=self.root/'outside run state'
        self.git('init','-b','main')
        self.git('config','user.name','Integration')
        self.git('config','user.email','integration@example.invalid')
        (self.repo/'fixture.txt').write_text('ready\n')
        self.git('add','fixture.txt')
        self.git('commit','-m','Fixture')
        self.remote=self.root/'local bare target'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,capture_output=True)
        self.git('remote','add','fixture-remote',str(self.remote))
        self.check=[sys.executable,'-c',"from pathlib import Path; assert Path('fixture.txt').read_text() == 'ready\\n'"]
        policy={'schema_version':1,'required_checks':[{'name':'fixture','argv':self.check}],
                'release':{'enabled':True,'authorization':'Isolated local fixture push only',
                           'remote':'fixture-remote','target':'main','argv':['git','push','fixture-remote','main']}}
        self.policy=self.write('policy.json',policy)
        self.lease=self.cli('start','--policy',str(self.policy))[1]['lease']

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.PIPE).decode().strip()

    def write(self,name,data):
        p=self.root/name
        p.write_text(json.dumps(data) if not isinstance(data,str) else data)
        return p

    def cli(self,*args,lease=False,expected=0):
        cmd=[sys.executable,str(CLI),'--repo',str(self.repo),'--state',str(self.state)]
        if lease:
            cmd+=['--lease',self.lease]
        result=subprocess.run(cmd+list(args),capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,expected,result.stderr+result.stdout)
        return result,json.loads(result.stdout if expected==0 else result.stderr)

    def review(self,ids,final=False,summary='Inspected fixture source and concrete failure checks.'):
        artifact=self.cli('artifact')[1]
        p=self.write('final.json' if final else 'checkpoint.json',
                     dict(reviewer='independent-reviewer',categories=CATEGORIES,tasks=ids,findings=[],
                          verdict='CLEAN',final=final,summary=summary,artifact=artifact))
        self.cli('review',str(p),lease=True)

    def test_local_release_and_repeated_run(self):
        for ident,file in [('B1','one.txt'),('B2','two.txt')]:
            task=dict(id=ident,role='builder',mode='implementation',inputs=['fixture outcome'],acceptance=['fixture check'],
                      files=[file],resources=[],dependencies=[],outcome='fixture outcome')
            self.cli('add',str(self.write(ident+'.json',task)),lease=True)
            token=self.cli('dispatch',ident,'worker-'+ident,lease=True)[1]['assignment']
            self.cli('report','worker-'+ident,token,str(self.write(ident+'.txt','Inspected fixture; no source change needed.')))
        groups=self.cli('review-groups')[1]
        self.assertEqual(groups[0]['tasks'],['B1','B2'])
        self.cli('finish',lease=True,expected=2)
        self.review(['B1','B2'])
        for ident in ['B1','B2']:
            self.cli('accept',ident,lease=True)
        self.cli('gate','fixture','--',*self.check,lease=True)
        self.review(['B1','B2'],True)
        self.cli('permit','fixture-remote','main',lease=True)
        payload=json.dumps({'cwd':str(self.repo),'tool_name':'Bash','tool_input':{'command':'git push fixture-remote main'}})
        result=subprocess.run(['/bin/sh',str(HOOK),'PreToolUse','--harness','codex'],input=payload,capture_output=True,text=True,
                              env={**os.environ,'ORCHESTRA_STATE_DIR':str(self.state)},timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('permissionDecision',result.stdout)
        self.cli('release','fixture-remote','main',lease=True)
        remote_head=subprocess.check_output(['git','--git-dir',str(self.remote),'rev-parse','refs/heads/main']).decode().strip()
        self.assertEqual(remote_head,self.git('rev-parse','HEAD'))
        self.cli('finish',lease=True)
        self.lease=self.cli('start','--new-run')[1]['lease']
        self.assertEqual(self.cli('status')[1]['tasks'],{})
        self.assertEqual(len(list((self.state/'history').glob('*.json'))),1)
        self.assertEqual(self.git('status','--porcelain'),'')

    def test_dirty_candidate_invalidates_review_and_permit(self):
        task=dict(id='I',role='investigator',mode='code',inputs=['fixture'],acceptance=['inspect'],files=[],resources=[],dependencies=[])
        self.cli('add',str(self.write('I.json',task)),lease=True)
        token=self.cli('dispatch','I','reader',lease=True)[1]['assignment']
        self.cli('report','reader',token,str(self.write('result.txt','Read fixture.txt: ready')))
        self.cli('accept','I',lease=True)
        self.cli('gate','fixture','--',*self.check,lease=True)
        self.review(['I'],True)
        (self.repo/'fixture.txt').write_text('changed\n')
        self.cli('permit','fixture-remote','main',lease=True,expected=2)
        self.cli('finish',lease=True,expected=2)


if __name__=='__main__':
    unittest.main()
