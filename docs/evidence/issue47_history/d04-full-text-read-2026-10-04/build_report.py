"""Bind an actual retrospective reading to unchanged paid source/answer bytes.

Mechanical coverage and identity checks do not produce semantic judgments;
those are the executor's separately saved reading notes. No network or Run.
"""
import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'scripts'))
from vnext.native_unit_index import restore_response


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img':
            a = dict(attrs)
            self.images.append({'src': a.get('src'), 'alt': a.get('alt'),
                                'read': False, 'meaning_inferred': False})


def main(requests, reading_root, out):
    notes = json.loads((HERE / 'reader-notes.json').read_bytes())
    index = json.loads((reading_root / 'index.json').read_bytes())
    packets = {p['file']: p for doc in index for p in doc['packets']}
    read = {p['file']: p for p in notes['read_packets']}
    assert len(read) == len(notes['read_packets']) == len(packets) == 39
    assert set(read) == set(packets)
    native = {r['label']: r for r in notes['native_reads']}
    assert len(native) == len(index) == 4
    documents = []
    units = {}
    for row in index:
        label = row['label']
        doc = json.loads((reading_root / (label + '.json')).read_bytes())
        assert sorted(map(int, doc['blocks'])) == list(range(row['blocks']))
        assert native[label]['facts'] == row['facts']
        assert native[label]['supplement_objects'] == row['supplement_objects']
        assert native[label]['concepts'] == len({(tuple(f['expanded_concept']), f['fact']['tag'])
                                               for f in doc['facts'].values()})
        for packet in row['packets']:
            assert sha(reading_root / packet['file']) == packet['sha256']
            assert read[packet['file']]['blocks'] == [packet['first_block'], packet['last_block']]
        raw = Path(row['raw_path']).read_bytes()
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == row['raw_asset_id']
        for block in doc['blocks'].values():
            assert hashlib.sha256(raw[block['raw_start_byte']:block['raw_end_byte']]).hexdigest() == block['raw_span_sha256']
        mapping = json.loads((reading_root / (label + '-native-text-map.json')).read_bytes())
        assert len(mapping) == row['facts'] + row['supplement_objects']
        parser = Images(); parser.feed(raw.decode('utf-8')); parser.close()
        documents.append({k: row[k] for k in ('label', 'document_id', 'raw_asset_id', 'blocks', 'facts', 'supplement_objects', 'packets')}
                         | {'native_text_map_sha256': sha(reading_root / (label + '-native-text-map.json')),
                            'native_extra_sha256': sha(reading_root / (label + '-native-extra.txt')),
                            'native_concepts_sha256': sha(reading_root / (label + '-native-concepts.txt')),
                            'images': parser.images, 'source_messages': doc['messages']})
        for unit in row['units']:
            assert unit['id'] not in units
            units[unit['id']] = {'document_id': row['document_id'], **unit}
    old = REPO / 'docs/evidence/issue47_history/model-live-round-9a368413'
    limited = json.loads((old / 'd04-limited-two-direction-read.json').read_bytes())
    results = []
    for previous in limited['requests']:
        name = previous['request']
        request_path = requests / (name + '.request.json')
        answer_path = old / 'paid-read-final/answers' / (name + '.json')
        assert sha(request_path) == previous['request_file_sha256']
        assert sha(answer_path) == previous['answer_sha256']
        request = json.loads(request_path.read_bytes())
        _, normalized, _ = restore_response(request=request, raw_response=answer_path.read_bytes())
        answer = json.loads(normalized)
        assert {u['unit_id'] for u in answer['units']} == {u['unit_id'] for u in request['units']}
        findings = []
        for u in answer['units']:
            assert u['reviewed'] is True and u['unresolved'] == []
            assert units[u['unit_id']]['request'] == name
            findings.extend({'unit_id': u['unit_id'], **f} for f in u['findings'])
        expected = previous['model_to_source']
        assert findings == [f['finding'] for f in expected]
        forward = []
        for f in expected:
            forward.append({'finding': f['finding'], 'source_block': f['source_block'],
                            'judgment': 'B340 concerns the registrant streaming business: competitive/cash-intensive investment and conditional profitability, not an explicit entity going-concern assessment. TARGET_REGISTRANT is the contract subject for its own operations; it does not assert parent-company doubt.',
                            'disposition': 'SUPPORTED_IN_COMPLETE_SUPPLIED_TEXT_READING'})
        results.append({k: previous[k] for k in ('request', 'ledger_slot', 'request_digest', 'request_file_sha256', 'answer_sha256')}
                       | {'normalized_answer_sha256': hashlib.sha256(normalized).hexdigest(),
                          'units': [units[u['unit_id']] for u in answer['units']],
                          'model_to_source': forward,
                          'source_to_model': {'required_candidates': previous['source_to_model']['required_candidates'],
                                              'additional_required_candidates_found_in_full_text': [],
                                              'agrees_in_complete_supplied_text': True},
                          'full_filing_content_acceptance': 'NOT_PROVEN'})
    assert len(results) == 16 and len(units) == 74
    report = {'record_type': 'ISSUE_47_D04_RETROSPECTIVE_COMPLETE_SUPPLIED_TEXT_READ',
              'reader': notes['reader'], 'reader_notes_sha256': sha(HERE / 'reader-notes.json'),
              'pre_call_reference_replaced': False,
              'documents': documents, 'requests': results,
              'visible_blocks_read': sum(d['blocks'] for d in documents),
              'native_facts_text_accounted_for': sum(d['facts'] for d in documents),
              'native_supplement_objects_accounted_for': sum(d['supplement_objects'] for d in documents),
              'native_numeric_context_operands_individually_analyzed': False,
              'complete_supplied_visible_text_read': True,
              'complete_filing_all_media_read': False,
              'images_not_read': sum(len(d['images']) for d in documents),
              'limitations': ['Image bytes are absent from the supplied text/native units and have not been read; alt names do not prove image meaning or irrelevance.',
                              'Incorporated external materials outside the fixed saved primary/amendment are not silently included.',
                              'Retrospective executor reading is neither an independent human review nor the original pre-call reference.',
                              'Native concepts/types and nonnumeric prose are covered; numeric literals and context operands are inventoried, not a liquidity/financial-health analysis.',
                              'Mechanical coverage and matching do not turn absence into a numeric no-doubt result.'],
              'acceptance_entries_added': 0, 'native_runs_rewritten': 0,
              'calls': [0, 0, 0], 'production_authorized': False}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: report[k] for k in ('visible_blocks_read', 'native_facts_text_accounted_for', 'native_supplement_objects_accounted_for', 'images_not_read', 'acceptance_entries_added')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--requests', type=Path, required=True)
    p.add_argument('--reading-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    main(a.requests, a.reading_root, a.out)
