"""Offline evidence inspection, never a runtime source-role approval table."""
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import socket
import subprocess
import tarfile

from vnext.capacity_semantic_source import prepare_capacity_semantic_source
from vnext.capacity_utilization_source import calculate_source_comparable_pair
from vnext.capacity_semantic_review import validate_response
from vnext.normal_source_authority import ROOT

HERE = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'docs/evidence/issue28_continuous/resume-2026-09-14/b13-complete-source.tar.gz'
# These are audit anchors in already observed originals, never production configuration.
ANCHORS = {'enphase_energy': [282, 809, 883, 899, 1364, 1369, 1560],
           'ford_motor_company': [539, 543, 545, 546, 550, 674, 785, 827, 2547, 3178, 3762]}
summary = {'record_type': 'B13_ORIGINAL_SOURCE_INSPECTION_NOT_ACCEPTANCE',
           'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'source_archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
           'real_calls': [0, 0, 0], 'companies': {}, 'native_result_created': False,
           'complete_semantic_coverage_verified': False, 'numeric_pair_absence_established': False}
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen', side_effect=AssertionError('SEC_FORBIDDEN')), tarfile.open(ARCHIVE) as archive:
    for member in archive.getmembers():
        old = json.load(archive.extractfile(member))
        company = old['company_id']
        current = prepare_capacity_semantic_source(repo_root=ROOT, company_id=company)
        assert current['units'] == old['units'], company + ': original units changed'
        assert current['documents'] == old['documents'], company + ': document metadata changed'
        raw = {}
        for document in current['documents']:
            blob = document['raw_blob']
            content = (ROOT / blob['storage_uri']).read_bytes()
            assert 'sha256:' + hashlib.sha256(content).hexdigest() == blob['raw_asset_id']
            raw[blob['raw_asset_id']] = content
        blocks = [b for u in current['units'] if u['kind'] == 'VISIBLE_TEXT' for b in u['payload']['blocks']]
        rows = []
        inventory = {}
        for u in current['units']:
            if u['kind'] != 'NATIVE_FACTS':
                continue
            for row in u['payload']['facts']:
                f = row['fact']
                if not f['unit_ref']:
                    continue
                definition = u['payload']['units'][f['unit_ref']]
                item = inventory.setdefault(f['unit_ref'], {'definition': definition, 'concepts': {}})
                assert item['definition'] == definition
                concept_key = '|'.join(row['expanded_concept'])
                item['concepts'].setdefault(concept_key, []).append(f['ordinal'])
        try:
            result = calculate_source_comparable_pair(source=current, raw_bytes_by_id=raw)
            quantity = {'status': 'CALCULATOR_RESULT', 'result': result['result']}
        except ValueError as exc:
            quantity = {'status': 'IMPLEMENTATION_OR_SOURCE_RELATION_NOT_ESTABLISHED',
                        'reason': str(exc), 'disclosure_absence_credit': False}
        report = {'company_id': company, 'semantic_source_id': current['semantic_source_id'],
                  'prepared_annual_input_id': current['prepared_annual_input'].get('prepared_input_id'),
                  'period': current['prepared_annual_input']['table_input']['target_period'],
                  'documents': current['documents'], 'all_units_equal_archived_originals': True,
                  'units_by_kind': dict(Counter(u['kind'] for u in current['units'])),
                  'complete_visible_block_count': len(blocks),
                  'source_anchor_blocks': [b for b in blocks if b['block_index'] in ANCHORS[company]],
                  'all_declared_quantity_units_and_facts': inventory,
                  'quantity_reader_actual_result': quantity,
                  'production_authorized': False, 'native_result_created': False}
        (HERE / (company + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        summary['companies'][company] = {k: report[k] for k in ('period', 'units_by_kind',
            'complete_visible_block_count', 'all_units_equal_archived_originals', 'quantity_reader_actual_result')}
    original68 = ROOT / 'docs/evidence/issue28_continuous/b13-source-indexing/original68'
    request = json.loads((original68 / 'semantic-request.json').read_text())
    response = (original68 / 'wire/assistant-output.bin').read_bytes()
    before = {str(p.relative_to(original68)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in original68.rglob('*') if p.is_file()}
    try:
        validate_response(request=request, raw_response=response)
    except ValueError as exc:
        rejected = str(exc)
    else:
        raise AssertionError('original68 business content unexpectedly accepted')
    after = {str(p.relative_to(original68)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in original68.rglob('*') if p.is_file()}
    assert before == after
    terminal = json.loads((original68 / 'terminal.json').read_text())
    assert terminal['status'] == 'SUCCEEDED'
    summary['original68'] = {'historical_terminal': 'SUCCEEDED', 'current_content_rejection': rejected,
                             'all_original_files_unchanged': True, 'original_sha256': before,
                             'usable_result_credit': False}
(HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
