"""One actual ordinary JPM source preparation and independent offline replay.

Full material stays in an explicit private development output, not a source
package. No response, selector, provider or native Result is consumed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
import time

from vnext.c02_table_context_417ccfb7 import (
    PROVIDER_COMMIT, PROVIDER_PATH, assert_matches, expanded_view, wire)
from vnext.c02_table_development_input import prepare_ordinary_table_development_input

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blocked(*args, **kwargs):
    raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')


def artifacts(result):
    return {'raw-source.html': result['raw_source'],
            'document.json': wire(result['document']),
            'table-grid.json': wire(result['table_grid']),
            'view.json': wire(result['view']),
            'request-body.json': result['request_body'],
            'input-binding.json': wire(result['input_binding']),
            'source-reference.json': wire(result['source_reference']),
            'raw-blob.json': wire(result['raw_blob']),
            'context-measurement.json': wire(result['measurement'])}


def run(mode, output, base_head):
    import subprocess
    socket.socket = blocked
    socket.create_connection = blocked
    subprocess.Popen = blocked
    output = output.resolve()
    assert not output.is_relative_to(ROOT) and not ROOT.is_relative_to(output)
    assert not output.is_relative_to(Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13'))
    template_path = ROOT / 'docs/evidence/issue28_continuous/c02-model-input-pilot-20261003/prompt.txt'
    template = template_path.read_text()
    task = template[template.index('Extract the registrant'):]
    start = time.monotonic()
    result = prepare_ordinary_table_development_input(
        data_root=ROOT, company_id='jpmorgan_chase', task_text=task)
    elapsed = round(time.monotonic() - start, 3)
    content = artifacts(result)
    if mode == 'prepare':
        output.mkdir(parents=True, exist_ok=False)
        for name, raw in content.items():
            (output / name).write_bytes(raw)
    else:
        for name, raw in content.items():
            assert sha((output / name).read_bytes()) == sha(raw), name
    assert_matches(result['view'], result['document'], result['table_grid'])
    blocks, tables = expanded_view(result['view'])
    # Independent-source leads from our previous original reading, not the
    # provider's FY2021 table id/expected answer. Print actual rows for reading.
    selected_tables = []
    for table in tables:
        if any(any('James Dimon' in v[0] or 'Stock Committee' in v[0]
                   or 'Executive Committee' in v[0] for v in row) for row in table['cells']):
            selected_tables.append(table)
    named_blocks = []
    for i in [766, 767, 1244, 1245]:
        b = result['document']['blocks'][i]
        raw = result['raw_source'][b['raw_start_byte']:b['raw_end_byte']]
        assert sha(raw) == b['raw_span_sha256']
        named_blocks.append({**b, 'raw_utf8': raw.decode('utf-8')})
    observed = {}
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).resolve().is_relative_to(ROOT) and path.endswith('.py'):
            p = Path(path).resolve()
            observed[str(p.relative_to(ROOT))] = sha(p.read_bytes())
    metadata = {'record_type': 'ISSUE_28_C02_TABLE_INPUT_RECEPTION_CHECK',
        'base_head': base_head, 'tested_uncommitted_paths': [
            'scripts/vnext/c02_table_context_417ccfb7.py',
            'scripts/vnext/c02_table_development_input.py'],
        'code_root': str(ROOT), 'source_data_root': str(ROOT), 'output_root': str(output),
        'provider_commit': PROVIDER_COMMIT, 'provider_path': PROVIDER_PATH,
        'ordinary_binding_id': result['input_binding']['input_binding_id'],
        'source_id': result['source_reference']['source_reference_id'],
        'raw_id': result['document']['raw_asset_id'],
        'document_id': result['document']['text_document_id'],
        'filing': result['document']['source_filing'], 'blocks': len(blocks),
        'tables': len(tables), 'cells': sum(len(r) for t in tables for r in t['cells']),
        'artifacts': {name: sha(raw) for name, raw in content.items()},
        'observed_code_dependencies': observed, 'task_sha256': sha(task.encode()),
        'request_context': result['measurement'], 'seconds': elapsed,
        'block_and_expanded_text_header_grid_equal': True,
        'full_raw_grid_roundtrip_claimed': False,
        'model_answer_tested': False, 'native_or_semantic_acceptance': False,
        'old_c02_batch_reopened': False, 'business_calls': [0, 0, 0]}
    if mode == 'prepare':
        (HERE / 'actual-input-check.json').write_bytes(wire(metadata))
        (output / 'metadata.json').write_bytes(wire(metadata))
        (HERE / 'original-boundary-readings.json').write_bytes(wire({
            'raw_id': metadata['raw_id'], 'filing': metadata['filing'],
            'blocks': named_blocks, 'tables': selected_tables,
            'scope': 'Named current identity/committee boundaries only; not whole document acceptance.'}))
    else:
        expected = json.loads((output / 'metadata.json').read_bytes())
        assert expected['observed_code_dependencies'] == observed
        (HERE / 'independent-process-replay.json').write_bytes(wire(metadata))
    print(json.dumps({k: metadata[k] for k in ['base_head', 'raw_id', 'blocks', 'tables',
        'cells', 'seconds', 'block_and_expanded_text_header_grid_equal', 'business_calls']}))
    print(json.dumps({'input_tokens': result['measurement']['input_tokens'],
                      'context_tokens': result['measurement']['context_tokens'],
                      'fits': result['measurement']['fits']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['prepare', 'replay'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-head', required=True)
    a = parser.parse_args()
    run(a.mode, a.output, a.base_head)
