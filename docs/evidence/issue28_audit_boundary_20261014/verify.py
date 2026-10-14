import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from vnext.annual_sources import saved_source
from sec_urls import accession_document_url
from vnext.sources import raw_blob_record,source_reference_record
from vnext.text_coverage import build_text_document
from vnext import text_business_candidates as candidates
from vnext.going_concern_source import _input_units
from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
results=[]
for year,accession,expected in [(2023,'0000018926-24-000016',996),(2024,'0000018926-25-000010',1081)]:
 start=time.perf_counter();name=f'lumn-{year}1231.htm';url=accession_document_url(cik=18926,accession=accession,document_name=name)
 source=saved_source(repo_root=SOURCE,url=url,accession=accession);assert source is not None
 proof=source['proof'];blob=raw_blob_record(repo_root=SOURCE,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
 ref=source_reference_record(raw_blob=blob,company_id='lumen_technologies',source_url=url,accession=accession,document_name=name,source_role='target_primary',request_attempt_id=proof['request_attempt_id'])
 d=build_text_document(raw_bytes=source['raw'],raw_blob=blob,source_reference=ref,expected_company_id='lumen_technologies',expected_cik='18926',expected_period_end=f'{year}-12-31',namespace_policy=YEAR_QUARTER_OR_DATE)
 before_units=_input_units(d)
 with patch.object(candidates,'_financial_report_boundary',side_effect=lambda b:b.get('emphasized') and candidates._FINANCIAL_HEADING.match(b['text'])):
  old=candidates.going_concern_candidates(document=d)
 new=candidates.going_concern_candidates(document=d)
 assert _input_units(d)==before_units
 old_ranges=[(r['start_block'],r.get('end_block_exclusive')) for r in old['auditor_report_ranges']]
 new_ranges=[(r['start_block'],r.get('end_block_exclusive')) for r in new['auditor_report_ranges']]
 second=new['auditor_report_ranges'][1];assert second['end_block_exclusive']==expected,(year,new_ranges)
 assert second['closing_heading']['text']=='CONSOLIDATED STATEMENTS OF OPERATIONS'
 assert old_ranges[1][1]>expected
 legal_index=2613 if year==2023 else 2942
 assert d['blocks'][legal_index]['text'] in [row[1] for u in before_units for row in u['blocks']]
 assert not(second['start_block']<=legal_index<second['end_block_exclusive'])
 rows={'year':year,'accession':accession,'raw_sha256':hashlib.sha256(source['raw']).hexdigest(),'seconds':time.perf_counter()-start,'before_ranges':old_ranges,'after_ranges':new_ranges,'closing_heading':second['closing_heading'],'all_unit_bytes_and_ids_preserved':True,'legal_block_kept':legal_index,'unit_count':len(before_units),'document_id':d['text_document_id'],'namespace_policy':YEAR_QUARTER_OR_DATE,'source_proof':proof,'semantic_absence_or_result_credit':False}
 results.append(rows);print(year,rows['seconds'],old_ranges,new_ranges,flush=True)
(OUT/'actual-ranges.json').write_text(json.dumps({'code_root':str(ROOT),'code_state':'named uncommitted financial boundary helper','rows':results,'calls':[0,0,0],'source_root_read_only':str(SOURCE)},indent=2)+'\n')
