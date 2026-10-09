"""Read a fixed saved SourceSet through the real public parser, with no network."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.annual_sources import saved_source
from vnext.financial_structured import inspect_inline_financial_claims
from vnext.normal_annual_input import annual_period, NormalAnnualInputError


def run(source_root):
    parameters = json.loads(Path(__file__).with_name('peer-source-parameters.json').read_text())
    bundle = {key: parameters[key] for key in ('metric_id', 'expected_cik', 'target_period',
              'source_reference', 'source_set_manifest', 'inventory_source_reference')}
    source_root = source_root.resolve()
    for reference_name, bytes_name in (('source_reference', 'source_bytes'),
                                        ('inventory_source_reference', 'inventory_bytes')):
        reference = bundle[reference_name]
        item = saved_source(repo_root=source_root, url=reference['source_url'],
                            accession=reference['accession'])
        assert item is not None, reference['source_url']
        raw = item['raw']
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == reference['raw_asset_id']
        bundle[bytes_name] = raw
    start = time.monotonic()
    try:
        annual_period(raw=bundle['source_bytes'], cik=bundle['expected_cik'],
                      filing={'form': '10-K', 'reportDate': bundle['target_period']['period_end']})
    except NormalAnnualInputError as error:
        baseline = str(error)
        assert baseline == 'DEI_MISSING_OR_AMBIGUOUS:DocumentType'
    else:
        raise AssertionError('Expected old default to retain its original release restriction')
    baseline_seconds = time.monotonic() - start
    start = time.monotonic()
    fact = inspect_inline_financial_claims(repo_root=ROOT, **bundle,
                                         dei_release='YEAR_QUARTER_OR_DATE')
    assert fact['outcome'] == 'STRUCTURED_PRIMARY_RESOLVED'
    assert fact['source_set_scope'] == 'NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET'
    assert fact['value'] == '28971000000'
    result = {'code_root': str(ROOT), 'source_root_read_only': str(source_root),
              'source_sha256': hashlib.sha256(bundle['source_bytes']).hexdigest(),
              'source_bytes': len(bundle['source_bytes']), 'baseline_error': baseline,
              'baseline_boundary_seconds': baseline_seconds,
              'explicit_full_component_seconds': time.monotonic() - start,
              'outcome': fact['outcome'], 'value': fact['value'],
              'period': bundle['target_period'], 'selected': fact['selected'],
              'source_set_scope': fact['source_set_scope'], 'new_calls': [0, 0, 0],
              'new_result_run_or_business_acceptance': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')), \
         patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')), \
         patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
        run(args.source_root)
