import os,runpy,sys
from pathlib import Path
runtime=Path(sys.argv[1]).resolve()
denied=[Path(p).resolve() for p in os.environ.get('COMPANY_DENY_READ_ROOTS','').split(':') if p]
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve()
  if any(p==d or d in p.parents for d in denied): raise PermissionError('ISOLATION_DENIED:'+str(p))
sys.addaudithook(audit)
sys.dont_write_bytecode=True
sys.argv=[str(runtime/'tools/vnext_company.py'),*sys.argv[2:]]
runpy.run_path(str(runtime/'tools/vnext_company.py'),run_name='__main__')
