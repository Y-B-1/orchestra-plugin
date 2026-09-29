"""Deterministic lane rubric; the coordinator supplies facts and uncertainty."""
import json
from pathlib import Path

FLOW_PATH = Path(__file__).resolve().parents[2] / 'config/flow.json'


def route(facts):
    if not isinstance(facts,dict):
        raise ValueError('Routing needs a facts object')
    flow=json.loads(FLOW_PATH.read_text())
    kind=facts.get('kind')
    if kind not in ['question','change','bug','review','full-test']:
        raise ValueError('Unknown request kind')
    for key in ['settled','unknown_api','product_decision']:
        if not isinstance(facts.get(key),bool):
            raise ValueError('Routing needs explicit boolean '+key)
    for key in ['files','independent_units']:
        if not isinstance(facts.get(key),int) or isinstance(facts[key],bool) or facts[key]<0:
            raise ValueError('Routing needs nonnegative '+key)
    risks=facts.get('risks')
    if not isinstance(risks,list) or any(r not in flow['consequential_risks'] for r in risks):
        raise ValueError('Unknown risk; inspect the request before routing')
    if kind in ['review','full-test']:
        lane=kind
        reason='The user named the operation.'
    elif kind=='bug':
        lane='bug'
        reason='A defect needs diagnosis and failing evidence before repair.'
    elif facts['unknown_api']:
        lane='investigate'
        reason='A factual premise remains unknown.'
    elif facts['product_decision'] or not facts['settled']:
        lane='design'
        reason='The intended behavior needs a decision.'
    elif kind=='question':
        lane='answer'
        reason='The question is self-contained.'
    elif risks or facts['files']>3 or facts['independent_units']>1:
        lane='plan'
        reason='Consequences or coordination need explicit tasks and independent challenge.'
    else:
        lane='direct'
        reason='The change is settled and bounded.'
    options = ['worker'] if lane == 'review' else ['inline'] if lane == 'answer' else ['inline', 'worker']
    execution = facts.get('execution', 'decide')
    if execution != 'decide' and execution not in options:
        raise ValueError('Choose an allowed inline or worker executor')
    return {'lane':lane,'reason':reason,'stages':flow['lanes'][lane],
            'execution':execution,'execution_options':options,
            'facts':facts,'boundary':'Facts need source evidence; this rubric does not understand an arbitrary prompt.'}


def review_groups(tasks):
    """Group reported implementation cards by outcome; isolate consequential foundations."""
    groups={}
    for task in tasks:
        if task['role']!='builder' or task['state']!='reported':
            continue
        dependent=any(task['id'] in other['dependencies'] for other in tasks)
        risky=bool(task.get('risks')) or task['mode']=='sensitive'
        if task.get('foundational') or (dependent and risky):
            key='foundation:'+task['id']
        else:
            key='outcome:'+str(task.get('review_group') or task.get('outcome') or '|'.join(task['inputs']))
        groups.setdefault(key,[]).append(task['id'])
    return [{'group':name,'tasks':ids,'timing':'before dependent dispatch' if name.startswith('foundation:')
             else 'when this outcome is ready for integration'} for name,ids in groups.items()]


def audit_axes(facts):
    """One independent pass per needed axis, on the frozen integration candidate."""
    if not isinstance(facts,dict):
        raise ValueError('Audit selection needs facts')
    for key in ['has_spec','substantial','binding_standards','ledger_claims']:
        if not isinstance(facts.get(key),bool):
            raise ValueError('Audit selection needs explicit '+key)
    explicit=facts.get('explicit_axes',[])
    if not isinstance(explicit,list) or any(x not in ['spec','standards','ledger'] for x in explicit):
        raise ValueError('Unknown audit axis')
    axes=set(explicit)
    if facts['has_spec'] and facts['substantial']:
        axes.add('spec')
    if facts['binding_standards'] and facts['substantial']:
        axes.add('standards')
    if facts['ledger_claims']:
        axes.add('ledger')
    return {'axes':sorted(axes),'timing':'frozen integration candidate, before release',
            'instances':len(axes),'reason':'Separate passes prevent one conformance axis from masking another.'}
