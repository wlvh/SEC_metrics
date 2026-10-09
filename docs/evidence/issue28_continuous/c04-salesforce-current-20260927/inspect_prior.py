"""Identify the exact saved-source C04 prior URL mismatch without changing it."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from sec_urls import accession_document_url
from vnext.normal_governance_input import prepare_saved_governance_input

DATA = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
base = prepare_saved_governance_input(repo_root=DATA, company_id='salesforce')
arguments = base['resolver_inputs']['c04']['arguments']
cik = int(arguments['expected_cik'])
proofs = base['input_binding']['source_proofs']


def summarize(sources):
    result = []
    for source in sources:
        ref = source['source_reference']
        expected = accession_document_url(cik=cik,
            accession=ref['accession'], document_name=ref['document_name'])
        matching = [proof for proof in proofs
            if proof['source_url'] == ref['source_url']
            and proof['accession'] == ref['accession']]
        result.append({'accession': ref['accession'],
            'document_name': ref['document_name'],
            'source_url': ref['source_url'], 'expected_url': expected,
            'same_cik_url': ref['source_url'] == expected,
            'source_reference_id': ref['source_reference_id'],
            'matching_saved_proof_count': len(matching),
            'matching_saved_proof': ({key: matching[0][key] for key in
                ('document_name', 'request_attempt_id', 'content_sha256',
                 'request_locator_kind')} if len(matching) == 1 else None)})
    return result


current = [summarize(sources) for sources in arguments['current_filings']]
prior = ([summarize(sources) for sources in arguments['prior_filings']]
         if arguments.get('prior_filings') else [summarize(arguments['prior_sources'])])
print(json.dumps({'company_id': 'salesforce',
    'expected_cik': arguments['expected_cik'],
    'target_period_end': arguments['target']['period_end'],
    'prior_period_end': arguments['prior_period_end'],
    'current_filings': current, 'prior_filings': prior,
    'read_only': True, 'native_run_created': False,
    'new_provider_paid_sec_calls': [0, 0, 0]}, ensure_ascii=False, indent=2))
