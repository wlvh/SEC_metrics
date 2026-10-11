"""Actual existing historical consumer, old/new label helper and original rows."""
import ast,hashlib,html,json,re,socket,subprocess,time
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
    prior,prior_seconds=case('ford_motor_company',year,True)
    after,after_seconds=case('ford_motor_company',year)
    assessment=after['input_assessments']['historical_statement']
    (E/('latest-ford-'+str(year)+'-assessment.json')).write_text(json.dumps(assessment,indent=2)+'\n')
    print('ACTUAL_AFTER',year,{k:assessment[k] for k in ('reason','unresolved_revenue_role') if k in assessment},flush=True)
    assert prior['results']['B02']['value'] is None,prior['results']['B02']
    assert after['results']['B02']['value'] is not None,after['results']['B02']
    assessment=after['input_assessments']['historical_statement'];scopes=assessment['paired_revenue_scopes']
    row={'year':year,'before_seconds':prior_seconds,'after_seconds':after_seconds,
         'before_result':prior['results']['B02'],'after_result':after['results']['B02'],
         'current_and_prior_scopes':scopes,'source_proofs':after['source_proofs']}
    for role in ('current','prior'):
        scope=scopes[role];assert scope['complete_scope_proven']
        selection=scope['reported_totals'][0];total=selection['total'];ref=total['source_reference']
        proof=next(p for p in after['source_proofs'] if p['source_url']==ref['source_url'])
        raw=(SOURCE/proof['request_repo_relative_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==proof['content_sha256']
        text=raw.decode('utf-8-sig');ordinal=total['ordinal']
        match=re.search(r'<ix:nonFraction\b[^>]*\bid="f-'+str(ordinal)+r'"[^>]*>.*?</ix:nonFraction>',text)
        assert match is not None
        left=text.rfind('<tr',0,match.start());right=text.index('</tr>',match.end())+len('</tr>')
        visible=' '.join(html.unescape(re.sub('<[^>]*>',' ',text[left:right])).split())
        assert 'Total revenues' in visible and '(Note 4)' in visible,visible
        row[role+'_original_total']={'source_sha256':proof['content_sha256'],'source_url':proof['source_url'],
            'native_ordinal':ordinal,'native_fact':match.group(),'original_row':visible,
            'value':total['value'],'context':total['context']}
    reports.append(row);(E/'actual-original-cases.json').write_text(json.dumps({'source_root':str(SOURCE),
        'scope':'Before uses exact old label helper with unchanged full actual consumer; not full old-checkout execution',
        'cases':reports,'protected_source_hashes':before_hashes,'new_calls':[0,0,0]},indent=2)+'\n')
    print('FORD',year,prior['results']['B02']['reason_code'],after['results']['B02']['value'],
          after['results']['B02']['result_id'],prior_seconds,after_seconds,flush=True)
negative,seconds=case('macys',2022)
assert negative['results']['B02']['value'] is None
(E/'actual-macys-negative.json').write_text(json.dumps({'seconds':seconds,'result':negative['results']['B02'],
    'assessment':negative['input_assessments']['historical_statement'],'new_calls':[0,0,0]},indent=2)+'\n')
assert before_hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
print('PASS_TWO_INDEPENDENT_FORD_ORIGINALS_AND_REAL_MACYS_WITHHELD',seconds,flush=True)
