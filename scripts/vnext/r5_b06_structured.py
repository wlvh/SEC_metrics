"""Saved Company Facts debt/equity primary route, with native calculation replay.

No old metric output or producer selects an input. The table fallback remains
an explicit unresolved responsibility and this module has no network opener.
"""
from pathlib import Path
from datetime import date
from decimal import Decimal
import json
from .canonical import content_hash, sha256_file, strict_json_loads, canonical_json_bytes
from .calculator import calculate_metric, _result_and_trace
from .sources import companyfacts_structured_facts

SPEC_PATH = 'catalog/r5/B06_structured.md'
POLICY_PATH = 'config/r5_b06_structured_v1.json'
REQUIREMENT_ID = 'issue_28_v9'
RESOLVER = 'debt_equity_structured_v1'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def is_primary(spec):
    return spec['compiled']['quality_rule'].get('resolver') in {RESOLVER, 'debt_equity_carrying_v2', 'debt_equity_financing_set_v3', 'debt_equity_new_source_v1'}


def concepts(spec, data_root=None):
    rule = spec['compiled']['quality_rule']
    if rule['resolver'] in {'debt_equity_financing_set_v3','debt_equity_new_source_v1'}:
        root=Path(__file__).resolve().parents[2] if data_root is None else data_root
        path=root/rule['debt_set_registry'];need(sha256_file(path=path)==rule['debt_set_registry_sha256'],'DEBT_SET_REGISTRY_CHANGED')
        models=strict_json_loads(text=path.read_text())['debt_set_models']
        names=[rule['equity_concept']]
        for model in models.values():
            names.extend(model['inputs'].values())
            for check in model.get('checks',[]):names.extend(check['inputs'].values())
        return sorted(set(names))
    names = rule['direct_totals'] + rule['equity_concepts'] + rule['review_only_standalone'] + rule['excluded_short_debt']
    names += [n for pair in rule['same_family_pairs'] for n in pair]
    additional=[]
    for model in rule.get('debt_set_models',{}).values():
        additional.extend(model['inputs'].values())
        for check in model.get('checks',[]):additional.extend(check['inputs'].values())
    return sorted({'us-gaap:' + n for n in names}|set(additional))


