"""Prepare a source-only development input, without running a selector or AI.

The source proof is from the preserved Enphase install. Only RAW_BLOB and
SOURCE_REFERENCE records are consumed; prior candidates/answers are ignored.
No native result, execution permission or absence conclusion is created.
"""
import argparse
import hashlib
import json
from pathlib import Path

from vnext.text_business_candidates import governance_source_document
from vnext.continuous_request_context import measure_request

SOURCE_SHA = '7bb995ddb80c61a4b25239852efa0a5673d225e17c6125e7005f8ad72e1c6a84'
DEFAULT = Path('/private/tmp/issue28-c02-normal-update-enphase-peer60aa-20261001/metrics/C02/attempts/df1f346bbddd4b4f97974e7ab7e09e48')


def prepare(attempt, output, *, source_sha=SOURCE_SHA, company_id='enphase_energy',
            cik='1463101', issuer_name='Enphase Energy, Inc.', form='DEF 14A',
            filing_date='2026-04-01', expected_blocks=2784):
    references, blobs = {}, {}
    for line in (attempt / 'runs/C02/records.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['record_type'] == 'RAW_BLOB':
            blobs[record['raw_asset_id']] = record
        elif record['record_type'] == 'SOURCE_REFERENCE':
            references[record['source_reference_id']] = record
    reference = next(r for r in references.values()
                     if r['raw_asset_id'] == 'sha256:' + source_sha)
    blob = blobs[reference['raw_asset_id']]
    raw = (attempt / 'data' / blob['storage_uri']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == source_sha
    filing = {'form': form, 'filingDate': filing_date,
              'accessionNumber': reference['accession'],
              'primaryDocument': reference['document_name']}
    document = governance_source_document(raw_bytes=raw, raw_blob=blob,
        source_reference=reference, company_id=company_id, cik=cik,
        filing=filing)
    assert document['source_state'] == 'COMPLETE_LOCAL_DOCUMENT'
    assert len(document['blocks']) == expected_blocks
    output.mkdir(parents=True, exist_ok=False)
    lines, locators = [], []
    for i, block in enumerate(document['blocks']):
        assert block['block_index'] == i
        start, end = block['raw_start_byte'], block['raw_end_byte']
        assert hashlib.sha256(raw[start:end]).hexdigest() == block['raw_span_sha256']
        lines.append('[B{}]\n{}\n'.format(i, block['text']))
        locators.append({k: block[k] for k in ('block_index', 'raw_start_byte',
                         'raw_end_byte', 'raw_span_sha256')})
    text = '\n'.join(lines)
    (output / 'source.txt').write_text(text)
    (output / 'locators.json').write_text(json.dumps(locators, indent=2) + '\n')
    template = (Path(__file__).parent / 'prompt.txt').read_text()
    boundary = template.index('Extract the registrant')
    header = (f'You receive the complete visible source blocks of one {issuer_name}\n'
              f'{form} filed on {filing_date}, accession {reference["accession"]}.\n'
              'It is associated with the FY2025 annual reporting container, not a\n'
              'measurement of the board at 2025-12-31. Source blocks have stable\n'
              '[B<number>] labels in document order.\n\n')
    # Metadata adaptation only; the extraction and output task is unchanged.
    prompt = template if company_id == 'enphase_energy' else header + template[boundary:]
    (output / 'prompt.txt').write_text(prompt)
    request = {'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': (output / 'prompt.txt').read_text()},
        {'role': 'user', 'content': text}],
        'response_format': {'type': 'json_object'}, 'temperature': 0,
        'max_tokens': 4096, 'stream': False, 'thinking': {'type': 'disabled'}}
    wire = json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode()
    (output / 'request-body.json').write_bytes(wire)
    measurement = measure_request(wire, require_reference=True)
    assert measurement['fits']
    (output / 'context-measurement.json').write_text(json.dumps(measurement, indent=2) + '\n')
    metadata = {'record_type': 'DEVELOPMENT_SOURCE_ONLY_C02_INPUT',
        'source_reference': reference, 'raw_blob': blob, 'filing': filing,
        'source_sha256': source_sha, 'source_blocks': len(locators),
        'visible_characters': sum(len(b['text']) for b in document['blocks']),
        'input_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'source_state': document['source_state'],
        'all_blocks_retained': True, 'selector_used': False,
        'prior_answer_included': False, 'new_business_calls': [0, 0, 0],
        'request_context': measurement,
        'no_native_or_production_credit': True}
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.attempt, args.output)
