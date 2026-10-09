import os,runpy,socket,sys
from pathlib import Path
from unittest.mock import patch
root=Path(os.environ['COMPANY_TEST_RUNTIME']).resolve()
forbidden=[Path('/Users/lyuhongwang/Developer/SEC_metrics'),Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13'),Path('/private/tmp/issue28-company-consumer-20261003/provider-code')]
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,Path)):
  path=Path(os.fsdecode(args[0])).absolute()
  if any(path==p or p in path.parents for p in forbidden):raise ValueError('COMPANY_TEST_ORIGINAL_PREPARATION_READ_FORBIDDEN:'+str(path))
  mode=args[1];flags=args[2] if len(args)>2 else 0
  writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if writing and (path==root or root in path.parents):raise ValueError('COMPANY_TEST_CODE_WRITE_FORBIDDEN:'+str(path))
sys.addaudithook(audit)
with patch.object(socket.socket,'connect',side_effect=ValueError('COMPANY_TEST_NETWORK_FORBIDDEN')),patch.object(socket,'getaddrinfo',side_effect=ValueError('COMPANY_TEST_DNS_FORBIDDEN')):
 runpy.run_path(str(root/'tools/vnext_company.py'),run_name='__main__')
