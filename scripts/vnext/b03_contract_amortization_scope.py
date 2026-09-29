"""Explicit V14 B03 guard for an unselected current amortization category.

The historical B03 Spec and V13 source check retain their original bytes.
A separate, source-reported contract-cost amortization amount makes a composed
D&A result unresolved until its relation to the selected components is proved.
The guard never adds that amount or creates a new metric result.
"""
from decimal import Decimal
from pathlib import Path
import re

from .b03_depreciation_scope import assess_direct_depreciation_scope
from .canonical import sha256_bytes
from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _unreconciled_contract_amortization(*, case, data_root):
    selected = [row for row in case['observations'] if row['metric_id'] == 'B03'
                and row['semantic_role'] in {'depreciation', 'amortization'}]
    if not selected:
        return None
    roles = {row['semantic_role']: row for row in selected}
    _need(len(selected) == 2 and set(roles) == {'depreciation', 'amortization'}
          and roles['depreciation']['source_binding']['concept'] == 'us-gaap:Depreciation'
          and roles['amortization']['source_binding']['concept'] ==
              'us-gaap:AmortizationOfIntangibleAssets',
          'B03_CONTRACT_SCOPE_COMPOSED_SELECTION_CHANGED')
    bindings = [row['source_binding'] for row in selected]
    _need(bindings[0]['accession'] == bindings[1]['accession']
          and bindings[0]['entity'] == bindings[1]['entity'],
          'B03_CONTRACT_SCOPE_COMPOSED_SOURCE_MISMATCH')
    period = case['target_period']
    _need(all(row['period_start'] == period['period_start']
              and row['period_end'] == period['period_end'] for row in selected),
          'B03_CONTRACT_SCOPE_COMPOSED_PERIOD_CHANGED')
    primary = [proof for proof in case['source_proofs']
        if proof.get('accession') == bindings[0]['accession']
        and proof.get('document_name', '').lower().endswith(('.htm', '.html'))]
    _need(len(primary) == 1, 'B03_CONTRACT_SCOPE_PRIMARY_NOT_UNIQUE')
    proof = primary[0]
    raw = resolve_repository_file(repo_root=Path(data_root),
        repo_relative_path=proof['request_repo_relative_path']).read_bytes()
    _need(sha256_bytes(content=raw) == proof['content_sha256'],
          'B03_CONTRACT_SCOPE_PRIMARY_BYTES_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw.decode('utf-8-sig'))
    metadata.close()
    _need(metadata.ordinal == len(parsed.facts),
          'B03_CONTRACT_SCOPE_NATIVE_STREAM_CHANGED')
    amounts = []
    for fact in parsed.facts:
        if fact['qualified_name'] != 'us-gaap:CapitalizedContractCostAmortization':
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['typed_dimension_count']
                or str(int(context['entity_identifier'])) !=
                   str(int(bindings[0]['entity']))):
            continue
        uri, concept = metadata.facts[fact['ordinal']]['concept']
        if (concept != 'CapitalizedContractCostAmortization'
                or not re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', uri)
                or metadata.units.get(fact['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                    'divided': False}):
            continue
        amount = Decimal(str(_numeric_xbrl_value(
            text=fact['text'], scale=fact['scale'], sign=fact['sign'])))
        if amount > 0:
            amounts.append({'ordinal': fact['ordinal'],
                'context_ref': fact['context_ref'],
                'dimensions': dict(context['dimensions']),
                'value_usd': str(amount)})
    if not amounts:
        return None
    return {'status': 'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED',
        'blocked': True, 'primary_source_sha256': proof['content_sha256'],
        'selected_components': {role: roles[role]['value']
                                for role in ('depreciation', 'amortization')},
        'additional_fact_concept': 'us-gaap:CapitalizedContractCostAmortization',
        'additional_facts': amounts,
        'amount_added_or_result_recomputed': False}


def assess_current_b03_scope(*, case, data_root):
    """Keep V13's direct-fact checks; extend only the V14 current path."""
    inherited = assess_direct_depreciation_scope(case=case, data_root=data_root)
    if inherited['blocked'] or inherited['status'] != 'NO_DIRECT_DEPRECIATION_SELECTION':
        return inherited
    return _unreconciled_contract_amortization(
        case=case, data_root=data_root) or inherited
