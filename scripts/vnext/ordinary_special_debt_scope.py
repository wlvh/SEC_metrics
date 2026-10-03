"""Read reported bank/industrial balances without promoting a subtotal to B06.

The ordinary current-input and denominator guards run before this adapter.
It reconstructs source scope, roles, amounts and the precise remaining limits;
no historical per-company scope review or supplied number is an input.
"""
from decimal import Decimal
from pathlib import Path
import re

from .b06_disclosure import label
from .calculator import withheld_metric_result
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .governance_signals import _source_value
from .normal_annual_input import _registry_rows, annual_period
from .normal_annual_input_v2 import exact_json_value
from .normal_candidates import _prepare_b06
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .r5_b06_scope import precision_choice
from .specs import compile_spec_file
from .text_results_v2 import _ReportedFactMetadata, _verified_context

POLICY_PATH = 'config/b06_special_scope_v1.json'


def need(condition, reason):
    if not condition:
        raise ValueError('B06_SPECIAL_SCOPE_' + reason)


def native(source, annual):
    raw = source['raw_bytes']
    need(source['source_reference']['raw_asset_id'] == 'sha256:' + sha256_bytes(content=raw)
         and source['source_reference']['accession'] == annual['filing']['accessionNumber'],
         'ORIGINAL_BINDING_CHANGED')
    need(annual_period(raw=raw, cik=annual['entity'], filing=annual['filing'])
         == annual['table_input']['target_period'], 'ANNUAL_IDENTITY_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    meta = _ReportedFactMetadata()
    meta.feed(raw.decode('utf-8-sig')); meta.close()
    need(meta.ordinal == len(parsed.facts), 'NATIVE_STREAM_CHANGED')
    return parsed, meta


def inspect_special_scope(*, primary, xml, annual, financial_institution, rules):
    sources = {'primary': primary, 'xml': xml}
    native_sources = {kind: native(source, annual) for kind, source in sources.items()}
    end = annual['table_input']['target_period']['period_end']
    contexts = native_sources['xml'][0].contexts
    industrial = {tuple(sorted(c['dimensions'].items())) for c in contexts.values()
        if c['period_start'] == c['period_end'] == end and not c['typed_dimension_count']
        and str(int(c['entity_identifier'])) == annual['entity'] and len(c['dimensions']) == 1
        and any(k.split(':')[-1] == rules['industrial_axis']
                and re.fullmatch(rules['industrial_member_pattern'], v.split(':')[-1])
                for k, v in c['dimensions'].items())}
    if not financial_institution and not industrial:
        return None
    need(not (financial_institution and industrial), 'BANK_INDUSTRIAL_SCOPE_CONFLICT')
    need(len(industrial) <= 1, 'INDUSTRIAL_MEMBER_AMBIGUOUS')
    dimensions = {} if financial_institution else dict(next(iter(industrial)))
    scope_class = 'bank_funding' if financial_institution else 'industrial'
    roles = rules['bank_roles' if financial_institution else 'industrial_roles']
    names = {r['concept'].casefold() for r in roles.values()}
    names.update([rules['equity_concept'].casefold(), *[n.casefold() for n in rules['finance_lease_concepts']]])
    reports = {kind: {} for kind in sources}
    for kind, (parsed, meta) in native_sources.items():
        for fact in parsed.facts:
            item = meta.facts[fact['ordinal']]; uri, name = item['concept']
            if name.casefold() not in names:
                continue
            c = parsed.contexts[fact['context_ref']]
            if c['period_start'] != end or c['period_end'] != end or dict(c['dimensions']) != dimensions:
                continue
            need(str(int(c['entity_identifier'])) == annual['entity'] and not c['typed_dimension_count'],
                 'SUBJECT_OR_DIMENSION_CHANGED')
            need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', uri) is not None,
                 'OFFICIAL_CONCEPT_REQUIRED')
            need(meta.units.get(fact['unit_ref']) == {
                'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')], 'divided': False}, 'USD_REQUIRED')
            context_proof = _verified_context(native={**c, 'dimensions': dict(c['dimensions'])}, metadata=meta)
            row = {'concept': name, 'value': _source_value(fact, item), 'unit': 'USD',
                   'ordinal': fact['ordinal'], 'context_ref': fact['context_ref'],
                   'context': {**c, 'dimensions': dict(c['dimensions'])}, 'context_proof': context_proof,
                   'decimals': item['attrs'].get('decimals'), 'source_reference': sources[kind]['source_reference']}
            reports[kind].setdefault(name.casefold(), []).append(row)
    parsed = native_sources['primary'][0]
    index = _InlineTableIndex(primary['raw_bytes'])
    index.feed(primary['raw_bytes'].decode('utf-8-sig')); index.close()
    ordinals = {r['ordinal'] for items in reports['primary'].values() for r in items}
    cells = _fact_cells(index, parsed, ordinals)
    chosen = {}
    for role, definition in roles.items():
        name = definition['concept'].casefold()
        left, right = reports['primary'].get(name, []), reports['xml'].get(name, [])
        need(left and right, 'ROLE_SOURCE_MISSING:' + role)
        selection = precision_choice(left + right)
        need(Decimal(selection['value']) >= 0, 'NEGATIVE_REPORTED_DEBT')
        visible = []
        for row in left:
            if row['ordinal'] not in cells:
                continue
            table, cell = cells[row['ordinal']]
            actual_label = label(table['rows'][cell['origin_row_index']])
            if not re.search(definition['label'], actual_label, re.I):
                continue
            # Some issuers put the entity in a section heading and years in
            # columns. Bind to the nearest dated section, not a label anywhere
            # in the table (which could belong to a different finance scope).
            column_headers = [c for r in table['rows'][:cell['origin_row_index']] for c in r['cells']
                if c['is_origin'] and c['column_index'] <= cell['column_index'] < c['column_index'] + c['colspan']]
            if dimensions:
                member = next(iter(dimensions.values())).split(':')[-1].removesuffix('Member')
                words = re.findall(r'[A-Z][a-z]*|[A-Z]+(?=[A-Z]|$)|[0-9]+', member)
                dated_sections = [r for r in table['rows'][:cell['origin_row_index']]
                    if any(c['is_origin'] and c['text'].strip() == end[:4]
                        and c['column_index'] <= cell['column_index'] < c['column_index'] + c['colspan']
                        for c in r['cells'])]
                section_label = label(dated_sections[-1]) if dated_sections else ''
                need(' '.join(words).casefold() == ' '.join(section_label.split()).casefold(),
                     'INDUSTRIAL_COLUMN_LABEL_NOT_PROVEN')
                column_headers = dated_sections[-1]['cells']
            visible.append({'ordinal': row['ordinal'], 'reported_label': actual_label,
                            'column_headers': column_headers, 'cell': cell, 'table': table})
        need(visible, 'REPORTED_ROLE_LABEL_NOT_PROVEN:' + role)
        chosen[role] = {'value': selection['value'], 'source_reports': {'primary': left, 'xml': right},
                        'visible_table_evidence': visible}
    subtotal = sum(Decimal(r['value']) for r in chosen.values())
    equity_name = rules['equity_concept'].casefold()
    equity_reports = {kind: reports[kind].get(equity_name, []) for kind in reports}
    equity = None
    if any(equity_reports.values()):
        need(all(equity_reports.values()), 'EQUITY_PRIMARY_XML_MISSING')
        equity = precision_choice(equity_reports['primary'] + equity_reports['xml'])['value']
    limitations = (['BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED'] if financial_institution
                  else ['INDUSTRIAL_ATTRIBUTABLE_EQUITY_NOT_ESTABLISHED'] if equity is None
                  else ['INDUSTRIAL_DEBT_SET_COMPLETENESS_NOT_ESTABLISHED'])
    body = exact_json_value({'record_type': 'ORDINARY_B06_SPECIAL_SCOPE_SOURCE', 'scope_class': scope_class,
        'company_id': annual['company_id'], 'entity': annual['entity'], 'accession': annual['filing']['accessionNumber'],
        'period_end': end, 'dimensions': dimensions, 'reported_components': chosen,
        'reported_subtotal': str(subtotal), 'subtotal_is_complete_B06': False,
        'same_scope_attributable_equity': equity, 'equity_reports': equity_reports,
        'native_finance_lease_reports': {kind: {n: rows for n, rows in values.items()
            if n in {c.casefold() for c in rules['finance_lease_concepts']}} for kind, values in reports.items()},
        'limitations': limitations, 'missing_concept_proves_absence': False,
        'definition_complete': False, 'ratio': None, 'production_authorized': False})
    return {**body, 'scope_source_id': content_hash(value=body)}


