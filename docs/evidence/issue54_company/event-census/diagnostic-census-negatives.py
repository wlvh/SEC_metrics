"""Real admitted header closure; private source copies, no financial calls."""
import json,os,shutil,sys,time
from pathlib import Path
work=Path('/workspace/work')
runtime=work/'company-event-ordinary-runtime-v2'
sys.path[:0]=[str(runtime),str(runtime/'scripts')]
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT']=str(work/'baseline-company-trust')
from vnext.company_event_census import installed_event_filings
from vnext.canonical import canonical_json_bytes,content_hash,sha256_file
from vnext.company_source_authority import EXPORT_PATH
origin=work/'company-event-ordinary-v2-state/source'
admission=json.loads((origin/EXPORT_PATH).read_text())
relative=next(p for p in admission['files'] if p.endswith('.hdr.sgml'))
rows=[]
for mutation in ('declared-header-bytes','additional-header','local-manifest-rehash','wrong-company'):
 source=work/('company-event-negative-'+mutation);shutil.copytree(origin,source)
 if mutation=='declared-header-bytes':
  path=source/relative;path.write_bytes(path.read_bytes()+b'\nBOUND_HEADER_NEGATIVE\n')
 elif mutation in ('additional-header','local-manifest-rehash'):
  extra=source/'evidence/accession_materials/marriott_international_1048286_000104828625999999/extra.hdr.sgml'
  extra.parent.mkdir();extra.write_bytes((source/relative).read_bytes())
  if mutation=='local-manifest-rehash':
   changed={**admission,'files':{**admission['files'],extra.relative_to(source).as_posix():{'sha256':sha256_file(path=extra),'size':extra.stat().st_size}}}
   changed['checkpoint_id']=content_hash(value={k:v for k,v in changed.items() if k!='checkpoint_id'})
   (source/EXPORT_PATH).write_bytes(canonical_json_bytes(value=changed))
 start=time.monotonic()
 try:
  installed_event_filings(source_root=source,company_id='enphase_energy' if mutation=='wrong-company' else 'marriott_international',allowed_ciks=['1048286'],period_start='2025-01-01',period_end='2025-12-31')
  raise AssertionError('Negative accepted: '+mutation)
 except ValueError as error:
  rows.append({'mutation':mutation,'rejected':True,'error_type':type(error).__name__,'reason':str(error),'seconds':time.monotonic()-start,'consumed_header_locator':relative if mutation=='declared-header-bytes' else None})
print(json.dumps({'status':'PASSED','scope':'REAL_TRUSTED_COMPANY_HEADER_CENSUS_PRIVATE_COPIES','uid':os.getuid(),'new_business_calls':[0,0,0],'probes':rows},indent=2))
