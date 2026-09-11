"""Build or read the zero-network B06 complete draft candidate."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import r5_b06_publication as r5, publication
from vnext.canonical import canonical_json_bytes

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['prepare','read']);p.add_argument('--candidate-root',type=Path,required=True);p.add_argument('--output-json',type=Path,required=True);a=p.parse_args()
    if a.output_json.exists() or not a.output_json.is_absolute():p.error('output-json must be a new absolute external path')
    if any(part.is_symlink() for part in (a.output_json,*a.output_json.parents)):p.error('output cannot follow symbolic links')
    if ROOT==a.output_json.parent or ROOT in a.output_json.parents:p.error('output must be outside checkout')
    if a.operation=='prepare':value=r5.prepare(candidate_root=a.candidate_root)
    else:
        saved=json.loads((a.candidate_root/'prepared.json').read_text());d=a.candidate_root/'outputs/publications'/saved['publication_id'];m=publication.verify_publication_bundle(bundle_dir=d);view=publication.PublicationView(publication_id=m['publication_id'],bundle_dir=d,manifest=m)
        batch=json.loads(view.read_bytes(relative_path='internal/annual_complete_version.json'));rows=r5._rows(view.read_bytes(relative_path='metrics_matrix.csv'))
        value={'status':'READ_ONLY_COMPLETE_CANDIDATE','publication_id':view.publication_id,'candidate_status':m['candidate_status'],'previous_publication_id':m['previous_publication_id'],'rows':len(rows),'coordinates':len(batch['cumulative_result_bindings']),'selected':[view.native_result(company_id=r['company_id'],metric_id='B06')['result'] for r in batch['cumulative_result_bindings'] if r['metric_id']=='B06'],'new_provider_paid_sec_calls':[0,0,0]}
    a.output_json.parent.mkdir(parents=True,exist_ok=True);a.output_json.write_bytes(canonical_json_bytes(value=value));print(json.dumps({'status':value['status'],'output':str(a.output_json)}));return 0
if __name__=='__main__':raise SystemExit(main())
