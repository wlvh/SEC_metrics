"""Rebuild ordinary catalog metrics from original current/prior SEC facts.

The existing catalog owns formulas and concept priority. This source adapter
supplies filing identities and actual periods without reading old results or
entering the historical release planner. It creates native records, not Runs.
"""
from datetime import date, timedelta
from decimal import Decimal, DecimalException
from pathlib import Path
import re

from sec_urls import companyfacts_url, submissions_url, submissions_file_url
from .annual_sources import AnnualUpdateError
from .batch_workflow import BatchWorkflowError
from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_loads
from .deterministic_router import adapt_companyfacts
from .normal_annual_input import annual_period, _registry_rows, NormalAnnualInputError
from .annual_amendment_scope import prepare_saved_amendment_input, POLICY_PATH as AMENDMENT_POLICY_PATH
from .instant_balance_amendment import prepare_instant_balance_amendment_input, POLICY_PATH as INSTANT_POLICY_PATH
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value, POLICY_PATH as FISCAL_LABEL_POLICY_PATH
from .normal_governance_input import _Sources, _filings, _history_index, history_body_alignment, NormalGovernanceInputError
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .paired_measure_v1 import PAIRED_MEASURE_REASON, paired_measure_problem
from .observations import scope_key
from .sources import resolve_repository_file, SourceError
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
    _deterministic_metric_graph, _manual_result_trace, _exact_filing_source_set)
from .deterministic_catalog import ZeroAiReleaseError
from .selected_income_source_v1 import IncomeSourceError


CATALOG_PATH = "catalog/deterministic_metrics.json"
_AUTHORITY_PATHS = (CATALOG_PATH, FISCAL_LABEL_POLICY_PATH, AMENDMENT_POLICY_PATH, INSTANT_POLICY_PATH, "config/company_registry.csv", "catalog/company_traits.yaml",
                    "config/metric_applicability.yaml")
_SOURCE_ERRORS = (AnnualUpdateError, BatchWorkflowError, NormalAnnualInputError,
                  NormalGovernanceInputError, SourceError, ZeroAiReleaseError, IncomeSourceError)


class NormalCompanyfactsError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise NormalCompanyfactsError(reason)


def _authority(root):
    files = {}
    for relative in _AUTHORITY_PATHS:
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=root, repo_relative_path=relative)) == expected,
              "NORMAL_COMPANYFACTS_INSTALLED_AUTHORITY_CHANGED:" + relative)
        files[relative] = expected
    return files


def _prior_filing(reader, inventory, prepared):
    """Prove the immediately preceding ordinary filing in relevant metadata."""
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    rows = [(r, inventory) for r in _filings(payload, inventory_name=inventory["source_reference"]["document_name"])]
    current_end = prepared["filing"]["reportDate"]
    for shard in _history_index(payload, prepared["entity"]):
        prior_end = max((r["reportDate"] for r, _ in rows if r["form"] == "10-K" and r["reportDate"] < current_end), default="")
        if prior_end and shard["filingTo"] < prior_end:
            break
        source = reader.read(submissions_file_url(file_name=shard["name"]), role="sec_submissions_history", media_type="application/json")
        body = strict_json_loads(text=source["raw_bytes"].decode("utf-8"))
        _need("cik" not in body or str(body["cik"]).isdigit() and int(body["cik"]) == int(prepared["entity"]),
              "NORMAL_COMPANYFACTS_PRIOR_HISTORY_ENTITY_CONFLICT")
        values = _filings(body, inventory_name=shard["name"])
        _need(history_body_alignment(shard=shard, rows=values) is None,
              "NORMAL_COMPANYFACTS_PRIOR_HISTORY_SNAPSHOT_CONFLICT")
        rows.extend((r, source) for r in values)
    _need(len({r["accessionNumber"] for r, _ in rows}) == len(rows), "NORMAL_COMPANYFACTS_PRIOR_METADATA_OVERLAP")
    prior_end = max((r["reportDate"] for r, _ in rows if r["form"] == "10-K" and r["reportDate"] < current_end), default="")
    matches = [(r, s) for r, s in rows if r["form"] == "10-K" and r["reportDate"] == prior_end]
    _need(len(matches) == 1, "NORMAL_COMPANYFACTS_PRIOR_ORDINARY_MISSING_OR_AMBIGUOUS")
    _need(not any(r["form"] == "10-K/A" and r["reportDate"] == prior_end for r, _ in rows),
          "NORMAL_COMPANYFACTS_PRIOR_AMENDMENT_REPLAY_NOT_IMPLEMENTED")
    return matches[0]


