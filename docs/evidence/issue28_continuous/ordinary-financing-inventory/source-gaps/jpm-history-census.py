import json,pathlib,sys,collections
sys.path[:0]=['.','scripts']
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_governance_input import _Sources,_history_index,_filings,history_body_alignment
from vnext.normal_source_authority import verify_saved_source_proofs
from sec_urls import submissions_url,submissions_file_url
from tests.vnext.test_normal_zero_ai_results import original_sources_only
root=pathlib.Path.cwd();out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/jpm-history-snapshot-census');out.mkdir(exist_ok=False)
with original_sources_only():
 prepared=prepare_saved_annual_input(repo_root=root,company_id='jpmorgan_chase');period=prepared['table_input']['target_period'];reader=_Sources(root,'jpmorgan_chase',prepared['entity'])
 inventory=reader.read(submissions_url(cik=int(prepared['entity'])),role='sec_submissions_inventory',media_type='application/json');body=json.loads(inventory['raw_bytes']);items=[]
 current=body['filings']['recent'];print('CURRENT',min(current['filingDate']),max(current['filingDate']),len(current['form']))
 for shard in _history_index(body,prepared['entity']):
  if shard['filingTo']<period['period_start']:continue
  source=reader.read(submissions_file_url(file_name=shard['name']),role='sec_submissions_history',media_type='application/json');data=json.loads(source['raw_bytes']);rows=_filings(data,inventory_name=shard['name']);alignment=history_body_alignment(shard=shard,rows=rows)
  vals=data.get('filings',{}).get('recent',data);all_dates=vals['filingDate'];events=[r for r in rows if r['form'] in ['8-K','8-K/A'] and period['period_start']<=r['filingDate']<=period['period_end']]
  entry={'declared':shard,'actual_all_forms_count':len(vals['form']),'actual_from':min(all_dates),'actual_to':max(all_dates),'form_counts':dict(collections.Counter(vals['form'])),'alignment':alignment,'target_events':events,'source_reference':source['source_reference']}
  items.append(entry)
  print('SHARD',json.dumps({k:v for k,v in entry.items() if k not in ['target_events','alignment','source_reference','form_counts']}));print('OUTSIDE',len(alignment['out_of_range_filings']) if alignment else 0,'TARGET_EVENTS',len(events))
  if alignment:print('OUTSIDE_SAMPLE',alignment['out_of_range_filings'][:3])
 proofs=[v['proof'] for v in reader.proofs.values()];admission=verify_saved_source_proofs(data_root=root,proofs=proofs)
for entry in reader.proofs.values():
 p=entry['proof'];h=json.loads((root/p['request_headers_repo_relative_path']).read_text());print('REQUEST',p['source_url'],'SAVED',entry.get('saved_at_utc'),'SOURCE_DATE',h.get('headers',{}).get('date'))
(out/'index.json').write_text(json.dumps({'period':period,'current_inventory':inventory['source_reference'],'items':items,'source_proofs':proofs,'source_admission':admission,'calls':{'provider':0,'paid':0,'sec':0}},ensure_ascii=False,indent=2))
