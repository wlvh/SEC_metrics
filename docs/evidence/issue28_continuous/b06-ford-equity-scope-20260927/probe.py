"""Read-only census of Ford's saved FY2025 B06 equity facts by XBRL scope.

This is a source-gap probe, not a B06 result or a general SEC no-disclosure
certificate. It never derives industrial equity from consolidated totals.
"""
import json
from collections import Counter
from pathlib import Path

from vnext.canonical import sha256_bytes, strict_json_file
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import ROOT
from vnext.ordinary_source_authority import verify_ordinary_source_proofs
from vnext.ordinary_special_debt_scope import prepare_special_debt_case


INDUSTRIAL_AXIS = 'us-gaap:StatementBusinessSegmentsAxis'
INDUSTRIAL_MEMBER = 'f:CompanyExcludingFordCreditMember'
EQUITY_WORDS = ('equity', 'stockholder', 'netasset')


def census(data_root):
    prepared = _prepare_b06(repo_root=data_root, company_id='ford_motor_company')
    annual = prepared['input_binding']['prepared_annual_input']
    admission = verify_ordinary_source_proofs(
        data_root=data_root, proofs=prepared['input_binding']['source_proofs'])
    end = annual['table_input']['target_period']['period_end']
    issuer = annual['entity']
    sources = {}
    for role in ('primary', 'xml'):
        source = prepared[role]
        raw = source['raw_bytes']
        parsed = parse_accession_xbrl_source(raw_bytes=raw)
        industrial_concepts = Counter()
        industrial_equity = []
        consolidated_equity = []
        for fact in parsed.facts:
            context = parsed.contexts[fact['context_ref']]
            if (context['period_start'] != end or context['period_end'] != end
                    or str(int(context['entity_identifier'])) != issuer):
                continue
            dimensions = context['dimensions']
            name = fact['qualified_name'].split(':')[-1]
            if dimensions.get(INDUSTRIAL_AXIS) == INDUSTRIAL_MEMBER:
                industrial_concepts[name] += 1
                if any(word in name.casefold() for word in EQUITY_WORDS):
                    industrial_equity.append({'concept': fact['qualified_name'],
                        'ordinal': fact['ordinal'],
                        'dimensions': dimensions})
            elif not dimensions and any(word in name.casefold() for word in EQUITY_WORDS):
                consolidated_equity.append({'concept': fact['qualified_name'],
                    'ordinal': fact['ordinal']})
        sources[role] = {
            'source_reference_id': source['source_reference']['source_reference_id'],
            'raw_sha256': sha256_bytes(content=raw), 'raw_size': len(raw),
            'industrial_dimension': {INDUSTRIAL_AXIS: INDUSTRIAL_MEMBER},
            'industrial_concept_counts': dict(sorted(industrial_concepts.items())),
            'industrial_equity_like_facts': industrial_equity,
            'consolidated_equity_like_facts': consolidated_equity,
        }
    case = prepare_special_debt_case(repo_root=data_root,
                                     company_id='ford_motor_company')
    result = case['results']['B06']
    return {
        'record_type': 'ISSUE28_B06_FORD_SAVED_SOURCE_EQUITY_SCOPE_CENSUS',
        'company_id': annual['company_id'], 'accession': annual['filing']['accessionNumber'],
        'period_end': end, 'source_admission_checkpoint_id': admission['checkpoint_id'],
        'source_credit': admission['source_credit'], 'new_business_calls': [0, 0, 0],
        'sources': sources,
        'same_scope_equity_fact_found': any(
            row['industrial_equity_like_facts'] for row in sources.values()),
        'current_case': {
            'classification': case['selection']['classification'],
            'limitations': case['selection']['reasons'],
            'reported_debt_subtotal': case['selection']['reported_subtotal'],
            'result_publication': result['publication'],
            'result_reason_code': result['reason_code'],
            'result_value': result['value'],
        },
        'consolidated_equity_not_industrial_denominator': True,
        'scope_limit': 'Only the admitted saved FY2025 annual primary and accession XML were searched; this does not prove absence in other filings or establish a B06 ratio.',
        'result_or_run_created': False,
    }


if __name__ == '__main__':
    config = strict_json_file(path=ROOT/'config/issue28_continuous_calls_v1.json')
    root = Path(config['budget_root'])/'source-inputs'
    print(json.dumps(census(root), ensure_ascii=False, sort_keys=True, indent=2))
