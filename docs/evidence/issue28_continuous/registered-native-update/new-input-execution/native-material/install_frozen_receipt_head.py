from pathlib import Path
import json,subprocess,hashlib
main=Path('/Users/lyuhongwang/Developer/SEC_metrics');runtime=Path('/tmp/sec_metrics_issue28_continuous/native-refresh-execution/current-runtime').resolve();foundation_path='requirements/issue_15_v1/foundation_verification_receipt.json';foundation=json.loads((runtime/foundation_path).read_text());written=[]
def main_git(*args):return subprocess.check_output(['git',*args],cwd=main)
def store(path,raw):
 oid=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=runtime,input=raw).decode().strip()
 subprocess.run(['git','update-index','--add','--cacheinfo','100644',oid,path],cwd=runtime,check=True)
 written.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'blob':oid})
store(foundation_path,(runtime/foundation_path).read_bytes())
for entry in foundation['receipt_bindings']:
 raw=(runtime/entry['path']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=entry['sha256']:
  pointer=json.loads(main_git('show','HEAD:outputs/active_publication.json'));prefix='outputs/publications/'+pointer['publication_id']+'/'
  manifest=json.loads(main_git('show','HEAD:'+prefix+'publication_manifest.json'))
  matches=[r for r in manifest['files']if r['sha256']==entry['sha256']and r['size']==entry['size']and r['path'].endswith('/'+entry['path'])];assert matches
  raw=main_git('show','HEAD:'+prefix+sorted(matches,key=lambda r:r['path'])[0]['path'])
 assert len(raw)==entry['size']and hashlib.sha256(raw).hexdigest()==entry['sha256']
 store(entry['path'],raw)
subprocess.run(['git','-c','user.name=Isolated runtime test','-c','user.email=isolated-runtime@example.invalid','commit','-q','-m','Record exact inherited foundation receipts for isolated native tests'],cwd=runtime,check=True)
report={'files':written,'local_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=runtime).decode().strip(),'scope':'Independent local Git objects; no clone or borrowed object store; original frozen receipt hashes unchanged; runtime worktree files unchanged'}
(runtime.parent/'frozen-receipt-head.json').write_text(json.dumps(report,indent=2)+'\n');print(report['local_head'])
