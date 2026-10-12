import json,subprocess
from pathlib import Path
root=Path.cwd();path='.github/workflows/company-current-records.yml'
def parsed(raw):
 r=subprocess.run(['ruby','-ryaml','-rjson','-e','puts YAML.safe_load(STDIN.read, aliases: true).to_json'],input=raw,capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 return json.loads(r.stdout)
base=parsed(subprocess.check_output(['git','show','c6f5c90f:'+path],text=True));actual=parsed((root/path).read_text())
assert set(base['jobs'])==set(actual['jobs'])
for name in base['jobs']:
 if name!='company-records':assert actual['jobs'][name]==base['jobs'][name],name
job=actual['jobs']['company-records'];original=base['jobs']['company-records'];assert job['steps'][:-1]==original['steps']
assert {k:v for k,v in job.items() if k!='steps'}=={k:v for k,v in original.items() if k!='steps'}
extra=job['steps'][-1];assert extra['run']=='python3 tests/required_unittests.py tests.vnext.test_request_binding_batch'
old=base['on']['pull_request']['paths'];new=actual['on']['pull_request']['paths'];assert set(new)-set(old)=={'tests/vnext/test_request_binding_batch.py'}
assert set(old)<=set(new)
assert actual['permissions']==base['permissions']
assert actual['jobs']['company-current']==base['jobs']['company-current']
record={'base':'c6f5c90fe1fa49762608f5605bd54e0b9c7590d5','main_jobs_and_commands_preserved':True,'new_required_step':extra,'new_trigger':'tests/vnext/test_request_binding_batch.py','required_gate_unchanged':True,'no_timeouts_changed':True,'no_removed_paths':True}
Path('docs/evidence/issue28_source_proof_batch_20261010/main-c6f-receiving/workflow.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
