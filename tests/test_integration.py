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

    def configure_local_release(self, argv, timeout=2):
        self.cli('interrupt', lease=True)
        policy=json.loads(self.policy.read_text())
        policy['release']['argv']=argv
        policy['release_timeout_seconds']=timeout
        self.policy.write_text(json.dumps(policy))
        self.lease=self.cli('start','--new-run','--policy',str(self.policy))[1]['lease']
        self.cli('gate','fixture','--',*self.check,lease=True)
        self.review([],True)
        self.cli('permit','fixture-remote','main',lease=True)

    def release_process(self, actor='main', lease=None):
        return subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),'--state',str(self.state),
                               '--actor',actor,'--lease',lease or self.lease,
                               'release','fixture-remote','main'],capture_output=True,text=True,timeout=10)

    def test_release_rejects_wrong_actor_and_stale_lease_before_execution(self):
        flag=self.root/'release executed'
        self.configure_local_release([sys.executable,'-c',f'from pathlib import Path; Path({str(flag)!r}).touch()'])
        for actor,lease in [('worker',self.lease),('main','stale-lease')]:
            with self.subTest(actor=actor):
                result=self.release_process(actor,lease)
                self.assertEqual(result.returncode,2,result.stdout+result.stderr)
                self.assertFalse(flag.exists())
                self.assertEqual(list(self.state.glob('release-*.log')),[])

    def test_release_timeout_kills_descendants(self):
        flag=self.root/'descendant survived'
        started=self.root/'descendant started'
        child=f"import time; from pathlib import Path; Path({str(started)!r}).touch(); time.sleep(1); Path({str(flag)!r}).touch()"
        parent=f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(5)"
        self.configure_local_release([sys.executable,'-c',parent],timeout=0.5)
        result=self.release_process()
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['exit_code'],124)
        import time
        self.assertTrue(started.exists(),'Release must start the child before the timeout')
        time.sleep(1.2)
        self.assertFalse(flag.exists(),'Timed out release left a running child')

    def test_release_spawn_failure_has_actual_exit_receipt(self):
        self.configure_local_release([str(self.root/'missing-executable')])
        result=self.release_process()
        self.assertEqual(result.returncode,1,result.stderr)
        receipt=json.loads(result.stdout)
        self.assertEqual(receipt['exit_code'],127)
        self.assertIn('No such file',Path(receipt['log']).read_text())
        self.assertEqual(len(list(self.state.glob('release-receipt-*.json'))),1)

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

    def test_inline_card_uses_main_actor_and_independent_review(self):
        task=dict(id='INLINE',role='builder',mode='implementation',inputs=['fixture'],
                  acceptance=['fixture check'],files=['fixture.txt'],resources=[],dependencies=[])
        self.cli('add',str(self.write('inline.json',task)),lease=True)
        result=self.cli('inline','INLINE',lease=True)[1]
        self.assertEqual(result['executor'],'main')
        self.assertTrue(result['inline'])
        self.cli('report','main',result['token'],str(self.write('inline.txt','Inspected fixture source.')))
        self.cli('accept','INLINE',lease=True,expected=2)
        self.review(['INLINE'])
        self.cli('accept','INLINE',lease=True)

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


class LinkedWorktreeHook(unittest.TestCase):
    """A15 through the real hook script: a linked worktree follows the main worktree's run."""

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Orchestra linked ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.env={**os.environ,'XDG_STATE_HOME':str(self.root/'xdg')}
        self.env.pop('ORCHESTRA_STATE_DIR',None)
        self.repo=self.root/'main checkout'
        self.repo.mkdir()
        self.git(self.repo,'init','-q','-b','main')
        self.git(self.repo,'config','user.name','Integration')
        self.git(self.repo,'config','user.email','integration@example.invalid')
        (self.repo/'fixture.txt').write_text('ready\n')
        self.git(self.repo,'add','fixture.txt')
        self.git(self.repo,'commit','-q','-m','Fixture')
        self.linked=self.root/'linked checkout'
        self.git(self.repo,'worktree','add','-q',str(self.linked),'-b','side')

    def git(self,cwd,*args):
        return subprocess.check_output(['git','-C',str(cwd),*args],stderr=subprocess.PIPE).decode().strip()

    def hook(self,cwd,command):
        payload={'cwd':str(cwd),'tool_name':'Bash','tool_input':{'command':command}}
        result=subprocess.run(['/bin/sh',str(HOOK),'PreToolUse','--harness','codex'],input=json.dumps(payload),
                              capture_output=True,text=True,env=self.env,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout).get('hookSpecificOutput',{}).get('permissionDecision')

    def test_push_from_linked_worktree_follows_the_main_checkout_run(self):
        command='git push origin side'
        self.assertIsNone(self.hook(self.linked,command))
        lease=json.loads(subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),'start'],env=self.env,
                                        capture_output=True,text=True,check=True).stdout)['lease']
        self.assertEqual(self.hook(self.linked,command),'deny')
        self.assertEqual(self.hook(self.repo,command),'deny')
        self.assertIsNone(self.hook(self.linked,'git status'))
        subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),'--lease',lease,'interrupt'],env=self.env,
                       capture_output=True,text=True,check=True)
        self.assertIsNone(self.hook(self.linked,command))

    def test_bare_common_directory_stays_unarmed(self):
        # A15: a worktree of a bare repository has no main worktree, so it is never armed,
        # even with a run state sitting at the bare directory's parent.
        bare=self.root/'bare.git'
        subprocess.run(['git','clone','-q','--bare',str(self.repo),str(bare)],check=True,capture_output=True)
        self.git(bare,'worktree','add','-q',str(self.root/'bare checkout'),'main')
        subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),'start'],env=self.env,
                       capture_output=True,text=True,check=True)
        parent_state=subprocess.run([sys.executable,'-c',
                                     'import sys;sys.path.insert(0,sys.argv[1]);'
                                     'from orchestra_core.paths import state_location;from pathlib import Path;'
                                     'print(state_location(Path(sys.argv[2])))',
                                     str(CLI.parent),str(self.root)],env=self.env,capture_output=True,text=True,check=True).stdout.strip()
        Path(parent_state).mkdir(parents=True)
        (Path(parent_state)/'state.json').write_text('{}')
        for command in ['git push origin main','git push origin main && git status']:
            with self.subTest(command=command):
                self.assertIsNone(self.hook(self.root/'bare checkout',command))


if __name__=='__main__':
    unittest.main()
