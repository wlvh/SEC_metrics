"""Independent read of a partial, read-only D04 material backup, not a ledger."""
import argparse,hashlib,json,socket
from pathlib import Path
from unittest.mock import patch
from vnext.d04_native_assessment import validate_response

p=argparse.ArgumentParser();p.add_argument('--backup-root',type=Path,required=True);a=p.parse_args()
root=a.backup_root
manifest=json.loads((root/'sample.json').read_text())
assert manifest['mode']=='PARTIAL_READ_ONLY_BACKUP_NOT_EXECUTION_ROOT'
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for relative,expected in manifest['files'].items():
  assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected,relative
 call=root/'call'
 terminal=json.loads((call/'terminal.json').read_text())
 request=json.loads((call/'semantic-request.json').read_text())
 assert terminal['status']=='SUCCEEDED' and request['request_id']==manifest['request_id']
 checked=validate_response(request=request,raw_response=(call/'wire/assistant-output.bin').read_bytes())
 assert not checked['unresolved']
print(json.dumps({'ordinal':manifest['ordinal'],'request_id':request['request_id'],
    'files_checked':len(manifest['files']),'original_status':terminal['status'],
    'current_response_unresolved':len(checked['unresolved']),
    'scope':'One original call plus referenced source files and original ledger metadata; not complete ledger backup, current company reuse or new result',
    'new_calls':[0,0,0]}))
