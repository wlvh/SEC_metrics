"""Current workflow selector/setup/gate controls; no financial or network execution."""
import collections,copy,itertools,json,os,re,shlex,subprocess
from pathlib import Path
BASE='672b46b6d99d0f98bd0dd458d1b9767adc664636'
PATH='.github/workflows/company-current-records.yml'

def parse(raw):
    return json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load(STDIN.read))'],input=raw,text=True))

old=parse(subprocess.check_output(['git','show',BASE+':'+PATH],text=True))
new=parse(Path(PATH).read_text())
assert {k:v for k,v in new.items() if k!='jobs'}=={k:v for k,v in old.items() if k!='jobs'}
previous=old['jobs']['company-current'];workers=[k for k in new['jobs'] if k!='company-current']
assert workers==['company-records','company-source','company-financial','company-history','source-contracts']
setup=previous['steps'][:2]
for k in workers:
    x=new['jobs'][k]
    assert x['runs-on']==previous['runs-on'] and x['timeout-minutes']==5
    assert x['steps'][:2]==setup
    assert all('if' not in step for step in x['steps'][2:])

def selectors(step):
    args=shlex.split(step['run'])
    if args[:3]==['python3','-m','unittest']:return args[3:-1] if args[-1]=='-v' else args[3:]
    assert args[:2]==['python3','tests/required_unittests.py'],args
    return args[2:]

old_steps=previous['steps'][2:]
new_steps=[s for k in workers for s in new['jobs'][k]['steps'][2:]]
old_count=collections.Counter(x for s in old_steps for x in selectors(s))
new_count=collections.Counter(x for s in new_steps for x in selectors(s))
assert old_count==new_count,(old_count-new_count,new_count-old_count)
assert collections.Counter(x for k in workers[:3] for x in selectors(new['jobs'][k]['steps'][2]))==collections.Counter(selectors(old_steps[0]))
for step in old_steps[1:]:
    matching=[s for s in new_steps if s['name']==step['name']]
    assert len(matching)==1 and matching[0]==step,step['name']
assert all(new['jobs'][k]['steps'][2].get('env')==old_steps[0].get('env') for k in workers[:3])
gate=new['jobs']['company-current'];assert gate['needs']==workers and gate['if']=='${{ always() }}' and gate['timeout-minutes']==1
assert len(gate['steps'])==1
step=gate['steps'][0];assert set(step['env'])=={k.upper().replace('-','_')+'_RESULT' for k in workers}
for k in workers:assert step['env'][k.upper().replace('-','_')+'_RESULT']=='${{ needs.'+k+'.result }}'
passed=0
for outcome in itertools.product(('success','failure','cancelled','skipped'),repeat=len(workers)):
    env=dict(os.environ);env.update(zip(step['env'],outcome))
    code=subprocess.run(['/bin/sh','-c',step['run']],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
    assert (code==0)==all(x=='success' for x in outcome),(outcome,code)
    passed+=1
# A no-work/unknown result cannot be accepted either.
for value in ('','unknown','neutral'):
    env=dict(os.environ);env.update({k:'success' for k in step['env']});env[next(iter(step['env']))]=value
    assert subprocess.run(['/bin/sh','-c',step['run']],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
assert not any('$HOME' in s.get('run','') or 'sudo' in s.get('run','') for s in new_steps)
print(json.dumps({'baseline':BASE,'workers':workers,'main_original_large_step_selectors':len(selectors(old_steps[0])),
    'exact_selector_multiset_preserved':True,'selector_executions':sum(new_count.values()),'unique_selectors':len(new_count),
    'unchanged_complete_steps':len(old_steps)-1,'unchanged_setup_permissions_triggers':True,
    'gate_outcome_combinations':passed,'unknown_outcome_controls':3,'required_check_name':'company-current',
    'worker_timeout_minutes':5,'full_material_tests_rerun':False,'new_business_calls':[0,0,0]},indent=2))
