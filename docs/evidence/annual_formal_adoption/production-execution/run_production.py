"""Observation wrapper for the approved CLI; no validator or authority substitutes."""
import os,sys,json,socket,subprocess,runpy,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics'); O=Path(__file__).resolve().parent
sys.path[:0]=[str(R),str(R/'scripts')]
for k in list(os.environ):
 if k.endswith('_API_KEY'):os.environ.pop(k)
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['GIT_OPTIONAL_LOCKS']='0'
from vnext import annual_candidate
from vnext.annual_adoption import git
from vnext.canonical import content_hash
mode=sys.argv[1]; label=sys.argv[2] if len(sys.argv)>2 else mode
plan=O.parent.parent/'attempt-02/pending-production-plan.json'
output=O/(label+'.json'); evidence=O/(label+'-execution.json')
assert not output.exists() and not evidence.exists(), 'Select new evidence names; do not overwrite'
def now():return datetime.now(timezone.utc).isoformat()
def proof(p):
 b=p.read_bytes();return {'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
head=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip()
assert branch=='main','Production actions only from main'
code={'head':head,'branch':branch,'implementation_tree':content_hash(value=git('ls-tree','-r',head,'scripts','tools','config','catalog','requirements').decode()),'test_tree':content_hash(value=git('ls-tree','-r',head,'tests').decode())}
reads=[]; original=annual_candidate._github
allowed_comments=[]
if (O/'approvals.json').exists():
 approvals=json.loads((O/'approvals.json').read_text());allowed_comments=[str(approvals[n]['id']) for n in ['requirement_transition','publication_decision']]
def tracked(path):
 assert mode!='read', 'Network forbidden during read'
 assert path=='repos/wlvh/SEC_metrics/pulls/40' or path in ['repos/wlvh/SEC_metrics/issues/comments/'+x for x in allowed_comments]
 value=original(path);reads.append({'path':path,'observed_at_utc':now(),'response':value});return value
annual_candidate._github=tracked
# All business sockets are forbidden. Real GitHub reads still use the original gh boundary.
def deny(*a,**kw):raise RuntimeError('BUSINESS_NETWORK_FORBIDDEN_BY_EXECUTION_WRAPPER')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
original_run=subprocess.run
def run(args,*a,**kw):
 assert isinstance(args,(list,tuple)) and args, 'Explicit subprocess argv required'
 exe=Path(str(args[0])).name
 assert exe=='git' or (exe=='gh' and list(args[:4])==['gh','api','--hostname','github.com']), 'Unexpected child process'
 return original_run(args,*a,**kw)
subprocess.run=run
cli=['tools/vnext_annual_publication.py']
if mode=='read':cli+=['read','--publication-root',str(R)]
else:
 cli+=['activate' if mode=='activate' else 'release','--plan',str(plan),'--activation-url',approvals['requirement_transition']['html_url']]
 if mode!='activate':cli+=['--owner-url',approvals['publication_decision']['html_url'],'--operation',mode]
cli+=['--output-json',str(output)]
started=now();exit_code=1
try:
 sys.argv=cli
 try:runpy.run_path(str(R/cli[0]),run_name='__main__');exit_code=0
 except SystemExit as e:exit_code=int(e.code or 0)
except BaseException:traceback.print_exc()
finally:
 record={'mode':mode,'command':['python3',*cli],'cwd':str(R),'implementation':code,'started_at_utc':started,'finished_at_utc':now(),'exit_status':exit_code,'github_reads':reads,'python_business_sockets_forbidden':True,'new_provider_paid_sec_calls':[0,0,0],'pr38_historical_calls':[2,2,0],'plan_file':proof(plan),'harness_file':proof(Path(__file__)),'output_file':proof(output) if output.exists() else None}
 evidence.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(exit_code)
