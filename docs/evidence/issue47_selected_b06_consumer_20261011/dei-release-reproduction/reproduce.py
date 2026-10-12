"""Read two saved originals through the existing historical and equity paths."""
import argparse,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext.b06_guarded_result_v3 import _source_equity
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.normal_annual_input import annual_period
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();records=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    for company,year in [('enphase_energy',2021),('salesforce',2022)]:
        started=time.monotonic();selected=prepare_selected_debt_sources(repo_root=args.source_root,company_id=company,fiscal_year=year)
        annual=selected['annual']['original_input'];source=selected['preparation']['primary'];period=annual['table_input']['target_period'];raw=source['raw_bytes']
        parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
        namespaces=sorted({meta.facts[f['ordinal']]['concept'][0] for f in parsed.facts if meta.facts[f['ordinal']]['concept'][1].casefold() in {'documenttype','stockholdersequity'}})
        try:
            _source_equity(raw=raw,kind='primary',target={'entity':annual['entity'],'period_end':period['period_end']},period=period,filing=annual['filing'])
        except ValueError as error:
            failure={'reason':str(error),'error_type':type(error).__name__,'category':getattr(error,'category',None)}
        else:
            raise AssertionError('This before reproduction expects the recorded namespace failure')
        assert annual_period(raw=raw,cik=annual['entity'],filing=annual['filing'],dei_release='YEAR_QUARTER_OR_DATE')==period
        records.append({'company':company,'year':year,'filing':annual['filing'],'period':period,'source_reference':source['source_reference'],'observed_namespaces':namespaces,'historical_preparation_passed':True,'shared_guard_failure':failure,'explicit_annual_reader_passed':True,'seconds':time.monotonic()-started,'financial_calculation':False})
args.output.write_text(json.dumps({'records':records,'new_calls':0},ensure_ascii=False,indent=2)+'\n')
