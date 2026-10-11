"""Actual existing historical consumer, old/new label helper and original rows."""
import ast,hashlib,html,json,re,socket,subprocess,time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from vnext.historical_statement_cases import prepare_historical_statement_year_case
from vnext import selected_revenue_scope_v1 as v1,selected_reported_revenue_v2 as v2
E=Path(__file__).parent;SOURCE=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
original=subprocess.check_output(['git','show','488b43871a2a06395ec4c4b155e94da6c02a06de:scripts/vnext/selected_revenue_scope_v1.py'],text=True)
node=next(x for x in ast.parse(original).body if isinstance(x,ast.FunctionDef) and x.name=='_label_key')
namespace={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'<base label helper>','exec'),namespace);old=namespace['_label_key']
protected=[SOURCE/p for p in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json')]
before_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};reports=[]
def case(company,year,before=False):
    started=time.perf_counter()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
        if before:
            with patch.object(v1,'_label_key',old),patch.object(v2,'_label_key',old):
                value=prepare_historical_statement_year_case(repo_root=SOURCE,company_id=company,metric_id='B02',fiscal_year=year)
        else:value=prepare_historical_statement_year_case(repo_root=SOURCE,company_id=company,metric_id='B02',fiscal_year=year)
    return value,time.perf_counter()-started
for year in (2023,2024):
    after,after_seconds=case('ford_motor_company',year)
    Path('/private/tmp/issue28-note-ford-'+str(year)+'-case.json').write_text(json.dumps(after)+'\n')
    assessment=after['input_assessments']['historical_statement']
    (E/('latest-ford-'+str(year)+'-assessment.json')).write_text(json.dumps({
        'kind':'OBSERVED_SELECTED_SCOPE_SUMMARY_NOT_FULL_REPLAY_RECORD',
        'scope_ids':{r:s['scope_id'] for r,s in assessment.get('paired_revenue_scopes',{}).items()},
        'result':after['results']['B02'],
        'unresolved':{k:assessment[k] for k in ('reason','unresolved_revenue_role') if k in assessment}},indent=2)+'\n')
    print('ACTUAL_AFTER',year,{k:assessment[k] for k in ('reason','unresolved_revenue_role') if k in assessment},flush=True)
    assert after['results']['B02']['value'] is not None,after['results']['B02']
    assessment=after['input_assessments']['historical_statement'];scopes=assessment['paired_revenue_scopes']
    row={'year':year,'after_seconds':after_seconds,'after_result':after['results']['B02'],
         'scope_ids':{r:s['scope_id'] for r,s in scopes.items()},'source_proofs':after['source_proofs']}
    for role in ('current','prior'):
        scope=scopes[role];assert scope['complete_scope_proven']
        selection=scope['reported_totals'][0];total=selection['total'];ref=total['source_reference']
        proof=next(p for p in after['source_proofs'] if p['source_url']==ref['source_url'])
        raw=(SOURCE/proof['request_repo_relative_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==proof['content_sha256']
        span=selection['statement_scope']['table_span'];table=raw[span['start_byte']:span['end_byte']].decode('utf-8')
        matches=[]
        for item in re.finditer(r'<ix:nonFraction\b[^>]*>.*?</ix:nonFraction>',table,re.I):
            opening=item.group().split('>',1)[0]
            attrs={k.casefold():v for k,v in re.findall(r'([\w:]+)="([^"]*)"',opening)}
            if attrs.get('name','').casefold()==total['concept'].casefold() and attrs.get('contextref')==total['context_ref']:
                matches.append((item,attrs))
        assert len(matches)==1,len(matches)
        match,attrs=matches[0]
        left=table.rfind('<tr',0,match.start());right=table.index('</tr>',match.end())+len('</tr>')
        visible=' '.join(html.unescape(re.sub('<[^>]*>',' ',table[left:right])).split())
        assert 'Total revenues' in visible and '(Note 4)' in visible,visible
        assert old('Total revenues (Note 4)') not in {'total revenue','total revenues','total net revenues'}
        fact_text=html.unescape(re.sub('<[^>]*>',' ',match.group())).replace(',','').strip()
        assert Decimal(fact_text)*(Decimal(10)**int(attrs['scale']))==Decimal(total['value'])
        assert attrs['scale']=='6' and total['unit']=='USD' and selection['xml_check']=='MATCH'
        for unit in selection['unit_sources']:
            proof=unit['proof']
            if 'start_byte' in proof:assert hashlib.sha256(raw[proof['start_byte']:proof['end_byte']]).hexdigest()==proof['span_sha256']
        row[role+'_original_total']={'source_sha256':proof['content_sha256'] if 'content_sha256' in proof else hashlib.sha256(raw).hexdigest(),
            'source_url':ref['source_url'],'native_ordinal':total['ordinal'],'native_fact':match.group(),
            'native_fact_byte_start':span['start_byte']+len(table[:match.start()].encode()),
            'original_row':visible,'value':total['value'],'context':total['context'],
            'statement':selection['statement_scope'],'unit_sources':selection['unit_sources'],
            'xml_check':selection['xml_check']}
    reports.append(row);(E/'actual-original-cases.json').write_text(json.dumps({'source_root':str(SOURCE),
        'scope':'Actual current consumer and original rows; old formatter checked on those row labels, not full old-checkout execution',
        'cases':reports,'protected_source_hashes':before_hashes,'new_calls':[0,0,0]},indent=2)+'\n')
    print('FORD',year,after['results']['B02']['value'],after['results']['B02']['result_id'],after_seconds,flush=True)
negative,seconds=case('macys',2022)
assert negative['results']['B02']['value'] is None
(E/'actual-macys-negative.json').write_text(json.dumps({'seconds':seconds,'result':negative['results']['B02'],
    'assessment':negative['input_assessments']['historical_statement'],'new_calls':[0,0,0]},indent=2)+'\n')
assert before_hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
print('PASS_TWO_INDEPENDENT_FORD_ORIGINALS_AND_REAL_MACYS_WITHHELD',seconds,flush=True)
