"""Read a relocated package through trusted PublicationView without writes/network."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext import publication as pub
from vnext.annual_adoption import _tree_files,git
export=json.loads((BASE/'export-receipt.json').read_text());root=Path(export['unpacked_directory'])
before=_tree_files(root=root);directory=root/'outputs/publications'/export['publication_id']
manifest=pub.verify_publication_bundle(bundle_dir=directory)
view=pub.PublicationView(publication_id=manifest['publication_id'],bundle_dir=directory,manifest=manifest)
record=json.loads((root/'review/read.json').read_text());checks={}
for name in ['metrics_matrix.csv','metric_evidence.csv','REPORT_十公司财务指标.md','internal/annual_complete_version.json']:
    raw=view.read_bytes(relative_path=name);checks[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
for source in record['verified_source_locations']:
    raw=view.read_bytes(relative_path=source['bundle_relative_path'])
    assert hashlib.sha256(raw).hexdigest()==source['sha256'] and len(raw)==source['size']
    checks[source['metric_id']]=source
assert _tree_files(root=root)==before
report={'status':'PASSED_RELOCATED_COMPLETE_PACKAGE_COLD_READ','source_head':git('rev-parse','HEAD').decode().strip(),
    'publication_id':manifest['publication_id'],'export_root':str(root),'checks':checks,
    'file_count':len(before),'export_bytes_unchanged':True,'network':'OS_DENIED','new_provider_paid_sec_calls':[0,0,0],
    'production_authority':'NONE_AUDIT_ONLY_EXPORT'}
(BASE/'export-cold-read.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