def _resolve_primary_v1(*, spec, target, traits, facts, scope_reasons=()):
    """Select an exact instant and retain coverage conflicts before Calculator."""
    need(is_primary(spec), 'STRUCTURED_ROUTE_SPEC_REQUIRED')
    rule = spec['compiled']['quality_rule']
    need(target['scope'] == {'entity_scope': rule['scope']} and target['period_start'] == target['period_end'], 'STRUCTURED_INSTANT_SCOPE_REQUIRED')
    exact = [f for f in facts if f['accession'] == target['accession'] and f['entity'] == target['entity']
             and f['period_start'] == f['period_end'] == target['period_end'] and f['duration_days'] == 0
             and f['form'] == '10-K' and f['fiscal_period'] == 'FY']
    grouped = {}
    for f in exact:
        grouped.setdefault(f['concept'].split(':')[-1], []).append(f)
    reasons, chosen, selection = list(scope_reasons), [], None
    def one(name):
        values = grouped.get(name, [])
        if not values:
            return None
        if len({(f['unit'], str(f['value'])) for f in values}) != 1 or values[0]['unit'] != 'USD':
            reasons.append('CONFLICTING_FACT_OR_UNIT:' + name)
            return None
        # SEC can repeat an identical value with/without frame: preserve all
        # candidates in the audit and bind one actual fact deterministically.
        return sorted(values, key=lambda f: f['fact_id'])[0]
    totals = [f for f in (one(n) for n in rule['direct_totals']) if f is not None]
    if totals:
        if len({str(f['value']) for f in totals}) != 1:
            reasons.append('DIRECT_TOTAL_CONFLICT')
        chosen = [totals[0]]; selection = 'DIRECT_TOTAL_NO_ADDERS'
    else:
        for pair in rule['same_family_pairs']:
            parts = [one(n) for n in pair]
            if all(p is not None for p in parts):
                chosen = parts; selection = 'SAME_FAMILY_CURRENT_NONCURRENT'
                if pair[0].startswith('FinanceLease'):
                    reasons.append('LEASE_ONLY_NOT_TOTAL_DEBT_SCOPE_REVIEW')
                break
    if not chosen:
        reasons.append('STANDALONE_NONCURRENT_REQUIRES_REVIEW' if any(n in grouped for n in rule['review_only_standalone']) else 'NO_COMPLETE_DEBT_BRANCH')
    # No automatic adder is introduced. Independent debt disclosed outside a
    # selected long-term family is a coverage question, not a computed total.
    if chosen and chosen[0]['concept'].split(':')[-1] != rule['direct_totals'][0]:
        if any(any(Decimal(str(f['value'])) != 0 for f in grouped.get(n, [])) for n in rule['excluded_short_debt']):
            reasons.append('SHORT_DEBT_COVERAGE_REQUIRES_REVIEW')
        if selection == 'SAME_FAMILY_CURRENT_NONCURRENT' and chosen[0]['concept'].endswith(':LongTermDebtCurrent'):
            if any(any(Decimal(str(f['value'])) != 0 for f in grouped.get(n, [])) for n in rule['same_family_pairs'][-1]):
                reasons.append('SEPARATE_LEASE_COVERAGE_REQUIRES_REVIEW')
    equity = one(rule['equity_concepts'][0])
    if equity is None:
        reasons.append('COMMON_EQUITY_NOT_UNAMBIGUOUS')
    if any(Decimal(str(f['value'])) < 0 for f in chosen):
        reasons.append('NEGATIVE_DEBT_REQUIRES_REVIEW')
    audit = {'record_type':'STRUCTURED_PRIMARY_SELECTION','resolver':RESOLVER,'target':target,
             'branch':selection,'debt_candidates':exact,'chosen_debt_fact_ids':[f['fact_id'] for f in chosen],
             'equity_fact_id':None if equity is None else equity['fact_id'],
             'debt':None if not chosen else str(sum(Decimal(str(f['value'])) for f in chosen)),
             'equity':None if equity is None else str(equity['value']), 'reasons':sorted(set(reasons)),
             'nonpositive_equity':equity is not None and Decimal(str(equity['value'])) <= 0,
             'excluded_candidates':[{'fact_id':f['fact_id'],'concept':f['concept'],'reason':'NOT_SELECTED_BY_DECLARED_DEBT_HIERARCHY_OR_EQUITY_ROLE'} for f in exact if f not in chosen and f != equity],
             'fallback_executed':False,'provider_paid_sec_calls':[0,0,0]}
    if reasons:
        result, trace = _result_and_trace(compiled_spec=spec,target=target,applicability='APPLICABLE',quality='NONE',publication='WITHHELD',reason_code='STRUCTURED_SOURCE_AMBIGUOUS',value=None,result_unit=None,trace_steps=[{'event':'WITHHELD','reason_code':'STRUCTURED_SOURCE_AMBIGUOUS'}],input_ids=[])
        observations = []
    else:
        result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=traits,structured_facts=chosen+[equity],verified_observations=[])
    audit['result_id']=result['result_id'];audit['selection_id']=content_hash(value=audit)
    return result,trace,observations,audit


def replay_result(*, manifest, spec, trace, source_references, raw_bytes_by_id, company_ciks, data_root=None):
    """Rebuild all candidates from bound raw bytes, never from saved selection."""
    target = trace['calculation_target'];facts=[];scope_reasons=[]
    for source in source_references.values():
        if source['source_role'] == 'accession_xbrl':
            need(source['accession'] == target['accession'], 'SCOPE_ACCESSION_CHANGED')
            scope_reasons.extend(scope_warnings(raw_bytes_by_id[source['raw_asset_id']], spec, target))
        if source['source_role'] != 'companyfacts':
            continue
        payload = strict_json_loads(text=raw_bytes_by_id[source['raw_asset_id']].decode())
        years = {f['fy'] for c in payload['facts'].get('us-gaap', {}).values()
                 for values in c['units'].values() for f in values
                 if f.get('accn') == target['accession'] and f.get('end') == target['period_end']
                 and f.get('form') == '10-K' and f.get('fp') == 'FY' and type(f.get('fy')) is int}
        need(years == {manifest['target_period']['fiscal_year']}, 'STRUCTURED_SOURCE_FISCAL_LABEL_CHANGED')
        facts.extend(companyfacts_structured_facts(raw_bytes=raw_bytes_by_id[source['raw_asset_id']],source_reference=source,
                     approved_concepts=concepts(spec,data_root=data_root),allowed_ciks=company_ciks,include_instant=True))
    need(any(s['source_role']=='companyfacts' for s in source_references.values()), 'STRUCTURED_PRIMARY_SOURCE_MISSING')
    measurement=None
    if spec['compiled']['quality_rule']['resolver'] in {'debt_equity_carrying_v2','debt_equity_financing_set_v3'}:
        from .r5_b06_measurement import measurement_inputs
        if spec['compiled']['quality_rule']['resolver']=='debt_equity_financing_set_v3':
            from .r5_b06_scope import scope_inputs as measurement_inputs
        dates={f['filed'] for f in facts if f['accession']==target['accession'] and f['period_end']==target['period_end']}
        need(len(dates)==1,'MEASUREMENT_FILING_DATE_UNKNOWN')
        for source in source_references.values():
            if source['source_role']=='accession_xbrl':
                measurement=measurement_inputs(raw=raw_bytes_by_id[source['raw_asset_id']],source=source,spec=spec,target=target,filed=next(iter(dates)),data_root=data_root) or measurement
    return resolve_primary(spec=spec,target={k:v for k,v in target.items() if k!='metric_id'},traits=manifest['company_traits'],facts=facts,scope_reasons=scope_reasons,measurement=measurement)


