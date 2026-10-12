"""Copy original D04 material to an independent read-only, non-executable backup."""
import argparse,hashlib,json,os,shutil,socket,time
from pathlib import Path
from unittest.mock import patch

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

p=argparse.ArgumentParser();p.add_argument('--ledger-root',type=Path,required=True)
p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True)
a=p.parse_args();root=a.ledger_root.resolve();destination=a.output_root.resolve()
assert destination!=root and root not in destination.parents and destination not in root.parents,'Backup must be outside the original ledger'
assert not destination.exists();stage=destination.with_name(destination.name+'.incomplete')
assert not stage.exists();stage.mkdir(parents=True);started=time.monotonic()
metadata={p.name:digest(p) for p in root.iterdir() if p.is_file() and p.suffix in {'.json','.jsonl'}}
index=json.loads(a.inventory.read_text());files={};calls=[];sources={}
def include(original,relative,expected=None):
    assert original.is_file() and not original.is_symlink()
    if relative in files:return
    before=digest(original)
    if expected is not None:assert before==expected,(relative,'original identity changed')
    target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    assert digest(target)==before==digest(original),(relative,'copy mismatch')
    target.chmod(0o400);files[relative]=before
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')):
    for name,value in metadata.items():include(root/name,'ledger-metadata-read-only/'+name,value)
    for row in index['rows']:
        ordinal=row['ordinal'];call=root/'calls'/f'{ordinal:04d}'
        request=json.loads((call/'semantic-request.json').read_text());terminal=json.loads((call/'terminal.json').read_text())
        assert request['metric_id']=='D04' and request['request_id']==row['request_id']
        assert terminal['status']==row['original_status']
        for path in call.rglob('*'):
            if path.is_file():include(path,'calls/'+f'{ordinal:04d}'+'/'+path.relative_to(call).as_posix())
        for relative,expected in terminal.get('evidence',{}).items():
            assert files['calls/'+f'{ordinal:04d}'+'/'+relative]==expected
        source=json.loads((call/'source.json').read_text())
        proofs=source.get('source_proofs',[])+source['prepared_annual_input']['source_proofs']
        for proof in proofs:
            for key,hashkey in (('request_repo_relative_path','content_sha256'),
                                ('request_headers_repo_relative_path','request_headers_sha256')):
                relative=proof.get(key)
                if relative:
                    path=(root/'source-inputs'/relative).resolve()
                    assert (root/'source-inputs') in path.parents
                    include(path,'source-inputs/'+relative,proof[hashkey]);sources[relative]=proof[hashkey]
        calls.append({'ordinal':ordinal,'request_id':request['request_id'],'company_id':request['company_id'],
            'original_status':terminal['status'],'source_id':request.get('source_id'),'period':request.get('target_period')})
    assert metadata=={name:digest(root/name) for name in metadata},'Ledger metadata changed'
    manifest={'mode':'D04_ORIGINAL_MATERIAL_BACKUP_NOT_EXECUTION_ROOT','original_ledger_root':str(root),
        'inventory_sha256':digest(a.inventory),'calls':calls,'source_files':sources,'files':files,
        'bytes':sum((stage/r).stat().st_size for r in files),'seconds':time.monotonic()-started,
        'full_ledger_backup':False,'company_result_acceptance':False,'new_calls':[0,0,0]}
    (stage/'backup.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (stage/'backup.json').chmod(0o400);os.replace(stage,destination)
print(json.dumps({'backup_root':str(destination),'calls':len(calls),'files':len(files),
    'source_files':len(sources),'bytes':manifest['bytes'],'seconds':manifest['seconds'],'new_calls':[0,0,0]},indent=2))
