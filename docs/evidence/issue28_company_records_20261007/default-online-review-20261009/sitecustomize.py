"""Temporary review HTTP reply injection; no program/selection/compute mock."""
import importlib.abc,importlib.machinery,sys,os,json,pathlib,socket
fixture=pathlib.Path(os.environ['SEC_REVIEW_HTTP_ROOT']).resolve()
# All processes, including installed acquisition/compute/export subprocesses,
# deny actual sockets. No business credentials are present in their environment.
def deny(*args,**kwargs):raise AssertionError('REVIEW_NETWORK_FORBIDDEN')
socket.socket.connect=deny
socket.getaddrinfo=deny

class Loader(importlib.abc.Loader):
 def __init__(self,original):self.original=original
 def create_module(self,spec):return self.original.create_module(spec) if hasattr(self.original,'create_module') else None
 def exec_module(self,module):
  self.original.exec_module(module)
  original=module.local_session
  def recorded_session(**kwargs):
   # Required temporary input: the actual native session's recorded response
   # mode. Nothing fakes its claim, capture, admission, discovery or return.
   kwargs['response']=b''
   session=original(**kwargs)
   capture=session.capture
   from sec_http import parse_request_log_rows
   rows=parse_request_log_rows(text=(fixture/'evidence/requests_log.csv').read_text())
   by_url={r['source_url']:r for r in rows if r['status_code']=='200' and not r['error'] and (fixture/r['repo_relative_path']).is_file()}
   def reply_capture(**request):
    url=request['url']
    if url not in by_url:raise ValueError('REVIEW_SAVED_HTTP_REPLY_MISSING:'+url)
    row=by_url[url];raw=(fixture/row['repo_relative_path']).read_bytes()
    import hashlib
    if len(raw)!=int(row['content_length']) or hashlib.sha256(raw).hexdigest()!=row['content_sha256']:
     raise ValueError('REVIEW_HTTP_BYTES_DIFFER:'+url)
    session.response=raw;session.response_status=200
    return capture(**request)
   session.capture=reply_capture
   return session
  module.local_session=recorded_session

class Finder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname!='vnext.company_local_acquisition':return None
  spec=importlib.machinery.PathFinder.find_spec(fullname,path)
  if spec is not None:spec.loader=Loader(spec.loader)
  return spec
sys.meta_path.insert(0,Finder())
