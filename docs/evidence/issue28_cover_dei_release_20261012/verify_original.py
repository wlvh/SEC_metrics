"""Read saved cover/DEI originals; no company result or external request."""
import argparse
import json
import socket
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from vnext.normal_governance_input import _Sources
from vnext.historical_dei import annual_period
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.canonical import sha256_bytes
from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
import vnext.selected_reported_revenue_v2 as revenue


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',required=True)
    args=parser.parse_args()
    # A fixed source-function comparison, not a new installed runtime.
    old=dict(revenue.__dict__)
    exec(subprocess.check_output(['git','show',args.baseline+':scripts/vnext/selected_reported_revenue_v2.py'],text=True),old)
    rows=[]
    filings=[{'form':'10-K','accessionNumber':'0001628280-22-002666','primaryDocument':'mar-20211231.htm','reportDate':'2021-12-31','filingDate':'2022-02-15'},
             {'form':'10-K','accessionNumber':'0001628280-23-003485','primaryDocument':'mar-20221231.htm','reportDate':'2022-12-31','filingDate':'2023-02-14'}]
    with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
        for filing in filings:
            started=time.perf_counter()
            selected=_Sources(args.source_root,'marriott_international','1048286').auditor_filing(filing)
            primary=next(item for item in selected if item['raw_blob']['media_type']=='text/html')
            annual={'company_id':'marriott_international','entity':'1048286','filing':filing,
                'table_input':{'target_period':annual_period(raw=primary['raw_bytes'],cik='1048286',filing=filing)}}
            parsed=parse_accession_xbrl_source(raw_bytes=primary['raw_bytes'])
            record={'filing':filing,'primary_sha256':sha256_bytes(content=primary['raw_bytes']),
                'source_reference':primary['source_reference'],'actual_period':annual['table_input']['target_period']}
            if filing['reportDate']=='2021-12-31':
                try:
                    old['_defined_income_headers'](primary,parsed,annual,include_cover=True)
                except ValueError as error:
                    record['baseline_error']=str(error)
                else:
                    raise AssertionError('EXPECTED_BASELINE_COVER_FAILURE')
                assert record['baseline_error']=='TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING'
                current=revenue._defined_income_headers(primary,parsed,annual,include_cover=True,
                    dei_release=YEAR_QUARTER_OR_DATE)
                binding=current['definitions'][0]['same_source_cover_name_binding']
                assert binding['status']=='SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND'
                assert binding['cover_name']['text'] in binding['accepted_source_names']
                assert not binding['relation']['marker_jurisdiction_meaning_asserted']
                record.update(headers=current,status='COVER_AND_DEI_BOUND')
            else:
                previous=old['_defined_income_headers'](primary,parsed,annual,include_cover=True)
                current=revenue._defined_income_headers(primary,parsed,annual,include_cover=True)
                assert exact_json_value(previous)==exact_json_value(current)
                record.update(headers=current,status='DEFAULT_YEAR_PROOF_IDENTICAL')
            record['elapsed_seconds']=format(time.perf_counter()-started,'.6f')
            rows.append(record)
            print(filing['reportDate'],record['status'],record['elapsed_seconds'],flush=True)
    result={'baseline':args.baseline,'code_root':str(Path.cwd()),'source_root':str(args.source_root.resolve()),
        'rows':rows,'new_business_calls':[0,0,0],
        'scope':'cover/source identity only; not full revenue scope or company B02 acceptance'}
    args.output.write_text(json.dumps(exact_json_value(result),ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    main()