def prepare_special_debt_case(*, repo_root: Path, company_id: str):
    rules = strict_json_file(path=repo_root / POLICY_PATH)
    need(rules == strict_json_file(path=ROOT / POLICY_PATH) and rules['full_ratio_enabled'] is False,
         'INSTALLED_RULES_CHANGED')
    preparation = _prepare_b06(repo_root=repo_root, company_id=company_id)
    annual = preparation['input_binding']['prepared_annual_input']
    company = next(c for c in _registry_rows(repo_root=repo_root) if c['company_id'] == company_id)
    inspected = inspect_special_scope(primary=preparation['primary'], xml=preparation['xml'], annual=annual,
        financial_institution=company['industry_profile'] == 'financial_institution', rules=rules)
    if inspected is None:
        return None
    proofs = [*preparation['input_binding']['source_proofs'], *annual['source_proofs']]
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    spec_path = rules['spec_path']; spec = compile_spec_file(path=repo_root / spec_path, dependency_specs={})
    need(spec == compile_spec_file(path=ROOT / spec_path, dependency_specs={}), 'SPEC_CHANGED')
    end = inspected['period_end']; scope = {'entity_scope': 'consolidated'}
    target = {'company_id': company_id, 'period_start': end, 'period_end': end,
              'scope': scope, 'scope_key': content_hash(value=scope)}
    result, trace = withheld_metric_result(compiled_spec=spec, target=target,
        reason_code='B06_SOURCE_RELATIONSHIP_UNRESOLVED')
    records = preparation['records']
    selection = {'classification': 'SOURCE_REBUILT_SPECIAL_SCOPE_LIMITATION',
        'scope_class': inspected['scope_class'], 'reasons': inspected['limitations'],
        'scope_source': inspected, 'reported_subtotal': inspected['reported_subtotal'], 'ratio': None}
    return {'kind': 'STRUCTURED', 'primary_metric_id': 'B06',
        'input_binding': {'original_source_input': preparation['input_binding'], 'scope_source': inspected,
                          'source_proofs': proofs, 'policy_sha256': sha256_file(path=repo_root / POLICY_PATH)},
        'source_records': records, 'references': [r for r in records if r['record_type'] == 'SOURCE_REFERENCE'],
        'source_proofs': proofs, 'admission': admission, 'spec_paths': {'B06': spec_path},
        'compiled_specs': {'B06': spec}, 'target_period': {'fiscal_year': annual['table_input']['target_period']['fiscal_year'],
            'period_start': end, 'period_end': end}, 'expected_records': [*records, trace, result],
        'results': {'B06': result}, 'traces': {'B06': trace}, 'observations': [], 'selection': selection}
