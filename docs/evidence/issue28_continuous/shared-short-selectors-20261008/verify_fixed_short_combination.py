"""One bounded fixed-source unittest execution, not a persistent test framework."""
import hashlib,json,subprocess,sys,tempfile,types,unittest,socket
from pathlib import Path
from unittest.mock import patch
repo=Path('/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics')
objects=Path('/Users/lyuhongwang/Developer/SEC_metrics');tree='621ce1b50051ab5559e3579422fb578209fe143e'
sys.path[:0]=[str(repo/'scripts'),str(repo/'tools')]
def raw(path):return subprocess.check_output(['git','show',tree+':'+path],cwd=objects)
def module(name,path,file):
 m=types.ModuleType(name);m.__package__=name.rpartition('.')[0];m.__file__=str(file);sys.modules[name]=m
 exec(compile(raw(path),'git:'+tree+':'+path,'exec'),m.__dict__);return m
with tempfile.TemporaryDirectory(prefix='issue28-h1h2-small-') as folder:
 root=Path(folder)
 for path in ['tests/fixtures/d02_saved_quote_failures.json','tests/fixtures/jpm_bank_scope_fragments.json','catalog/zero_ai_public_projection.json','config/company_registry.csv','catalog/metrics/B01_revenue.md']:
  p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw(path))
 import vnext
 review=module('vnext.legal_review_contract','scripts/vnext/legal_review_contract.py',repo/'scripts/vnext/legal_review_contract.py');vnext.legal_review_contract=review
 h1=module('_issue28_fixed_h1','tests/vnext/test_legal_review_contract.py',root/'tests/vnext/test_legal_review_contract.py')
 h2=module('_issue28_fixed_h2','tests/vnext/test_history_business_boundaries.py',root/'tests/vnext/test_history_business_boundaries.py')
 # Every other project dependency actually imported by these two modules must
 # be exact fixed combined source, not a different working branch assumption.
 checked=[]
 for name,m in list(sys.modules.items()):
  file=getattr(m,'__file__',None)
  if not file or m is review:continue
  p=Path(file).resolve()
  if not p.is_relative_to(repo):continue
  path=str(p.relative_to(repo))
  if path.startswith(('scripts/','tools/')):
   assert p.read_bytes()==raw(path),path;checked.append(path)
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(h1),unittest.defaultTestLoader.loadTestsFromModule(h2)])
 with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
  result=unittest.TextTestRunner(verbosity=2).run(suite)
 summary={'fixed_merged_tree':tree,'source58':'372f4b74','source62':'09563892','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'fixture_source':'exact combined-tree five fixed files in temporary readonly input layout','project_imports_byte_checked':len(set(checked)),'actual_combined_execution':True,'new_calls':[0,0,0]}
 print(json.dumps(summary,indent=2));sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
