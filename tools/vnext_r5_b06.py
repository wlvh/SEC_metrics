"""Build or read the zero-network B06 complete draft candidate."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import r5_b06_publication as r5, publication
from vnext.canonical import canonical_json_bytes

def checked_output(path):
    if not path.is_absolute() or path.exists() or '..' in path.parts:
        raise ValueError('output must be a new canonical absolute external path')
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise ValueError('output cannot follow symbolic links')
    resolved=path.resolve(strict=False)
    if resolved==ROOT or ROOT in resolved.parents:
        raise ValueError('output must be outside checkout')
    return resolved

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['prepare','read']);p.add_argument('--candidate-root',type=Path,required=True);p.add_argument('--output-json',type=Path,required=True);a=p.parse_args()
    try:a.output_json=checked_output(a.output_json)
    except ValueError as error:p.error(str(error))
    if a.operation=='prepare':value=r5.prepare(candidate_root=a.candidate_root)
    else:
        saved=json.loads((a.candidate_root/'prepared.json').read_text());d=a.candidate_root/'outputs/publications'/saved['publication_id'];m=publication.verify_publication_bundle(bundle_dir=d);view=publication.PublicationView(publication_id=m['publication_id'],bundle_dir=d,manifest=m)
        batch=json.loads(view.read_bytes(relative_path='internal/annual_complete_version.json'));rows=r5._rows(view.read_bytes(relative_path='metrics_matrix.csv'))
        import hashlib
        selected=[];source_reads={}
        for row in batch['cumulative_result_bindings']:
            if row['metric_id']!='B06':continue
            native=view.native_result(company_id=row['company_id'],metric_id='B06');selected.append(native['result']);source_reads[row['company_id']]=[]
            records=[json.loads(line) for line in native['records_raw'].decode().splitlines()]
            for source in native['sources']:
                raw=next(r for r in records if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==source['raw_asset_id'])
                relative='internal/annual_snapshot/data/'+raw['storage_uri'];body=view.read_bytes(relative_path=relative);digest=hashlib.sha256(body).hexdigest()
                if digest!=raw['raw_asset_id'][7:]:raise ValueError('Source read differs')
                source_reads[row['company_id']].append({'source_url':source['source_url'],'bundle_path':relative,'size':len(body),'sha256':digest})
        value={'status':'READ_ONLY_COMPLETE_CANDIDATE','publication_id':view.publication_id,'candidate_status':m['candidate_status'],'previous_publication_id':m['previous_publication_id'],'rows':len(rows),'coordinates':len(batch['cumulative_result_bindings']),'selected':selected,'source_reads':source_reads,'matrix_sha256':hashlib.sha256(view.read_bytes(relative_path='metrics_matrix.csv')).hexdigest(),'evidence_sha256':hashlib.sha256(view.read_bytes(relative_path='metric_evidence.csv')).hexdigest(),'new_provider_paid_sec_calls':[0,0,0]}
    a.output_json.parent.mkdir(parents=True,exist_ok=True);a.output_json.write_bytes(canonical_json_bytes(value=value));print(json.dumps({'status':value['status'],'output':str(a.output_json)}));return 0
if __name__=='__main__':raise SystemExit(main())
