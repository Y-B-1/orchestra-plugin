import unittest
from test_packaging import PLUGIN
from orchestra_core.routing import route, review_groups, audit_axes


class RoutingTests(unittest.TestCase):
    def facts(self,**extra):
        return dict(kind='change',settled=True,unknown_api=False,product_decision=False,
                    files=1,independent_units=1,risks=[],**extra)

    def test_cases(self):
        baseline=self.facts()
        for changes,lane in [({},'direct'),({'risks':['permission']},'plan'),
                             ({'independent_units':3},'plan'),({'settled':False},'design'),
                             ({'unknown_api':True},'investigate'),({'kind':'question'},'answer'),
                             ({'kind':'bug','files':1},'bug'),({'kind':'full-test'},'full-test')]:
            self.assertEqual(route({**baseline,**changes})['lane'],lane)

    def test_unknown_facts_reject(self):
        for changes in [{'risks':['made-up']},{'files':True},{'settled':'yes'},{'kind':'feature'}]:
            with self.assertRaises(ValueError):
                route({**self.facts(),**changes})

    def test_execution_choice_preserves_lane_and_exposes_both_options(self):
        for execution in ['inline', 'worker']:
            result = route({**self.facts(), 'execution': execution})
            self.assertEqual(result['lane'], 'direct')
            self.assertEqual(result['execution'], execution)
            self.assertEqual(result['execution_options'], ['inline', 'worker'])
        self.assertEqual(route(self.facts())['execution'], 'decide')
        with self.assertRaises(ValueError):
            route({**self.facts(), 'execution': 'automatic'})

    def test_microtickets_share_review_and_foundation_is_early(self):
        task=dict(role='builder',state='reported',mode='implementation',inputs=['spec'],dependencies=[],outcome='settings')
        cards=[dict(task,id='B1'),dict(task,id='B2'),dict(task,id='B3',mode='sensitive'),dict(task,id='B4',dependencies=['B3'])]
        groups=review_groups(cards)
        self.assertEqual(groups[0]['tasks'],['B1','B2','B4'])
        self.assertEqual(groups[1]['tasks'],['B3'])
        self.assertEqual(groups[1]['timing'],'before dependent dispatch')

    def test_audits_follow_axes_not_wave_count(self):
        facts=dict(has_spec=True,substantial=False,binding_standards=False,ledger_claims=False)
        self.assertEqual(audit_axes(facts)['axes'],[])
        result=audit_axes({**facts,'substantial':True,'ledger_claims':True})
        self.assertEqual(result['axes'],['ledger','spec'])
        self.assertEqual(result['instances'],2)


if __name__=='__main__':
    unittest.main()
