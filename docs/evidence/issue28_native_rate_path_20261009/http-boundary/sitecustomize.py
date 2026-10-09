"""External HTTP replay only; native LIVE branch including rate lock is real.

All task data/ledgers are isolated test state. Internal LIVE receipt labels do
not grant real acquisition/production credit; no socket/DNS is permitted.
"""
import importlib.abc,importlib.machinery,sys,os,pathlib,socket,io,json
source=pathlib.Path(os.environ['SEC_RATE_TEST_HTTP_ROOT']).resolve()
trace=pathlib.Path(os.environ['SEC_RATE_TEST_HTTP_TRACE'])
def deny(*args,**kwargs):raise AssertionError('RATE_TEST_NETWORK_FORBIDDEN')
socket.socket.connect=deny;socket.getaddrinfo=deny
class Response(io.BytesIO):
 def __init__(self,raw,headers):super().__init__(raw);self.status=200;self.headers=headers
class Loader(importlib.abc.Loader):
 def __init__(self,original):self.original=original
 def create_module(self,spec):return self.original.create_module(spec) if hasattr(self.original,'create_module') else None
 def exec_module(self,module):
  self.original.exec_module(module)
  def replay(*,request,timeout):
   rows=module.parse_request_log_rows(text=(source/'evidence/requests_log.csv').read_text())
   matches=[r for r in rows if r['source_url']==request.full_url and r['status_code']=='200' and not r['error']]
   if not matches:raise ValueError('RATE_TEST_REPLY_MISSING:'+request.full_url)
   row=matches[-1];raw=(source/row['repo_relative_path']).read_bytes()
   import hashlib
   if hashlib.sha256(raw).hexdigest()!=row['content_sha256'] or len(raw)!=int(row['content_length']):
    raise ValueError('RATE_TEST_REPLY_BYTES_DIFFER:'+request.full_url)
   with trace.open('a') as out:out.write(json.dumps({'url':request.full_url,'bytes':len(raw),'sha256':row['content_sha256']})+'\n')
   return Response(raw,{'Content-Type':'application/octet-stream'})
  module.urlopen=replay
class Finder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname!='sec_http':return None
  spec=importlib.machinery.PathFinder.find_spec(fullname,path)
  if spec is not None:spec.loader=Loader(spec.loader)
  return spec
sys.meta_path.insert(0,Finder())