def scope_warnings(raw, spec, target):
    from .deterministic_router import parse_accession_xbrl_source
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    members=set(spec['compiled']['quality_rule']['scope_review_dimension_members'])
    for context in parsed.contexts.values():
        if context.get('period_end') != target['period_end']:
            continue
        entity=str(context['entity_identifier'])
        need(entity.isdigit() and str(int(entity))==target['entity'], 'SCOPE_ENTITY_CHANGED')
        if any(str(v).split(':')[-1] in members for v in context['dimensions'].values()):
            return ['INDUSTRIAL_VS_FINANCE_SCOPE_REQUIRES_REVIEW']
    return []


def validate_input_binding(*, data_root, manifest):
    """A Run may not omit a discovered scope source or borrow another filing."""
    from .batch_workflow import _registry_rows
    from .sources import raw_blob_record, source_reference_record
    company=next(c for c in _registry_rows(repo_root=data_root) if c['company_id']==manifest['company_id'])
    selected=discover(data_root=data_root,company=company)
    need(selected['target_period']==manifest['target_period'], 'R5_DISCOVERED_PERIOD_CHANGED')
    expected=[]
    for proof in selected['sources']:
        is_cf='/companyfacts/' in proof['source_url']
        is_scope=proof['document_name'].endswith('_htm.xml')
        if not (is_cf or is_scope):continue
        blob=raw_blob_record(repo_root=data_root,repo_relative_path=proof['request_repo_relative_path'],media_type='application/json' if is_cf else 'application/xml')
        expected.append(source_reference_record(raw_blob=blob,company_id=company['company_id'],source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role='companyfacts' if is_cf else 'accession_xbrl',request_attempt_id=proof['request_attempt_id']))
    need(sorted(expected,key=lambda s:s['source_reference_id'])==sorted(manifest['source_references'],key=lambda s:s['source_reference_id']), 'R5_REQUIRED_SOURCE_SET_CHANGED')


