"""Read one saved original and exercise the existing contract-deduction check.

This is a source diagnostic. It creates no observations, Run or Result.
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from vnext.b03_contract_amortization_scope import _visible_revenue_deductions
from vnext.deterministic_router import parse_accession_xbrl_source, _numeric_xbrl_value
from vnext.text_results_v2 import _ReportedFactMetadata, _verified_context
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE, is_fasb_namespace


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--source-root', type=Path, required=True)
    options = args.parse_args()
    started = perf_counter()
    root = Path(__file__).resolve().parents[3]
    old = json.loads((root / 'docs/evidence/issue28_b03_source_candidates_20261008/real-2021.json').read_text())
    reference = old['candidates'][0]['source_reports']['primary'][0]['source_reference']
    sha = reference['raw_asset_id'].removeprefix('sha256:')
    source = options.source_root / 'evidence/request_attempts' / sha[:2] / sha / reference['document_name']
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == sha
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    meta = _ReportedFactMetadata()
    meta.feed(raw.decode('utf-8-sig'))
    meta.close()
    assert meta.ordinal == len(parsed.facts)

    def canonical(qname):
        uri, local = qname
        for taxonomy in ('us-gaap', 'srt'):
            if is_fasb_namespace(uri, taxonomy=taxonomy, namespace_policy=YEAR_OR_DATE_RELEASE):
                return taxonomy + ':' + local
        return '{' + uri + '}' + local

    amounts = []
    for fact in parsed.facts:
        uri, concept = meta.facts[fact['ordinal']]['concept']
        context = parsed.contexts[fact['context_ref']]
        if concept != 'CapitalizedContractCostAmortization':
            continue
        if context['period_start'] != old['period']['period_start'] or context['period_end'] != old['period']['period_end']:
            continue
        assert int(context['entity_identifier']) == 1048286
        assert not context['typed_dimension_count']
        assert is_fasb_namespace(uri, namespace_policy=YEAR_OR_DATE_RELEASE)
        assert meta.units[fact['unit_ref']] == {
            'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')], 'divided': False}
        proof = _verified_context(native={**context, 'dimensions': dict(context['dimensions'])}, metadata=meta)
        amounts.append({'ordinal': fact['ordinal'], 'context_ref': fact['context_ref'],
            'dimensions': dict(context['dimensions']),
            'resolved_dimensions': {canonical(d['dimension_qname']): canonical(d['member_qname']) for d in proof['dimensions']},
            'value_usd': str(_numeric_xbrl_value(text=fact['text'], scale=fact['scale'], sign=fact['sign']))})
    checks = _visible_revenue_deductions(raw=raw, parsed=parsed, amounts=amounts, period=old['period'])
    assert checks and len(checks) == 4
    assert checks[0]['displayed_amounts'] == ['2694', '-75', '2619']
    assert [row['value_usd'] for row in amounts] == ['75000000', '55000000', '20000000', '75000000']
    print(json.dumps({'source_reference': reference, 'actual_period': old['period'],
        'contract_cost_facts': amounts, 'existing_shared_deduction_proofs': checks,
        'full_da_scope_established': False, 'metric_result_created': False,
        'calls': {'sec': 0, 'provider': 0}, 'elapsed_seconds': perf_counter() - started}, indent=2))


if __name__ == '__main__':
    main()
