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
        artifact=self.cli('artifact')[1] if final or not ids else self.cli('artifact','--tasks',','.join(ids))[1]
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
        self.assertNotIn('lease',json.dumps(self.cli('status')[1]))
        for removed in ('route','audit-policy','review-groups'):
            result=subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),'--state',str(self.state),removed],
                                  capture_output=True,text=True,timeout=25)
            self.assertNotEqual(result.returncode,0,removed)
        self.cli('finish',lease=True,expected=2)
        self.review(['B1','B2'])
        for ident in ['B1','B2']:
            self.cli('accept',ident,lease=True)
        self.cli('gate','fixture','--',*self.check,lease=True)
        self.review(['B1','B2'],True)
        self.cli('permit','fixture-remote','main',lease=True)
        payload=json.dumps({'cwd':str(self.repo),'tool_name':'Bash','tool_input':{'command':'git push fixture-remote main'}})
        result=subprocess.run(['/bin/sh',str(HOOK),'PreToolUse','--harness','claude'],input=payload,capture_output=True,text=True,
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

    def test_artifact_tasks_output_is_accepted_by_review(self):
        task=dict(id='T',role='builder',mode='implementation',inputs=['fixture'],
                  acceptance=['fixture check'],files=['fixture.txt'],resources=[],dependencies=[])
        self.cli('add',str(self.write('T.json',task)),lease=True)
        token=self.cli('dispatch','T','worker',lease=True)[1]['assignment']
        self.cli('report','worker',token,str(self.write('t.txt','Inspected fixture source.')))
        artifact=self.cli('artifact','--tasks','T')[1]
        self.assertEqual(['fixture.txt'],artifact['scope'])
        self.assertNotIn('scope',self.cli('artifact')[1])
        (self.repo/'sibling.txt').write_text('sibling uncommitted edit\n')
        p=self.write('scoped.json',dict(reviewer='independent-reviewer',categories=['correctness'],tasks=['T'],
                     findings=[],verdict='CLEAN',final=False,summary='Inspected fixture source.',artifact=artifact))
        self.cli('review',str(p),lease=True)
        self.cli('accept','T',lease=True)
        self.cli('artifact','--tasks','NOPE',expected=2)

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
        result=subprocess.run(['/bin/sh',str(HOOK),'PreToolUse','--harness','claude'],input=json.dumps(payload),
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


class HarnessSessionIntegration(unittest.TestCase):
    """B-F5 through the real CLI and run-hook.sh."""

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Orchestra harness session ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.repo=self.root/'repo'
        self.repo.mkdir()
        self.state=self.root/'state'
        for args in (['init','-b','main'],['config','user.name','T'],['config','user.email','t@example.invalid']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        (self.repo/'f').write_text('x')
        subprocess.run(['git','-C',str(self.repo),'add','f'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','f'],check=True,capture_output=True)
        self.env=dict(os.environ,ORCHESTRA_STATE_DIR=str(self.state))

    def cli(self,*args,expected=0):
        result=subprocess.run([sys.executable,str(CLI),'--repo',str(self.repo),*args],env=self.env,
                              capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,expected,result.stderr+result.stdout)
        return json.loads(result.stdout) if expected==0 else result.stderr

    def hook(self,event,**payload):
        payload.setdefault('cwd',str(self.repo))
        result=subprocess.run(['/bin/sh',str(HOOK),event,'--harness','claude'],input=json.dumps(payload),env=self.env,
                              capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def session(self):
        return self.cli('status')['session']

    def test_session_end_releases_so_a_new_run_starts(self):
        self.cli('start','--harness-session','S')
        self.assertEqual(self.session()['harness_session'],'S')
        self.cli('start',expected=2)  # still armed
        self.hook('SessionEnd',session_id='S',reason='prompt_input_exit')
        self.assertFalse(self.session()['active'])
        self.cli('start','--new-run')

    def foreign_policy(self):
        """A plugin upgrade or policy edit: the stored policy hash no longer matches."""
        path=self.state/'state.json'
        data=json.loads(path.read_text())
        data['policy']='0'*64
        path.write_text(json.dumps(data))

    def test_new_run_archives_an_ended_run_under_a_changed_policy(self):
        lease=self.cli('start')['lease']
        self.cli('--lease',lease,'interrupt')
        self.foreign_policy()
        self.assertIn('start --new-run',self.cli('status',expected=2))
        self.assertIn('start --new-run',self.cli('start',expected=2))
        push=self.hook('PreToolUse',tool_name='Bash',tool_input={'command':'git push origin main'})
        self.assertEqual(push,{})  # O35: an ended run is unarmed
        self.cli('start','--new-run')
        self.assertEqual(len(list((self.state/'history').glob('run-*.json'))),1)
        self.assertTrue(self.session()['active'])

    def test_changed_policy_message_depends_on_whether_the_run_is_active(self):
        lease=self.cli('start')['lease']
        self.foreign_policy()
        active=self.cli('status',expected=2)
        self.assertNotIn('start --new-run',active)
        self.assertIn('state.json',active)
        self.assertIn('version that started',active)
        self.cli('start','--new-run',expected=2)
        path=self.state/'state.json'
        data=json.loads(path.read_text())
        data['session']['active']=False
        path.write_text(json.dumps(data))
        self.assertIn('start --new-run',self.cli('status',expected=2))

    def test_new_run_refuses_an_active_run_under_a_changed_policy(self):
        self.cli('start')
        self.foreign_policy()
        refused=self.cli('start','--new-run',expected=2)  # FX6: the engine's recovery steps, not interrupt/finish
        self.assertIn('version that started',refused)
        self.assertIn('state.json',refused)
        self.assertNotIn('Stop or finish',refused)
        self.assertFalse((self.state/'history').exists())
        push=self.hook('PreToolUse',tool_name='Bash',tool_input={'command':'git push origin main'})
        self.assertEqual(push['hookSpecificOutput']['permissionDecision'],'deny')

    def test_new_run_refuses_an_active_run_under_the_current_policy(self):
        self.cli('start')
        self.assertIn('Stop or finish the active run',self.cli('start','--new-run',expected=2))
        self.assertFalse((self.state/'history').exists())

    def test_clear_and_resume_rebind_then_exit_releases(self):
        for reason in ('clear','resume'):
            with self.subTest(reason=reason):
                self.cli('start','--new-run','--harness-session','S')
                self.hook('SessionEnd',session_id='S',reason=reason)
                self.assertTrue(self.session()['active'])
                out=self.hook('SessionStart',session_id='S2',source=reason)
                self.assertIn('--harness-session S2',out['hookSpecificOutput']['additionalContext'])
                self.assertEqual(self.session()['harness_session'],'S2')
                self.hook('SessionEnd',session_id='S',reason='prompt_input_exit')
                self.assertTrue(self.session()['active'])  # the old id no longer owns the run
                self.hook('SessionEnd',session_id='S2',reason='prompt_input_exit')
                self.assertFalse(self.session()['active'])
                lease=self.cli('start','--new-run')['lease']
                self.cli('--lease',lease,'interrupt')

    def test_unbound_run_ignores_session_end_and_where_hides_the_lease(self):
        self.cli('start')
        self.hook('SessionEnd',session_id='S',reason='prompt_input_exit')
        self.assertTrue(self.session()['active'])
        where=self.cli('where')
        self.assertEqual(set(where),{'repo','state','standing_orders'})
        self.assertEqual((where['repo'],where['state'],where['standing_orders']),(str(self.repo),str(self.state),False))
        (self.state/'standing-orders.md').write_text('rules\n')
        self.assertTrue(self.cli('where')['standing_orders'])


class AutonomyIntegration(unittest.TestCase):
    """SPEC 12 through the real CLI and run-hook.sh."""

    def ledger(self,passes='1'):
        from datetime import datetime,timedelta,timezone
        sys.path.insert(0,str(PLUGIN/'scripts'))
        from orchestra_core.engine import AUTONOMY_FIXED
        when=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(timespec='seconds')
        text=['goal: integration','max_passes: '+passes,'max_stalls: 2','deadline: '+when,'','## Completion checks','',
              'never: '+sys.executable+' -c "import sys; sys.exit(1)"','','## Approval boundaries','',*AUTONOMY_FIXED]
        (self.state/'autonomy.md').write_text('\n'.join(text)+'\n')

    def card(self,name):
        task=self.root/(name+'.json')
        task.write_text(json.dumps(dict(id=name,role='builder',mode='implementation',inputs=['s'],acceptance=['a'],
                                        files=[name],resources=[],dependencies=[])))
        self.cli('--lease',self.lease,'add',str(task))

    cli=HarnessSessionIntegration.cli
    hook=HarnessSessionIntegration.hook

    def setUp(self):
        HarnessSessionIntegration.setUp(self)
        self.lease=self.cli('start')['lease']

    def test_arm_needs_no_lease_writes_the_template_then_arms_and_reports_preconditions(self):
        message=self.cli('autonomy','arm',expected=2)
        self.assertIn('fill the ledger, then arm again',message)
        self.assertTrue((self.state/'autonomy.md').is_file())
        self.ledger()
        armed=self.cli('autonomy','arm')
        self.assertTrue(armed['active'])
        self.assertIn('permission_mode',armed['preconditions'])
        self.assertTrue(self.cli('autonomy','status')['active'])
        self.assertTrue(self.cli('autonomy','disarm')['was_active'])
        self.assertFalse(self.cli('autonomy','status')['active'])

    def test_park_and_unpark_take_the_lease_and_a_reason(self):
        self.card('c1')
        self.cli('park','c1','--reason','x',expected=2)  # no lease
        self.cli('--lease',self.lease,'park','c1',expected=2)  # --reason is required
        self.cli('--lease',self.lease,'park','c1','--reason','needs a push')
        self.assertEqual(self.cli('status')['tasks']['c1']['state'],'parked')
        self.cli('--lease',self.lease,'unpark','c1')
        self.assertEqual(self.cli('status')['tasks']['c1']['state'],'queued')

    def test_stop_continues_then_caps_then_session_start_shows_the_report(self):
        self.card('c1')
        self.ledger('1')
        self.cli('autonomy','arm')
        first=self.hook('Stop')
        self.assertEqual(first['decision'],'block')
        self.assertEqual(self.hook('Stop'),{})
        self.assertEqual(self.cli('autonomy','status')['last_stop_reason'],'cap-passes')
        context=self.hook('SessionStart',session_id='S3',source='startup')['hookSpecificOutput']['additionalContext']
        self.assertIn('cap-passes',context)
        self.assertIn('progress.md',context)

    def test_hook_denies_boundary_only_while_active(self):
        self.card('c1')
        self.ledger()
        self.cli('autonomy','arm')
        out=self.hook('PreToolUse',tool_name='Bash',tool_input={'command':'rm -rf build'})
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'],'deny')
        self.cli('autonomy','disarm')
        self.assertEqual(self.hook('PreToolUse',tool_name='Bash',tool_input={'command':'rm -rf build'}),{})


if __name__=='__main__':
    unittest.main()
