"""The reviewed Ford introduction counterexample, derived in memory only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import sha256_bytes, strict_json_file
from vnext.normal_candidates import _prepare_b06
from vnext.ordinary_special_debt_scope import inspect_special_scope, POLICY_PATH
from vnext.composite_scope import index_source_structure

source = Path(sys.argv[1])
started = time.monotonic()
prepared = _prepare_b06(repo_root=source, company_id='ford_motor_company')
annual = prepared['input_binding']['prepared_annual_input']
def inspect(primary):
    return inspect_special_scope(primary=primary, xml=prepared['xml'], annual=annual,
        financial_institution=False, rules=strict_json_file(path=source / POLICY_PATH),
        reported_relations=True)
original = inspect(prepared['primary'])
assert original['lease_inclusion']['status'] == 'REPORTED_INCLUDED'
table_id = original['lease_inclusion']['relationships'][0]['evidence'][0]['table_id']
raw = prepared['primary']['raw_bytes']
structure = index_source_structure(source_bytes=raw)
order = int(table_id.split('_')[1]) - 1
selected = [t for t in structure['tables'] if t['table_order'] == order]
assert len(selected) == 1
start = selected[0]['start_byte']
sentence = b'<p>Euro-denominated debt is translated into U.S. dollars for presentation.</p>'
derived = raw[:start] + sentence + raw[start:]
primary = deepcopy(prepared['primary'])
primary['raw_bytes'] = derived
primary['source_reference']['raw_asset_id'] = 'sha256:' + sha256_bytes(content=derived)
result = inspect(primary)
assert result['lease_inclusion']['status'] == 'REPORTED_INCLUDED'
assert result['lease_inclusion']['additional_debt_amount'] == '0'
assert result['reported_subtotal'] == original['reported_subtotal'] == '21919000000'
assert result['definition_complete'] is False and result['ratio'] is None
caption = b'<caption>Amounts (in \xe2\x82\xac)</caption>'
tag_end = raw.index(b'>', start) + 1
foreign_bytes = raw[:tag_end] + caption + raw[tag_end:]
foreign = deepcopy(prepared['primary'])
foreign['raw_bytes'] = foreign_bytes
foreign['source_reference']['raw_asset_id'] = 'sha256:' + sha256_bytes(content=foreign_bytes)
conflict = inspect(foreign)
assert conflict['lease_inclusion']['status'] == 'UNRESOLVED'
assert conflict['lease_inclusion']['additional_debt_amount'] is None
print(json.dumps({'seconds': time.monotonic() - started, 'code_root': str(ROOT),
    'source_root': str(source.resolve()), 'source_kind': 'MEMORY_DERIVED_TEST_ONLY',
    'original_primary_sha256': sha256_bytes(content=raw),
    'derived_primary_sha256': sha256_bytes(content=derived),
    'foreign_caption_primary_sha256': sha256_bytes(content=foreign_bytes),
    'foreign_caption_relation': conflict['lease_inclusion']['status'],
    'table_id': table_id, 'insertion_byte': start,
    'original_relation': original['lease_inclusion']['status'],
    'derived_relation': result['lease_inclusion']['status'], 'additional_debt_amount': '0',
    'complete_B06': False, 'ratio': None, 'new_calls': [0, 0, 0]}, indent=2))