def _discover_v1(*, data_root, company):
    """Pick the latest saved ordinary annual filing before any result exists."""
    from .annual_input import _saved_source, _json
    from .annual_update import _rows
    from sec_urls import submissions_url, companyfacts_url
    rows=_rows(data_root);cik=int(company['primary_cik'])
    submission,raw=_saved_source(repo_root=data_root,rows=rows,url=submissions_url(cik=cik));payload=_json(raw=raw)
    need(int(payload['cik'])==cik,'SUBMISSIONS_ENTITY_CHANGED')
    recent=payload['filings']['recent'];need(len({len(v) for v in recent.values()})==1,'SUBMISSIONS_COLUMNS_DIFFER')
    filings=[{k:v[i] for k,v in recent.items()} for i in range(len(recent['form'])) if recent['form'][i]=='10-K']
    need(bool(filings),'SAVED_ANNUAL_MISSING');filings.sort(key=lambda x:(x['reportDate'],x['filingDate']),reverse=True);filing=filings[0]
    end=filing['reportDate'];need(date.fromisoformat(end).isoformat()==end,'ANNUAL_REPORT_DATE_INVALID')
    same=[x for x in filings if x['reportDate']==end];need(len({x['accessionNumber'] for x in same})==1,'ANNUAL_ACCESSION_AMBIGUOUS')
    amendments=[{k:v[i] for k,v in recent.items()} for i in range(len(recent['form']))
                if recent['form'][i]=='10-K/A' and recent['reportDate'][i]==end]
    proof,body=_saved_source(repo_root=data_root,rows=rows,url=companyfacts_url(cik=cik),accession=filing['accessionNumber'])
    cf=_json(raw=body);need(int(cf['cik'])==cik,'COMPANYFACTS_ENTITY_CHANGED')
    years={int(f['fy']) for concept in cf['facts'].get('us-gaap',{}).values() for vals in concept['units'].values() for f in vals if f.get('accn')==filing['accessionNumber'] and f.get('end')==end and f.get('form')=='10-K' and f.get('fp')=='FY' and type(f.get('fy')) is int}
    need(len(years)==1,'SOURCE_FISCAL_YEAR_AMBIGUOUS')
    proofs=[submission,proof]
    instances=[r for r in rows if r['accession']==filing['accessionNumber'] and r['document_name'].endswith('_htm.xml') and r['status_code']=='200' and not r['error']]
    if instances:
        scope_proof,_=_saved_source(repo_root=data_root,rows=rows,url=instances[-1]['source_url'],accession=filing['accessionNumber'])
        proofs.append(scope_proof)
    return {'company_id':company['company_id'],'filing':filing,'target_period':{'fiscal_year':years.pop(),'period_start':end,'period_end':end},'sources':proofs,'entity':str(cik),
            'later_amendments':amendments,'adoption_blockers':['AMENDED_ANNUAL_REQUIRES_REVIEW'] if amendments else [],
            'source_scope':'EXACT_SAVED_ORDINARY_10K_AS_FILED_NOT_AMENDMENT_ADJUDICATION'}


