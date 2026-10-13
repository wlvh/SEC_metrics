"""Real original through unchanged heading algorithm, explicit new capacity."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,socket,subprocess,tempfile,time
from unittest.mock import patch
from vnext.annual_update import saved_source
from vnext.sources import raw_blob_record,source_reference_record
from vnext.saved_source_checks import verify_saved_inputs
from vnext.specs import compile_spec_file
from vnext.canonical import canonical_json_bytes,content_hash,sha256_bytes,sha256_file
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext import text_results
from vnext.historical_dei import release_aware
api=release_aware(text_results)
from vnext.text_review import build_text_review_unit
from vnext.review import _create_review_decision,_system_approved_claims,SYSTEM_REVIEWER_ID,SYSTEM_REVIEW_REASON

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);a=p.parse_args()
root=a.source_root.resolve();program=Path.cwd();company='enphase_energy';cik='1463101';acc='0001463101-22-000016';name='enph-20211231.htm'
url='https://www.sec.gov/Archives/edgar/data/'+cik+'/'+acc.replace('-','')+'/'+name
t=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
    saved=saved_source(repo_root=root,url=url,accession=acc);assert saved is not None
    admission=verify_saved_inputs(data_root=root,proofs=[saved['proof']]);raw=saved['raw']
    blob=raw_blob_record(repo_root=root,repo_relative_path=saved['proof']['request_repo_relative_path'],media_type='text/html')
    ref=source_reference_record(raw_blob=blob,company_id=company,source_url=url,accession=acc,
        document_name=name,source_role='target_primary',request_attempt_id=saved['proof']['request_attempt_id'])
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    contexts=[parsed.contexts[f['context_ref']] for f in parsed.facts if f['qualified_name'].split(':')[-1]=='DocumentPeriodEndDate']
    assert len(contexts)==1
    native=contexts[0];scope={'entity_scope':'registrant'}
    target={'company_id':company,'entity':cik,'accession':acc,'period_start':native['period_start'],
            'period_end':native['period_end'],'scope':scope,'scope_key':content_hash(value=scope)}
    base=dict(target=target,source_references=[ref],raw_blobs={blob['raw_asset_id']:blob},raw_bytes_by_id={blob['raw_asset_id']:raw})
    old=compile_spec_file(path=program/'catalog/r6/D01_risk_factor_headings.md',dependency_specs={})
    try:api.create_deterministic_text_candidate(compiled_spec=old,**base)
    except ValueError as e:
        old_failure={'error_type':type(e).__name__,'reason':str(e)}
        assert str(e)=='DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND',old_failure
    else:raise AssertionError('Expected real original68 to exceed old64')
    spec_path='catalog/ordinary_risk_headings/D01_128.md';spec=compile_spec_file(path=program/spec_path,dependency_specs={})
    args=dict(compiled_spec=spec,**base);candidate=api.create_deterministic_text_candidate(**args)
    evidence=api.build_text_evidence(candidate=candidate,**args)
    unit,_=build_text_review_unit(compiled_spec=spec,candidate=candidate,evidence_check=evidence,source_bindings=[ref])
    decision=_create_review_decision(review_unit=unit,decision='APPROVE',approved_claims=_system_approved_claims(review_unit=unit),
        required_claims=spec['compiled']['required_claims'],reviewer_type='SYSTEM',reviewer_id=SYSTEM_REVIEWER_ID,
        decided_at_utc=datetime.now(timezone.utc).isoformat(),reason=SYSTEM_REVIEW_REASON,supersedes_decision_id=None)
    replay=dict(**args,company_traits=[],candidate=candidate,evidence_check=evidence,review_unit=unit,review_decisions=[decision])
    result,trace,observations=api.replay_text_result(**replay)
    calculation=time.monotonic()-t
    # The comparison is first loaded only after the source-created result.
    reference=json.loads(a.reference.read_text())['years']['2021']['reference']
    expected=reference['headings_read'];assert len(expected)==68
    expected_text='\n'.join(x['text'] if isinstance(x,dict) else x for x in expected)
    assert result['value']==expected_text
    out=Path(tempfile.mkdtemp(prefix='issue28-text68-replay-'))/'records.json'
    out.write_bytes(canonical_json_bytes(value={'result':result,'trace':trace,'observations':observations}))
    initial=sha256_file(path=out);started=time.monotonic();stored=json.loads(out.read_bytes())
    verified=api.verify_text_result(**stored,**replay);read_replay=time.monotonic()-started
    assert verified==(result,trace,observations) and sha256_file(path=out)==initial
    assert len(result['text_payload']['items'])==len(observations)==68
record={'program_root':str(program),'source_root':str(root),'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'tested_tree':'UNCOMMITTED_CAPACITY_CHANGE','source_sha256':sha256_bytes(content=raw),'source_proof':saved['proof'],
        'source_reference':ref,'source_admission':admission,'spec_path':spec_path,'spec_sha256':sha256_file(path=program/spec_path),
        'old_spec_unchanged':{'spec_path':'catalog/r6/D01_risk_factor_headings.md','failure':old_failure},
        'target':target,'new_spec_closure_hash':spec['spec_closure_hash'],'result_id':result['result_id'],
        'renderer':result['text_payload']['renderer'],'observations':len(observations),'heading_count':len(candidate['selected']),
        'text_chars':len(result['value']),'text_utf8_bytes':len(result['value'].encode()),'value_sha256':'sha256:'+sha256_bytes(content=result['value'].encode()),
        'matches_existing_reference_after_extraction':True,'existing_reference_sha256':sha256_file(path=a.reference),
        'calculation_seconds':calculation,'saved_replay_seconds':read_replay,'saved_records_path':str(out),
        'saved_record_sha256_unchanged':initial,'evidence_status':evidence['status'],'review_type':'SYSTEM_MECHANICAL_NOT_OWNER_ADOPTION',
        'native_run_created':False,'company_cli_completed':False,'calls':[0,0,0]}
(Path('docs/evidence/issue28_text_item_capacity_20261010/actual-enphase-source.json')).write_text(json.dumps(record,indent=2)+'\n')
print('headings',record['heading_count'],'chars/bytes',record['text_chars'],record['text_utf8_bytes'],'reference match true')
print('old failure',old_failure,'new renderer',record['renderer'])
print('time',calculation,read_replay,'Result',result['result_id'])
