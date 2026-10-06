import json,re,html,pathlib
from decimal import Decimal
reports=json.load(open('/private/tmp/issue28-native-source-only-company-results.json'));checks=[]
for report in reports:
 for item in report['metrics']:
  records=[json.loads(s) for s in (pathlib.Path(item['result_root'])/'records.jsonl').read_text().splitlines()]
  claim=next(r for r in records if r.get('record_type')=='DETERMINISTIC_VERIFIED_CLAIM' and r.get('claim_kind')=='ACCESSION_XBRL_NUMERIC_FACT')
  ref=next(r for r in records if r.get('source_reference_id')==claim['source_reference_id'] and r['record_type']=='SOURCE_REFERENCE')
  blob=next(r for r in records if r.get('raw_asset_id')==ref['raw_asset_id'] and r['record_type']=='RAW_BLOB')
  raw=(pathlib.Path(report['source_root'])/blob['storage_uri']).read_text();locator=claim['locator']
  hits=[]
  for m in re.finditer(r'<ix:nonfraction\b([^>]*)>(.*?)</ix:nonfraction>',raw,re.I|re.S):
   attrs={a.lower():html.unescape(v) for a,v in re.findall(r'([\w:.-]+)="([^"]*)"',m[1])}
   if attrs.get('name')==locator['qualified_name'] and attrs.get('contextref')==locator['context_ref']:hits.append((m,attrs))
  assert len(hits)==1,(item['metric_id'],len(hits));m,attrs=hits[0]
  lexical=html.unescape(re.sub('<[^>]+>','',m[2])).strip().replace(',','')
  value=Decimal(lexical)*(Decimal(10)**int(attrs.get('scale','0')))
  if attrs.get('sign')=='-':value=-value
  assert value==Decimal(item['actual_result']['value'])
  def element(local,identity):
   found=re.search(r'<(?:[\w-]+:)?'+local+r'\b[^>]*\bid="'+re.escape(identity)+r'"[^>]*>.*?</(?:[\w-]+:)?'+local+r'>',raw,re.I|re.S)
   assert found,(local,identity)
   return found[0]
  check={'company':report['company_id'],'metric':item['metric_id'],'source_file':str(pathlib.Path(report['source_root'])/blob['storage_uri']),
         'raw_fact':m[0],'raw_context':element('context',attrs['contextref']),'raw_unit':element('unit',attrs['unitref']),
         'scaled_value':str(value),'saved_value':item['actual_result']['value'],'saved_unit':item['actual_result']['unit'],
         'fiscal_year':2026 if item['metric_id']=='B12' else 2025,'method':'direct raw-tag/context/unit extraction and independent Decimal scaling; no metric selector or expected answer supplied'}
  checks.append(check)
  print(item['metric_id'],value,'context',check['raw_context'][:900],'unit',check['raw_unit'],flush=True)
pathlib.Path('/private/tmp/issue28-native-original-quoted-check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
