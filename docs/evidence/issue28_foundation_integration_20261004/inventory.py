"""Fixed dependency inventory, never semantic approval or activation."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
BASE='0bc24734736bb1e6cb34fbcf7ab9fece6951764e';MAIN='af1984ad5f1a3598ded3626fe999d3abeffd29b9';PEER='83db2c0284d76cfe6a1fafc8703743add05738f8'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def tree(ref):
 rows={}
 for line in git('ls-tree','-r',ref).decode().splitlines():
  info,path=line.split('\t');mode,kind,oid=info.split();rows[path]={'mode':mode,'oid':oid}
 return rows

t=tree(BASE);main=tree(MAIN);peer=tree(PEER);seen=set();queue=[];reasons={}
def add(path,why):
 if path not in t:return
 reasons.setdefault(path,set()).add(why)
 if path not in seen:seen.add(path);queue.append(path)
# Exact snapshots and their nested historical authority are inseparable.
for path in t:
 if path.startswith('requirements/') or path.startswith('docs/evidence/issue28_continuous/frozen-parent-v10'):
  add(path,'snapshot_chain_and_frozen_parent')
for req in ['issue_28_v13','issue_28_v14']:
 b=json.loads(git('show',BASE+':requirements/'+req+'/baseline_manifest.json'))
 for field in [b.get('execution_authority',{}).get('files',{}),b.get('new_rule_files',{})]:
  for path in field:add(path,'exact_'+req+'_authority')
for path in ['scripts/vnext/annual_runtime.py','scripts/vnext/annual_continuity_sources.py','scripts/vnext/continuous_sec_acquisition.py','scripts/vnext/continuous_call_ledger.py','scripts/vnext/normal_source_requirements.py','scripts/vnext/normal_annual_input_v2.py','scripts/vnext/normal_run_v3.py','scripts/vnext/ordinary_update_cycle.py','scripts/vnext/c04_update_cycle.py','scripts/vnext/capacity_update_cycle.py','tools/vnext_normal_candidate.py','tools/vnext_normal_update.py','tools/vnext_continuous_sec.py']:
 add(path,'requested_current_year_interface')
# Existing runtime installers intentionally inventory all catalog/config rules.
for path in t:
 if path.startswith(('catalog/','config/')):add(path,'runtime_rule_inventory')
foundation=json.loads(git('show',BASE+':requirements/issue_15_v1/foundation_verification_receipt.json'))
for row in foundation['receipt_bindings']:add(row['path'],'frozen_foundation_receipt')
# Follow Python imports including lazy function imports; do not copy peer code.
while queue:
 path=queue.pop(0)
 if not path.endswith('.py'):continue
 raw=git('show',BASE+':'+path)
 try:module=ast.parse(raw)
 except SyntaxError:continue
 package=path.rsplit('/',1)[0]
 for node in ast.walk(module):
  if isinstance(node,ast.ImportFrom):
   if node.level:
    prefix=package.split('/')
    prefix=prefix[:len(prefix)-node.level+1]
    parts=prefix+(node.module.split('.') if node.module else [])
   else:parts=(node.module or '').split('.')
   choices=['/'.join(parts)+'.py','/'.join(parts)+'/__init__.py']
   for alias in node.names:choices.append('/'.join(parts+[alias.name])+'.py')
   if not node.level:
    choices+=['scripts/'+p for p in choices]+['tools/'+p for p in choices]
   for p in choices:add(p,'python_import:'+path)
  elif isinstance(node,ast.Import):
   for alias in node.names:
    for prefix in ['', 'scripts/', 'tools/']:add(prefix+alias.name.replace('.','/')+'.py','python_import:'+path)
  elif isinstance(node,ast.Constant) and isinstance(node.value,str):
   v=node.value
   if v in t:add(v,'literal_path:'+path)
# Frozen receipts may live in immutable old publication packages, not mirrors.
extra=[]
for row in foundation['receipt_bindings']:
 path=row['path'];raw=git('show',BASE+':'+path)
 if hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['size']:continue
 pointer=json.loads(git('show',BASE+':outputs/active_publication.json'));prefix='outputs/publications/'+pointer['publication_id']+'/'
 manifest=json.loads(git('show',BASE+':'+prefix+'publication_manifest.json'))
 matches=[x for x in manifest['files'] if x['sha256']==row['sha256'] and x['size']==row['size'] and x['path'].endswith('/'+path)]
 assert matches,path
 loc=prefix+sorted(matches,key=lambda x:x['path'])[0]['path'];extra.append({'receipt_path':path,'fixed_locator':loc,'sha256':row['sha256'],'size':row['size']});add(loc,'frozen_foundation_original_locator');add('outputs/active_publication.json','fixed_foundation_locator_pointer');add(prefix+'publication_manifest.json','fixed_foundation_locator_manifest')
rows=[{'path':p,'source_blob':t[p]['oid'],'main_blob':main.get(p,{}).get('oid'),'peer_blob':peer.get(p,{}).get('oid'),'status':'SAME' if main.get(p,{}).get('oid')==t[p]['oid'] else ('MISSING' if p not in main else 'DIFFERENT'),'reasons':sorted(reasons[p])} for p in sorted(seen)]
result={'main_sha':MAIN,'foundation_sha':BASE,'pr55_sha':PEER,'all_selected_paths':len(rows),'changed_paths':sum(r['status']!='SAME' for r in rows),'changed_python':sum(r['status']!='SAME' and r['path'].endswith('.py') for r in rows),'main_changed_existing':[r['path'] for r in rows if r['status']=='DIFFERENT'],'foundation_receipt_locators':extra,'scope':'static exact snapshot/import/rule closure, runtime verification still required','rows':rows}
(HERE/'foundation-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['rows','foundation_receipt_locators']}))
