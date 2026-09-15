import csv,io,json,hashlib,tarfile
from pathlib import Path
from vnext.canonical import content_hash
archive=Path('docs/evidence/issue28_continuous/ordinary-release-preparation/material.tar.gz')
with tarfile.open(archive) as t:
 names=set(t.getnames())
 assert 'prepared/ordinary_release_preparation.json'in names
 read=lambda path:t.extractfile(path).read()
 p=json.loads(read('prepared/ordinary_release_preparation.json'));c=p['composition']
 assert p['preparation_id']==content_hash(value={k:v for k,v in p.items()if k!='preparation_id'})
 assert c['publication_credit']=='NONE_PREPARATION_ONLY' and c['production_authorized'] is False and c['switch_available'] is False and c['full390_acceptance'] is False
 assert 'prepared/publication_manifest.json'not in names
 predecessor='prepared/predecessor/'+p['inputs']['predecessor']['publication_id']+'/'
 assert hashlib.sha256(read(predecessor+'publication_manifest.json')).hexdigest()==p['inputs']['predecessor']['manifest_sha256']
 selected={(q['render_receipt']['primary_metric_id'],q['company_id'])for q in c['selected_results']}
 selected_names={('Pfizer','B01'),('Salesforce','C02')}
 key=lambda row:(row['company'],row['metric_id'])
 counts={}
 for filename in ['metrics_matrix.csv','metric_evidence.csv']:
  before=list(csv.DictReader(io.StringIO(read(predecessor+filename).decode())))
  after=list(csv.DictReader(io.StringIO(read('prepared/'+filename).decode())))
  inherited_before=[r for r in before if key(r)not in selected_names]
  inherited_after=[r for r in after if key(r)not in selected_names]
  assert inherited_before==inherited_after
  counts[filename]={'total_rows':len(after),'unchanged_inherited_rows':len(inherited_after)}
 checked_sources=set()
 for q in c['selected_results']:
  assert q['source_admission']['source_credit']=='PREEXISTING_SAVED_ACQUISITIONS_ONLY'
  for s in q['source_locations']:
   if s['package_path']in checked_sources:continue
   assert hashlib.sha256(read('prepared/'+s['package_path'])).hexdigest()==s['sha256']
   checked_sources.add(s['package_path'])
 assert counts['metrics_matrix.csv']=={'total_rows':327,'unchanged_inherited_rows':325}
 result={'status':'PASS','scope':'Independent archived preparation identity, predecessor digest, row/evidence inheritance and selected source byte audit; no native recomputation rerun',
  'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'preparation_id':p['preparation_id'],'counts':counts,
  'selected_unique_original_files_hashed':len(checked_sources),'selected_modes':[{'company':q['company_id'],'metric':q['metric_id'],'value_kind':q['value_kind'],'source_credit':q['source_admission']['source_credit']}for q in c['selected_results']],
  'credit':'NONE_PREPARATION_ONLY','new_calls':[0,0,0]}
Path('/tmp/sec_metrics_issue28_continuous/refresh-release-independent-review/release-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