def _filing_source(reader, prepared, filing, inventory, concepts):
    source = reader.read(companyfacts_url(cik=int(prepared["entity"])), accession=filing["accessionNumber"],
                         role="companyfacts", media_type="application/json")
    manifest = _exact_filing_source_set(company_id=prepared["company_id"], source_role="companyfacts",
        reference=source["source_reference"], inventory_reference=inventory["source_reference"], inventory_bytes=inventory["raw_bytes"])
    claims = adapt_companyfacts(raw_bytes=source["raw_bytes"], source_reference=source["source_reference"],
        source_set_manifest=manifest, approved_concepts=concepts, allowed_ciks=[prepared["entity"]], include_instant=True)
    return {"reference":source["source_reference"], "manifest":manifest}, claims


def _original_revenue_claims(*, reader, prepared, filing, period, claims, concepts,
                             allow_single_revenue_line, current_scope=None, current_filing=None,
                             current_claims=None):
    """Admit each year's original full total without changing claim identities.

    This current consumer reuses the public statement proof. Later comparative
    columns do not replace the immediately preceding filing's original value.
    """
    from .fiscal_year_labels import inspect_fiscal_year_labels
    from .normal_annual_input_v2 import _choose_fiscal_year
    from .normal_zero_ai_results import _revenue_admission
    concepts=[c.split(':')[-1] for c in concepts]
    eligible = [c for c in claims if c['locator']['concept'] in concepts
        and c['attributes']['accession']==filing['accessionNumber'] and c['unit']=='USD'
        and (c['locator']['period_start'],c['locator']['period_end'])
            ==(period['period_start'],period['period_end'])]
    _need(eligible, 'NORMAL_COMPANYFACTS_REVENUE_ORIGINAL_FACTS_MISSING')
    if len({Decimal(c['value']) for c in eligible})==1:
        return claims, {'method':'NONCOMPETING_APPROVED_REVENUE_FACTS',
            'status':'NO_COMPETING_REVENUE_AMOUNTS','complete_scope_proven':False,
            'original_value_retained':True,'filing':filing,'actual_period':period}
    primary = reader.primary(filing, required=False)
    if primary is None:
        return _prior_revenue_from_comparative(reader=reader, prepared=prepared,
            filing=filing, period=period, claims=claims, concepts=concepts,
            current_scope=current_scope, current_filing=current_filing, current_claims=current_claims)
    facts = reader.read(companyfacts_url(cik=int(prepared['entity'])),
        accession=filing['accessionNumber'], role='companyfacts', media_type='application/json')
    original_period = annual_period(raw=primary['raw_bytes'], cik=prepared['entity'], filing=filing)
    _need(all(original_period[k] == period[k] for k in ('period_start','period_end')),
          'NORMAL_COMPANYFACTS_REVENUE_ORIGINAL_PERIOD_CHANGED')
    inspected = inspect_fiscal_year_labels(primary_bytes=primary['raw_bytes'],
        companyfacts_bytes=facts['raw_bytes'], expected_primary_sha256=sha256_bytes(content=primary['raw_bytes']),
        expected_companyfacts_sha256=sha256_bytes(content=facts['raw_bytes']),
        expected_cik=prepared['entity'], filing=filing)
    year, _ = _choose_fiscal_year(inspected)
    label = {'record_type':'ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION','source_inspection':inspected,
        'original_dei_fiscal_year':original_period['fiscal_year'],'selected_fiscal_year':year}
    annual = {'company_id':prepared['company_id'],'entity':prepared['entity'],'filing':filing,
              'table_input':{'target_period':original_period}}
    scope, admit, _ = _revenue_admission(primary=primary, annual=annual,
        approved_concepts=['us-gaap:'+c.split(':')[-1] for c in concepts],
        contract='reported-total-v2', fiscal_label_resolution=label,
        allow_single_revenue_line=allow_single_revenue_line)
    # Match B01's existing admission: a proven total filters competing facts;
    # absence of a demonstrated split retains the catalog path and records
    # complete_scope_proven=False. A source/period error never falls back.
    _need(all(c['claim_kind']=='COMPANYFACTS_NUMERIC_FACT' and ':' not in c['locator']['concept']
              for c in claims), 'NORMAL_COMPANYFACTS_REVENUE_CLAIM_KIND_CHANGED')
    views = [{**c['locator'], **c['attributes'], 'concept':'us-gaap:'+c['locator']['concept'],
        'value':c['value'],'unit':c['unit'],'verified_claim_id':c['verified_claim_id']} for c in claims]
    allowed = {v['verified_claim_id'] for v in admit(facts=views, scope=scope)}
    return [c for c in claims if c['verified_claim_id'] in allowed], scope