def prepare_data(*, code_root, data_root):
    from .annual_runtime import _authority_files
    from .annual_continuity_sources import frozen_foundation_receipts
    from .batch_workflow import _registry_rows
    from .requirements import load_requirement_snapshot
    from .sources import resolve_repository_file
    need(not data_root.exists(),'R5_DATA_ROOT_EXISTS')
    requirement=load_requirement_snapshot(snapshot_dir=code_root/'requirements'/REQUIREMENT_ID)
    inventory=[];paths=set(_authority_files(requirement))|{'evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    # Retained loaders include superseded siblings as historical authority;
    # copy their immutable files as data, without executing embedded Python.
    paths.update(str(p.relative_to(code_root)) for p in (code_root/'requirements').rglob('*') if p.is_file())
    cursor = requirement
    while cursor.get('parent_snapshot'):
        cursor = cursor['parent_snapshot']
        paths.update(cursor.get('execution_authority', {}).get('files', {}))
    for company in _registry_rows(repo_root=code_root):
        try:entry=discover(data_root=code_root,company=company)
        except (ValueError,FileNotFoundError) as e:
            entry={'company_id':company['company_id'],'status':'LOCAL_MATERIAL_OR_SELECTION_BLOCKED','reason':str(e),'sources':[]}
        inventory.append(entry)
        for proof in entry['sources']:
            paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
    receipts=frozen_foundation_receipts()
    for relative in sorted(paths):
        source=resolve_repository_file(repo_root=code_root,repo_relative_path=relative);out=data_root/relative;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(receipts[relative]['bytes'] if relative in receipts else source.read_bytes())
    result={'record_type':'R5_SAVED_INPUT_INVENTORY','companies':inventory,'business_calls':[0,0,0]}
    (data_root/'r5-input-inventory.json').write_bytes(canonical_json_bytes(value=result))
    return result


def create_primary_run(*, data_root, run_dir, company):
    from .batch_workflow import repository_company_traits, repository_company_ciks
    from .sources import raw_blob_record, source_reference_record
    from .specs import compile_spec_file
    from .observations import scope_key
    from .requirements import load_requirement_snapshot
    from .run_store import create_run, append_run_record, validate_and_freeze_run
    spec=compile_spec_file(path=data_root/SPEC_PATH,dependency_specs={})
    need(spec['compiled']['quality_rule']['resolver']=='debt_equity_financing_set_v3','HISTORICAL_PRIMARY_RULE_READ_ONLY')
    requirement=load_requirement_snapshot(snapshot_dir=data_root/'requirements'/REQUIREMENT_ID)
    selected=discover(data_root=data_root,company=company);sourceproof=next(p for p in selected['sources'] if '/companyfacts/' in p['source_url'])
    raw=raw_blob_record(repo_root=data_root,repo_relative_path=sourceproof['request_repo_relative_path'],media_type='application/json')
    source=source_reference_record(raw_blob=raw,company_id=company['company_id'],source_url=sourceproof['source_url'],accession=sourceproof['accession'],document_name=sourceproof['document_name'],source_role='companyfacts',request_attempt_id=sourceproof['request_attempt_id'])
    scope={'entity_scope':'consolidated'};period=selected['target_period'];target={'company_id':company['company_id'],'period_start':period['period_start'],'period_end':period['period_end'],'accession':source['accession'],'entity':selected['entity'],'scope':scope,'scope_key':scope_key(scope=scope)}
    traits=repository_company_traits(repo_root=data_root,company_id=company['company_id'])
    facts=companyfacts_structured_facts(raw_bytes=(data_root/sourceproof['request_repo_relative_path']).read_bytes(),source_reference=source,approved_concepts=concepts(spec,data_root=data_root),allowed_ciks=repository_company_ciks(repo_root=data_root,company_id=company['company_id']),include_instant=True)
    extra=[];scope_reasons=[];measurement=None
    for proof in selected['sources']:
        if not proof['document_name'].endswith('_htm.xml'):
            continue
        blob=raw_blob_record(repo_root=data_root,repo_relative_path=proof['request_repo_relative_path'],media_type='application/xml')
        ref=source_reference_record(raw_blob=blob,company_id=company['company_id'],source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role='accession_xbrl',request_attempt_id=proof['request_attempt_id'])
        scope_reasons.extend(scope_warnings((data_root/proof['request_repo_relative_path']).read_bytes(),spec,target));extra.extend([blob,ref])
        if spec['compiled']['quality_rule']['resolver']=='debt_equity_financing_set_v3':
            from .r5_b06_scope import scope_inputs as measurement_inputs
            measurement=measurement_inputs(raw=(data_root/proof['request_repo_relative_path']).read_bytes(),source=ref,spec=spec,target=target,filed=selected['filing']['filingDate'],data_root=data_root) or measurement
    result,trace,observations,audit=resolve_primary(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=scope_reasons,measurement=measurement)
    run_id='run:r5-primary:'+content_hash(value={'input':selected,'spec':spec['spec_closure_hash'],'requirement':requirement['requirement_closure_hash']})[7:]
    create_run(run_dir=run_dir,run_id=run_id,company_id=company['company_id'],company_traits=traits,target_period=period,source_references=[source]+[r for r in extra if r['record_type']=='SOURCE_REFERENCE'],missing_required_source_roles=[],spec_file_hashes={SPEC_PATH:sha256_file(path=data_root/SPEC_PATH)},requirement_hashes=requirement['hashes'],requirement_id=REQUIREMENT_ID,requirement_closure_hash=requirement['requirement_closure_hash'],artifact_requirement_generation='EXPLICIT_REQUIREMENT_V1')
    for r in [raw,source,*extra,*observations,trace,result]:append_run_record(run_dir=run_dir,record=r)
    (run_dir.parent/(run_dir.name+'-selection.json')).write_bytes(canonical_json_bytes(value={'input':selected,'selection':audit}))
    manifest=validate_and_freeze_run(run_dir=run_dir,repo_root=data_root)
    return {'company_id':company['company_id'],'run_id':run_id,'manifest':manifest,'result':result,'selection':audit,'input':selected,'calls':[0,0,0]}


def current_rule(data_root):
    from .specs import compile_spec_file
    path=data_root/SPEC_PATH
    return not path.exists() or compile_spec_file(path=path,dependency_specs={})['compiled']['quality_rule']['resolver'] in {'debt_equity_carrying_v2','debt_equity_financing_set_v3'}


def discover(*,data_root,company):
    if not current_rule(data_root):
        return _discover_v1(data_root=data_root,company=company)
    from .annual_input import _saved_source,_json
    from .annual_update import _rows,_date
    from sec_urls import submissions_url
    import re
    rows=_rows(data_root);proof,raw=_saved_source(repo_root=data_root,rows=rows,url=submissions_url(cik=int(company['primary_cik'])))
    payload=_json(raw=raw);need(int(payload['cik'])==int(company['primary_cik']),'SUBMISSIONS_ENTITY_CHANGED')
    recent=payload['filings']['recent'];need(type(recent) is dict and recent and len({len(v) for v in recent.values() if type(v) is list})==1 and all(type(v) is list for v in recent.values()),'SUBMISSIONS_COLUMNS_DIFFER')
    required={'form','accessionNumber','reportDate','filingDate','primaryDocument'}
    need(required.issubset(recent),'ANNUAL_IDENTITY_FIELDS_MISSING')
    annual=[]
    for i,form in enumerate(recent['form']):
        need(type(form) is str and form and form==form.strip(),'FILING_FORM_UNKNOWN')
        if form not in {'10-K','10-K/A'}:continue
        f={k:v[i] for k,v in recent.items()}
        for field in ['reportDate','filingDate']:_date(f[field],'ANNUAL_'+field.upper()+'_DATE_INVALID')
        need(f['filingDate']>=f['reportDate'],'ANNUAL_FILING_DATE_CONFLICT')
        need(type(f['accessionNumber']) is str and re.fullmatch(r'\d{10}-\d{2}-\d{6}',f['accessionNumber']),'ACCESSION_INVALID')
        need(type(f['primaryDocument']) is str and re.fullmatch(r'[A-Za-z0-9_.-]+',f['primaryDocument']) and f['primaryDocument'] not in {'.','..'},'PRIMARY_DOCUMENT_INVALID')
        annual.append(f)
    ordinary=[f for f in annual if f['form']=='10-K'];need(ordinary,'SAVED_ANNUAL_MISSING')
    latest=max(ordinary,key=lambda f:(f['reportDate'],f['filingDate']))
    need(not any(f['reportDate']>latest['reportDate'] for f in annual),'ANNUAL_ORIGINAL_FOR_AMENDMENT_MISSING')
    shards=payload['filings'].get('files');need(type(shards) is list,'SUPPLEMENTAL_HISTORY_INVALID')
    for shard in shards:
        need(type(shard) is dict,'SUPPLEMENTAL_HISTORY_INVALID')
        start=_date(shard.get('filingFrom'),'SUPPLEMENTAL_HISTORY_DATE_UNKNOWN');end=_date(shard.get('filingTo'),'SUPPLEMENTAL_HISTORY_DATE_UNKNOWN')
        need(start<=end,'SUPPLEMENTAL_HISTORY_DATE_CONFLICT')
        # Any shard that could contain a later/relevant filing must be read by
        # a future complete-list path; this bounded current-block path stops.
        need(end<latest['reportDate'],'SUPPLEMENTAL_HISTORY_REQUIRED')
    selected=_discover_v1(data_root=data_root,company=company)
    selected['discovery_rule']='VALIDATE_ALL_ANNUAL_METADATA_V2'
    selected['history_coverage']='RECENT_BLOCK;OLDER_SHARDS_EXCLUDE_SELECTED_OR_LATER_PERIOD'
    if selected['later_amendments']:
        from sec_urls import accession_document_url
        for f in [selected['filing'],*selected['later_amendments']]:
            try:
                source,_=_saved_source(repo_root=data_root,rows=rows,url=accession_document_url(cik=int(company['primary_cik']),accession=f['accessionNumber'],document_name=f['primaryDocument']),accession=f['accessionNumber'])
                selected['sources'].append(source)
            except (ValueError,FileNotFoundError):
                selected['adoption_blockers']=sorted(set(selected['adoption_blockers']+['AMENDMENT_SOURCE_MISSING']))
    return selected


def resolve_primary(*,spec,target,traits,facts,scope_reasons=(),measurement=None):
    if spec['compiled']['quality_rule']['resolver']==RESOLVER:
        return _resolve_primary_v1(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=scope_reasons)
    if spec['compiled']['quality_rule']['resolver']=='debt_equity_financing_set_v3':
        from .r5_b06_scope import resolve_financing
        return resolve_financing(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=scope_reasons,measurement=measurement)
    from .r5_b06_measurement import resolve_carrying
    return resolve_carrying(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=scope_reasons,measurement=measurement)
