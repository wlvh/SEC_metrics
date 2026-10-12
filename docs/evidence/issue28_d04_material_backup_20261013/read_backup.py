"""Independent disk read of copied original calls; no ledger or execution credit."""
import argparse,collections,hashlib,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.d04_native_assessment import validate_response

p=argparse.ArgumentParser();p.add_argument('--backup-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.backup_root.resolve();start=time.monotonic()
assert not a.output.exists();manifest=json.loads((root/'backup.json').read_text())
assert manifest['mode']=='D04_ORIGINAL_MATERIAL_BACKUP_NOT_EXECUTION_ROOT'
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
counts=collections.Counter();companies=collections.defaultdict(collections.Counter);seen=set()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')):
    for relative,expected in manifest['files'].items():
        path=(root/relative).resolve();assert root in path.parents
        assert digest(path)==expected,relative
    claims={row['ordinal']:row for row in (json.loads(line) for line in
        (root/'ledger-metadata-read-only/claims.jsonl').read_text().splitlines())}
    for row in manifest['calls']:
        ordinal=row['ordinal'];assert ordinal not in seen;seen.add(ordinal);call=root/'calls'/f'{ordinal:04d}'
        request=json.loads((call/'semantic-request.json').read_text());terminal=json.loads((call/'terminal.json').read_text())
        assert request['request_id']==row['request_id'] and terminal['status']==row['original_status']
        assert ordinal in claims and claims[ordinal]['channel']=='PROVIDER'
        for relative,expected in terminal.get('evidence',{}).items():
            assert manifest['files'].get('calls/'+f'{ordinal:04d}'+'/'+relative)==expected,relative
        if terminal['status']=='SUCCEEDED':
            checked=validate_response(request=request,raw_response=(call/'wire/assistant-output.bin').read_bytes())
            assert not checked['unresolved'];status='ORIGINAL_RESPONSE_READ_AND_CHECKED'
        else:status='HISTORICAL_FAILURE_RETAINED'
        counts[status]+=1;companies[row['company_id']][status]+=1
result={'backup_root':str(root),'original_ledger_root':manifest['original_ledger_root'],
    'files_checked':len(manifest['files']),'bytes':manifest['bytes'],'counts':dict(counts),
    'by_company':{k:dict(v) for k,v in sorted(companies.items())},'seconds':time.monotonic()-start,
    'full_ledger_restore':False,'current_company_result_acceptance':False,'new_calls':[0,0,0]}
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
