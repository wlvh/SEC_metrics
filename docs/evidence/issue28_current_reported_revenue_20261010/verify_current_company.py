"""Actual saved-source CLI, forbidden factory repeat, independent reader; no HTTP."""
from pathlib import Path
import contextlib,csv,io,json,shutil,subprocess,sys,tempfile,time,socket
from unittest.mock import patch
from vnext.ordinary_saved_result import _ordinary_case
from vnext.canonical import sha256_file
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tools.vnext_company import main

program=Path.cwd(); existing=Path('/Users/lyuhongwang/Developer/SEC_metrics')
evidence=program/'docs/evidence/issue28_current_reported_revenue_20261010'
base=Path(tempfile.mkdtemp(prefix='issue28-current-reported-total-')); outcomes=[]
for company in ('macys','pfizer','salesforce'):
    source=base/company/'source';source.mkdir(parents=True)
    with original_sources_only():case=_ordinary_case(existing,company,'B01')
    paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    for proof in case['source_proofs']:
        paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
    for p in paths:
        target=source/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(existing/p,target)
    state=base/company/'state'; output=base/company/'output'
    args=['run','--company',company,'--source-root',str(source),'--work-dir',str(state),
          '--output-dir',str(output),'--metric','B01']
    stream=io.StringIO()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
        started=time.monotonic()
        with contextlib.redirect_stdout(stream): first_exit=main(args)
        first=time.monotonic()-started
        files={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*')
               if p.is_file() and '/results/' in str(p)}
        directories=sorted(str(p.relative_to(state)) for p in state.rglob('manifest.json'))
        started=time.monotonic()
        with patch('vnext.ordinary_current_update.create_saved_result',
                   side_effect=AssertionError('No calculation for unchanged source/config')),contextlib.redirect_stdout(stream):
            repeat_exit=main(args)
        repeat=time.monotonic()-started
        assert files=={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*')
                       if p.is_file() and '/results/' in str(p)}
        assert directories==sorted(str(p.relative_to(state)) for p in state.rglob('manifest.json'))
    reader=base/company/'reader';started=time.monotonic()
    result=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company',company,
        '--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
    read=time.monotonic()-started;assert result.returncode==0,result.stderr
    rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()))
    assert len(rows)==1 and rows[0]['value']==case['results']['B01']['value'],rows
    assert rows[0]['unit']=='USD'
    assert (rows[0]['period_start'],rows[0]['period_end'])==tuple(case['target_period'][k] for k in ('period_start','period_end'))
    references=list(csv.DictReader((reader/'metric_evidence.csv').open()))
    assert references and all(r['source_url'].startswith('https://') for r in references)
    assessment=case.get('input_assessments',{}).get('revenue_scope',{})
    if assessment.get('reported_totals'):
        total=assessment['reported_totals'][0]
        assert total['total']['value']==rows[0]['value']
        assert total['total']['source_reference']['raw_asset_id'] in {r['raw_asset_id'] for r in case['references']}
    if company=='pfizer':assert rows[0]['value']=='62579000000'
    if company=='salesforce':assert rows[0]['value']=='41525000000'
    outcomes.append({'company_id':company,'source_root':str(source),'state_root':str(state),
        'independent_reader_root':str(reader),'cli_args':args,'first_seconds':first,'repeat_seconds':repeat,
        'reader_seconds':read,'first_exit':first_exit,'repeat_exit':repeat_exit,'reader_exit':result.returncode,
        'rows':[{k:v for k,v in row.items() if k!='context_or_dimension'} for row in rows],
        'csv_sha256':sha256_file(path=reader/'metrics_matrix.csv'),
        'evidence_rows':references,'revenue_assessment':{k:assessment[k] for k in (
            'method','scope_id','status','complete_scope_proven','selected_fiscal_column_year','reported_totals') if k in assessment},
        'source_files':sorted(paths),
        'source_hashes':{p:sha256_file(path=source/p) for p in sorted(paths)},'protected_result_files':files,
        'result_directories':directories,'repeat_preserves_result_bytes_and_directories':True,
        'cli_output':stream.getvalue(),'reader_output':result.stdout})
    print(company,rows[0]['value'],rows[0]['unit'],rows[0]['period_start'],rows[0]['period_end'],
          assessment.get('status'),first,repeat,read,flush=True)
changed=subprocess.run(['git','diff','--name-only'],capture_output=True,text=True,check=True).stdout.splitlines()
record={'program_root':str(program),'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'tested_tree':'UNCOMMITTED_CURRENT_CHANGES','changed_files':changed,
        'tested_code_sha256':{p:sha256_file(path=program/p) for p in changed if (program/p).is_file()},
        'data_root':str(existing),'outcomes':outcomes,'calls':{'provider':0,'paid':0,'sec':0}}
(evidence/'final-actual-company.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