def _prior_revenue_from_comparative(*, reader, prepared, filing, period, claims, concepts,
                                   current_scope, current_filing, current_claims):
    """Prove the total concept in the current statement, keep original prior value.

    The current comparative cell is evidence of scope, never a replacement
    monetary operand. The prior original XML and Company Facts still own it.
    """
    from .deterministic_router import parse_accession_xbrl_source
    from .financial_structured import _InlineTableIndex, _fact_cells
    from .financial_duration import _column_period, _cell_proof
    from .text_results_v2 import _ReportedFactMetadata, _verified_context
    from .governance_signals import _source_value
    from .selected_income_source_v1 import native_income_reports
    from .selected_revenue_scope_v1 import UNIT_HEADER
    from .xbrl_namespace_policy import YEAR_ONLY, is_fasb_namespace
    _need(current_filing and current_scope and current_scope.get('reported_totals')
          and current_scope.get('complete_scope_proven'),
          'NORMAL_COMPANYFACTS_PRIOR_REVENUE_COMPARATIVE_SCOPE_UNPROVEN')
    _need(date.fromisoformat(period['period_end'])+timedelta(days=1)
          ==date.fromisoformat(prepared['table_input']['target_period']['period_start']),
          'NORMAL_COMPANYFACTS_PRIOR_REVENUE_COMPARATIVE_PERIOD_CHANGED')
    primary=reader.primary(current_filing);raw=primary['raw_bytes']
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    by_ordinal={f['ordinal']:f for f in parsed.facts}
    meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
    _need(meta.ordinal==len(parsed.facts), 'NORMAL_COMPANYFACTS_COMPARATIVE_NATIVE_STREAM_CHANGED')
    index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
    totals=current_scope['reported_totals'];wanted={x['total']['concept'] for x in totals}
    rows=[]
    for fact in parsed.facts:
        info=meta.facts[fact['ordinal']];uri,name=info['concept'];context=parsed.contexts[fact['context_ref']]
        if 'us-gaap:'+name not in wanted or (context['period_start'],context['period_end'])!=(period['period_start'],period['period_end']):continue
        if context['dimensions'] or context['typed_dimension_count']:continue
        _need(str(int(context['entity_identifier']))==prepared['entity']
              and is_fasb_namespace(uri,namespace_policy=YEAR_ONLY)
              and meta.units.get(fact['unit_ref'])=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
              'NORMAL_COMPANYFACTS_COMPARATIVE_ENTITY_UNIT_OR_CONCEPT_CHANGED')
        rows.append({'concept':'us-gaap:'+name,'value':_source_value(fact,info),'unit':'USD',
            'period_start':context['period_start'],'period_end':context['period_end'],
            'ordinal':fact['ordinal'],'context_ref':fact['context_ref'],'scale':int(fact['scale'] or 0),
            'context_proof':_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta),
            'source_reference':primary['source_reference']})
    bound=_fact_cells(index,parsed,{r['ordinal'] for r in rows});matched=[]
    for row in rows:
        if row['ordinal'] not in bound:continue
        table,cell=bound[row['ordinal']]
        for total in totals:
            if (row['concept']!=total['total']['concept'] or table['table_id']!=total['total_cell']['table_id']
                    or cell['row_index']!=total['total_cell']['row_index']):continue
            _need(row['scale']==int(by_ordinal[total['total']['ordinal']]['scale'] or 0),
                  'NORMAL_COMPANYFACTS_COMPARATIVE_VISIBLE_SCALE_CHANGED')
            extra=tuple(re.escape(u['text']) for u in total['unit_sources'])
            column,headers,reason=_column_period(table=table,selected=cell,extra_header_descriptors=UNIT_HEADER+extra)
            _need(not reason and column['year']==current_scope['selected_fiscal_column_year']-1
                  and (column.get('date') is None or column['date'].isoformat()==period['period_end']),
                  'NORMAL_COMPANYFACTS_COMPARATIVE_VISIBLE_PERIOD_CHANGED')
            matched.append({**row,'cell':_cell_proof(table=table,cell=cell),
                'year_headers':[_cell_proof(table=table,cell=h) for h,_,_ in headers],
                'current_total_scope_id':current_scope['scope_id']})
    _need(matched and len({(r['concept'],Decimal(r['value'])) for r in matched})==1,
          'NORMAL_COMPANYFACTS_PRIOR_REVENUE_COMPARATIVE_MISSING_OR_CONFLICTING')
    concept=matched[0]['concept'].split(':')[-1]
    _need(current_claims and all(any(c['locator']['concept']==concept and c['unit']=='USD'
          and c['attributes']['accession']==current_filing['accessionNumber']
          and (c['locator']['period_start'],c['locator']['period_end'])==(period['period_start'],period['period_end'])
          and Decimal(c['value'])==Decimal(r['value']) for c in current_claims) for r in matched),
          'NORMAL_COMPANYFACTS_COMPARATIVE_COMPANYFACTS_VALUE_DIFFERS')
    original=[c for c in claims if c['locator']['concept']==concept and c['unit']=='USD'
        and c['attributes']['accession']==filing['accessionNumber']
        and (c['locator']['period_start'],c['locator']['period_end'])==(period['period_start'],period['period_end'])]
    originals=reader.auditor_filing(filing)
    xml=[s for s in originals if s['raw_blob']['media_type']=='application/xml']
    _need(len(xml)==1 and original, 'NORMAL_COMPANYFACTS_PRIOR_REVENUE_ORIGINAL_XML_OR_FACT_MISSING')
    annual={'company_id':prepared['company_id'],'entity':prepared['entity'],'filing':filing,
        'table_input':{'target_period':annual_period(raw=xml[0]['raw_bytes'],cik=prepared['entity'],filing=filing)}}
    native=native_income_reports(xml[0],annual,['us-gaap:'+concept])
    native=[r for r in native if (r['period_start'],r['period_end'])==(period['period_start'],period['period_end'])]
    _need(all(any(Decimal(r['value'])==Decimal(c['value']) for r in native) for c in original),
          'NORMAL_COMPANYFACTS_PRIOR_REVENUE_ORIGINAL_XML_DIFFERS')
    allowed={c['verified_claim_id'] for c in original}
    admitted=[c for c in claims if c['locator']['concept'] not in concepts
        or (c['locator']['period_start'],c['locator']['period_end'])!=(period['period_start'],period['period_end'])
        or c['verified_claim_id'] in allowed]
    return admitted, {'method':'CURRENT_COMPARATIVE_TOTAL_ORIGINAL_PRIOR_VALUE',
        'status':'REPORTED_COMPARATIVE_TOTAL_WITH_ORIGINAL_VALUE','complete_scope_proven':True,
        'original_prior_statement_scope_proven':False,'current_comparative_scope_proven':True,
        'original_value_retained':True,'filing':filing,'actual_period':period,
        'original_claim_ids':sorted(allowed),'original_xml_reports':native,'comparative_reports':matched}


