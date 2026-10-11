"""Read actual matched annual AuditorName raw fragments separately from the resolver."""
import hashlib,json,re,html
from pathlib import Path
E=Path(__file__).parent;v=json.loads((E/'actual-company.json').read_text());out=[]
for result in v['results'][:2]:
 source=Path(result['args'][result['args'].index('--source-root')+1]);root=Path(result['first']['metrics'][0]['result_root']);manifest=json.loads((root/'manifest.json').read_text());a=json.loads((root/'input-assessments.json').read_text())['assessments']['current_auditor'];checks=[*a['current_filing_checks'],a['prior_filing_check']]
 for check in checks:
  for ref in check['source_references']:
   proof=next(p for p in manifest['source_proofs'] if p['source_url']==ref['source_url'] and p['accession']==ref['accession'] and 'sha256:'+p['content_sha256']==ref['raw_asset_id']);raw=(source/proof['request_repo_relative_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['content_sha256'];text=raw.decode('utf-8-sig');matches=[]
   # Read QName-tagged original text and its context anchor directly, not
   # normalised canonical auditor strings from the result.
   pattern=r'<(?:ix:nonNumeric\b[^>]*\bname=[\"\']dei:AuditorName[\"\'][^>]*|dei:AuditorName\b[^>]*)>(.*?)</(?:ix:nonNumeric|dei:AuditorName)\s*>'
   for m in re.finditer(pattern,text,re.I|re.S):
    value=' '.join(html.unescape(re.sub('<[^>]+>','',m.group(1))).split());start=len(text[:m.start()].encode());end=len(text[:m.end()].encode());matches.append({'text':value,'raw_start_byte':start,'raw_end_byte':end,'raw_span_sha256':hashlib.sha256(raw[start:end]).hexdigest(),'context_attribute':re.search(r'contextRef=[\"\']([^\"\']+)',m.group(0),re.I).group(1)})
   assert matches and all(m['text']=='Ernst & Young LLP' for m in matches),(ref,matches)
   out.append({'company':result['company'],'accession':ref['accession'],'source_url':ref['source_url'],'raw_sha256':proof['content_sha256'],'raw_path':str(source/proof['request_repo_relative_path']),'auditor_fragments':matches,'context_period':{k:check['facts'][0][k] for k in ('period_start','period_end','entity_identifier')},'evidence_kind':'Actual raw AuditorName text read plus current/prior source identity; not full visible audit-report independent review'})
(E/'original-auditor-fragments.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS_RAW_CURRENT_AND_PRIOR_AUDITOR_FRAGMENTS',len(out))