def resolve_ordinary_companyfacts_metrics(*, repo_root: Path, company_id: str, rules_root=None,
                                         validate_revenue_scope=False, allow_single_revenue_line=False):
    """Resolve all eleven catalog Company Facts metrics from saved originals.

    Current-only metrics can succeed when a required prior source for another
    metric is unavailable. No caller period, answer, filing or proof is accepted.
    """
    _need(type(validate_revenue_scope) is bool and type(allow_single_revenue_line) is bool
          and (not allow_single_revenue_line or validate_revenue_scope),
          'NORMAL_COMPANYFACTS_REVENUE_OPTION_INVALID')
    rules = repo_root if rules_root is None else Path(rules_root)
    authority = _authority(rules)
    catalog = _load_deterministic_catalog(repo_root=rules)
    routes = {key:value for key,value in catalog["metrics"].items() if value["adapter_id"] == "companyfacts"}
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id,
        **({} if rules_root is None else {'ordinary_registered':True}))
    verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    registry = next(r for r in _registry_rows(repo_root=repo_root) if r["company_id"] == company_id)
    if rules_root is not None:
        rule_registry=next(r for r in _registry_rows(repo_root=rules) if r['company_id']==company_id)
        _need(registry==rule_registry,'NORMAL_COMPANYFACTS_SOURCE_SUBJECT_REGISTRY_CHANGED')
    traits = repository_company_traits(repo_root=rules, company_id=company_id)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])), role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    concepts = sorted({concept for route in routes.values() for branch in route["branches"]
                       for component in branch["components"] for concept in component["approved_concepts"]})
    sources, claims_by_role = [], {}
    source, claims_by_role["current"] = _filing_source(reader, prepared, prepared["filing"], inventory, concepts)
    sources.append({**source, "accession_role":"current"})
    periods, filings = {"current":period, "prior":None}, {"current":prepared["filing"], "prior":None}
    prior_error = None
    amendment_input = None;instant_amendment_input = None;common_error = None
    subject_error = "NORMAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED" if prepared["subject_policy"]["mode"] != "CONTINUOUS_PRIMARY" else None
    if prepared["amendments"]:
        amendment_input = prepare_saved_amendment_input(repo_root=repo_root,company_id=company_id,input_class="ORIGINAL_STATEMENT_VALUES",
            **({} if rules_root is None else {'rules_root':rules_root}))
        _need(amendment_input["prepared_input"] == prepared.get("original_input",prepared), "NORMAL_AMENDMENT_ORIGINAL_INPUT_DIFFERS")
        if amendment_input["decision"] != "INPUT_PROPERTY_PROVEN":
            common_error = "NORMAL_COMPANYFACTS_AMENDMENT_INPUT_SCOPE_UNRESOLVED"
            instant_amendment_input = prepare_instant_balance_amendment_input(repo_root=repo_root,company_id=company_id,
                **({} if rules_root is None else {'rules_root':rules_root}))
            _need(instant_amendment_input["prepared_input"] == prepared.get("original_input",prepared),
                  "NORMAL_INSTANT_AMENDMENT_ORIGINAL_INPUT_DIFFERS")
    needs_prior = any(metric_is_applicable(applicability=route["applicability"], traits=traits)
        and any(c["accession_role"] == "prior" for b in route["branches"] for c in b["components"]) for route in routes.values())
    if needs_prior and not common_error and not subject_error:
        try:
            filing, prior_inventory = _prior_filing(reader, inventory, prepared)
            primary = reader.primary(filing, required=False)
            # A missing saved HTML body can still have its exact accession
            # instance from the authenticated directory index. The same DEI
            # identity/context checks apply to every supplied native document.
            # A failed final GET propagates; it is never replaced by an older
            # success or treated as an optional missing body.
            documents = [primary] if primary else reader.auditor_filing(filing)
            source_periods = [annual_period(raw=s["raw_bytes"], cik=prepared["entity"], filing=filing) for s in documents]
            _need(bool(source_periods) and all(p == source_periods[0] for p in source_periods),
                  "NORMAL_COMPANYFACTS_PRIOR_NATIVE_PERIOD_CONFLICT")
            prior = source_periods[0]
            _need(date.fromisoformat(prior["period_end"]) + timedelta(days=1) == date.fromisoformat(period["period_start"]),
                  "NORMAL_COMPANYFACTS_PRIOR_PERIOD_NOT_ADJACENT")
            source, claims_by_role["prior"] = _filing_source(reader, prepared, filing, prior_inventory, concepts)
            sources.append({**source,"accession_role":"prior"})
            periods["prior"], filings["prior"] = prior, filing
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            prior_error = {"reason":str(error), "error_type":type(error).__name__}
    context = {"repo_root":rules, "deterministic_catalog":catalog,
        "role_context":{(company_id,"companyfacts"):{"sources":sources,"claims_by_accession_role":claims_by_role}},
        "target_periods":{company_id:periods},"targets":{company_id:period},"registry":{company_id:registry},
        "filings_by_company":{company_id:{role:({"accession":filing["accessionNumber"]} if filing else None) for role,filing in filings.items()}}}
    results = {}
    for metric_id, route in routes.items():
        spec = _compiled_deterministic_spec(metric_id=metric_id, route=route)
        instant = route["result_period_role"] == "current_instant"
        scope = {"coverage":"deterministic_source_set", "fiscal_year":period["fiscal_year"]}
        target = {"company_id":company_id,"period_start":period["period_end"] if instant else period["period_start"],
                  "period_end":period["period_end"],"scope":scope,"scope_key":scope_key(scope=scope)}
        detail = None
        graph = {"claims":[],"projection_claims":[],"observation":None}
        if not metric_is_applicable(applicability=route["applicability"], traits=traits):
            result, trace = _manual_result_trace(metric_id=metric_id, company_id=company_id,
                period_start=target["period_start"],period_end=target["period_end"],scope=scope,spec_closure_hash=spec["spec_closure_hash"],
                applicability="N_A_STRUCTURAL",quality="NONE",reason_code="TRAIT_NOT_APPLICABLE",input_observation_ids=[],
                steps=[{"event":"N_A_STRUCTURAL"}],accession=None,entity=None,unit=None)
        else:
            try:
                continuity_guard = (bool(subject_error)
                    and route["continuity_policy"] == "REQUIRE_CONTINUOUS"
                    and registry["entity_continuity_status"] != "continuous")
                if continuity_guard:
                    # This existing catalog guard needs the authenticated
                    # registrant/period, not unproven statement values. Keep
                    # the amendment limitation without inventing a ratio or
                    # relabelling an approved non-comparability outcome as a
                    # missing implementation.
                    graph = _deterministic_metric_graph(context=context, company_id=company_id, metric_id=metric_id)
                    result, trace = graph["result"], graph["trace"]
                    _need(result["quality"] == "NOT_MEANINGFUL"
                          and result["reason_code"] == "ENTITY_CONTINUITY_NOT_COMPARABLE"
                          and result["value"] is None and not graph["claims"] and graph["observation"] is None,
                          "NORMAL_COMPANYFACTS_CONTINUITY_GUARD_CHANGED")
                    detail = {"category":"APPROVED_COMPARABILITY_LIMIT",
                        "reason":"ENTITY_CONTINUITY_NOT_COMPARABLE",
                        "continuity_policy":route["continuity_policy"],
                        "entity_continuity_status":registry["entity_continuity_status"],
                        "subject_policy":prepared["subject_policy"],
                        "statement_values_used":False,"financial_amendment_limitation":common_error,
                        "amendment_input_id":amendment_input["amendment_input_id"] if amendment_input else None}
                else:
                    # The installed catalog already permits these current-instant
                    # metrics across a registrant transition. Their facts still
                    # come exclusively from this primary CIK/current accession;
                    # this does not establish comparable annual performance.
                    instant_scope=(route["continuity_policy"] == "ALLOW" and instant
                        and all(c["accession_role"] == "current" and c["period_role"] == "current_instant"
                                for branch in route["branches"] for c in branch["components"]))
                    _need(not subject_error or instant_scope, subject_error)
                    limited_amendment=(instant_scope and instant_amendment_input is not None
                        and metric_id in instant_amendment_input["metric_ids"]
                        and instant_amendment_input["decision"] == "INPUT_PROPERTY_PROVEN")
                    _need(not common_error or limited_amendment, common_error)
                    requires_prior = any(c["accession_role"] == "prior" for b in route["branches"] for c in b["components"])
                    _need(not requires_prior or prior_error is None, (prior_error or {}).get("reason"))
                    graph_context = context
                    revenue_scopes = None
                    if metric_id == 'B02' and validate_revenue_scope:
                        income_concepts = sorted({c for b in route['branches'] for component in b['components']
                                                  for c in component['approved_concepts']})
                        admitted, revenue_scopes = {}, {}
                        for role in ('current','prior'):
                            admitted[role], revenue_scopes[role] = _original_revenue_claims(
                                reader=reader, prepared=prepared, filing=filings[role], period=periods[role],
                                claims=claims_by_role[role], concepts=income_concepts,
                                allow_single_revenue_line=allow_single_revenue_line,
                                current_scope=revenue_scopes.get('current'), current_filing=filings['current'],
                                current_claims=claims_by_role['current'])
                        graph_context = {**context, 'role_context':{(company_id,'companyfacts'):
                            {'sources':sources,'claims_by_accession_role':admitted}}}
                    graph = _deterministic_metric_graph(context=graph_context, company_id=company_id, metric_id=metric_id)
                    if metric_id == "B02":
                        problem, bridged = paired_measure_problem(
                            route=route, claims=graph["claims"],
                            current_claims=claims_by_role["current"],
                            accessions={"current": prepared["filing"]["accessionNumber"],
                                        "prior": (filings["prior"] or {}).get("accessionNumber")})
                        if problem is not None:
                            graph = {"claims": [], "projection_claims": [], "observation": None}
                            detail = {"category": "MEASURE_NOT_COMPARABLE", **problem}
                            result, trace = withheld_metric_result(
                                compiled_spec=spec, target=target,
                                reason_code=PAIRED_MEASURE_REASON)
                        else:
                            result, trace = graph["result"], graph["trace"]
                            if bridged:
                                detail = {"paired_measure_bridge": bridged}
                            if revenue_scopes is not None:
                                detail = {**(detail or {}), 'paired_revenue_scopes':revenue_scopes}
                    else:
                        result, trace = graph["result"], graph["trace"]
                    if subject_error or limited_amendment:
                        detail={"subject_scope":"CURRENT_PRIMARY_CIK_AND_CURRENT_INSTANT_ONLY",
                                "annual_continuity_proven":False,
                                "instant_amendment_input_id":instant_amendment_input["instant_input_id"] if limited_amendment else None}
            except (*_SOURCE_ERRORS, NormalCompanyfactsError, DecimalException) as error:
                detail = {"reason":str(error),"error_type":type(error).__name__,
                          "category":"SOURCE_OR_IMPLEMENTATION_UNRESOLVED"}
                graph = {"claims":[],"projection_claims":[],"observation":None}
                result, trace = withheld_metric_result(compiled_spec=spec,target=target,reason_code="NORMAL_COMPANYFACTS_ROUTE_UNRESOLVED")
        observations = [graph["observation"]] if graph["observation"] else []
        results[metric_id] = {"metric_id":metric_id,"compiled_spec":spec,"target":target,
            "selection":detail,"claims":graph["claims"],"projection_claims":graph["projection_claims"],
            "observations":observations,"result":result,"trace":trace,"records":[*observations,trace,result]}
    proofs = list({content_hash(value=p):p for p in [*prepared["source_proofs"],*[s["proof"] for s in reader.proofs.values()]]}.values())
    if amendment_input is not None:
        proofs = list({content_hash(value=p):p for p in [*proofs,*amendment_input["source_proofs"]]}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list(reader.records.values())
    if amendment_input is not None:
        source_records = list({content_hash(value=r):r for r in [*source_records,*amendment_input["source_records"]]}.values())
    body = {"record_type":"NORMAL_COMPANYFACTS_NATIVE_RESULTS","company_id":company_id,
        "prepared_input":prepared,"filings":filings,"periods":periods,"prior_error":prior_error,
        "authority_file_hashes":authority,"source_records":source_records,"amendment_input":amendment_input,
        "instant_amendment_input":instant_amendment_input,"source_proofs":proofs,
        "source_admission":admission,"source_sets":[s["manifest"] for s in sources],"claims_by_accession_role":claims_by_role,
        "failed_source_attempts":list(reader.failed_attempts.values()),"metrics":results,
        "resolver_sha256":sha256_file(path=Path(__file__)),"calls":{"provider":0,"paid":0,"sec":0},
        "native_run_status":"NOT_CREATED","current_latest_verified":False,"production_authorized":False}
    body = exact_json_value(body)
    return {**body,"component_id":content_hash(value=body)}


def verify_ordinary_companyfacts_metrics(*, candidate, repo_root: Path, company_id: str):
    rebuilt = resolve_ordinary_companyfacts_metrics(repo_root=repo_root, company_id=company_id)
    _need(candidate == rebuilt, "NORMAL_COMPANYFACTS_SOURCE_REPLAY_CHANGED")
    return rebuilt
