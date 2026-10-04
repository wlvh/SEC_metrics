"""Freeze a complete B06 development request from a prepared source-only packet.

No provider transport, source acquisition, model answer, Run or acceptance.
Keep the full packet even when its measured request does not fit the context.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from tools.prepare_c02_table_context import FORMAT, assert_matches, wire
from vnext.canonical import strict_json_file
from vnext.continuous_request_context import measure_request

SOURCE_FILES = {'document.json', 'table-grid.json', 'view.json',
                'native-current-financing-facts.json', 'source-only-package.json',
                'normal-b06-source-binding.json'}

TASK = """Extract a source-supported B06 financing composition for the supplied
registrant and annual filing. The reporting period identifies the target; use
the actual source dates, entities, units and statement carrying measurements.
The approved debt definition is supplied below. It is policy, not an answer.
Read the complete supplied primary text and table layout and reconcile the
relevant native HTML/XML facts. The candidate class is broad but not a proof of
completeness. Concept names and keywords cannot decide debt membership.

Distinguish recognized borrowing/bond/finance-lease carrying liabilities from
credit limits, borrowing capacity, actual availability, letters of credit,
annual draw/repayment flows, future principal/interest/lease payments, assets,
operating obligations, tax/provisions and equity. Retain different agreements
and each instrument's current/noncurrent occurrences. Repeated native facts and
note/balance-sheet presentations are evidence of the same amounts, not adders.
For financing accruals, establish their nature and whether already included in
the reported carrying amount before proposing addition or exclusion. Never
replace this proof with a generic accounts-payable label or a keyword rule.
Reconcile premiums, discounts/costs, leases and combined nonlease components;
do not net an asset or count a future-payment total as a second balance. Preserve
literal surprising limits and uncertainty rather than silently repairing text.

Return one JSON object with:
subject: {company_id, report_end, entity_scope};
components: [{id,label,amount_usd,measurement,period_start,period_end,
  entity_scope,agreement_or_group,debt_treatment,reason,source_blocks,
  native_facts,table_cells}];
relations: [{left_ids,relation,right_ids,reason,source_blocks,table_cells}];
debt: {component_ids,amount_usd,complete,reason};
equity: {amount_usd,entity_scope,source_blocks,native_facts};
ratio: {value,reason};
unresolved: [{issue,source_blocks,native_facts,table_cells}];
coverage: {primary_blocks_read,table_count_read,html_xml_reconciled,
  relevant_uninterpreted_media,limitations}.

amount_usd and ratio value are decimal strings or null; report USD, not source
millions. measurement is carrying_balance, credit_limit, borrowing_capacity,
availability, period_flow, future_payment, expense, rate, asset or other.
debt_treatment is include, already_included, exclude or unresolved. relations
may express sum, difference, contains, disjoint, or different_measurement.
source_blocks are original zero-based B indices. native_facts are
{source_kind,ordinal}; table_cells are {table_id,row,column}. Give short reasons
and cite the evidence that supports each actual relationship. Cite an entire
table by its full row/column range in the reason if a decomposition is needed;
do not enumerate all irrelevant candidates or repeat whole source paragraphs.
Only supply a debt total and ratio when all required classes, overlaps and
relevant coverage are established. Otherwise retain proved components and
specific unresolved issues, with total/ratio null and complete=false. Omission,
a blank cell or a generic absence claim is not zero. Do not assert interpreted
images or full media coverage from a text/header representation.
"""


def request_for(packet, definition):
    """Carry the entire source packet into the user message, without answers."""
    prompt = TASK + '\nApproved definition:\n' + wire(definition).decode() + FORMAT
    return {'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': wire(packet).decode()}],
        'response_format': {'type': 'json_object'}, 'temperature': 0,
        'max_tokens': 4096, 'stream': False, 'thinking': {'type': 'disabled'}}


def load_packet(directory):
    """Check preparation bytes and full block/table equivalence, not admission."""
    metadata = strict_json_file(path=directory / 'metadata.json')
    if set(metadata['artifacts']) != SOURCE_FILES:
        raise ValueError('B06_DEVELOPMENT_ARTIFACT_SET_CHANGED')
    for name, expected in metadata['artifacts'].items():
        if Path(name).name != name:
            raise ValueError('B06_DEVELOPMENT_ARTIFACT_PATH_INVALID')
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('B06_DEVELOPMENT_ARTIFACT_CHANGED:' + name)
    packet = strict_json_file(path=directory / 'source-only-package.json')
    document = strict_json_file(path=directory / 'document.json')
    grid = strict_json_file(path=directory / 'table-grid.json')
    view = strict_json_file(path=directory / 'view.json')
    assert_matches(view, document, grid)
    if (metadata['block_count'] != view['block_count']
            or metadata['table_count'] != len(grid['tables'])
            or metadata['expanded_cells'] != sum(
                t['row_count'] * t['column_count'] for t in grid['tables'])):
        raise ValueError('B06_DEVELOPMENT_SOURCE_COUNTS_CHANGED')
    if (packet['primary_text_and_table_layout'] != view
            or packet['current_potential_financing_native_facts'] != strict_json_file(
                path=directory / 'native-current-financing-facts.json')):
        raise ValueError('B06_DEVELOPMENT_PACKET_CONTENT_CHANGED')
    return packet, metadata


def prepare(directory, out):
    packet, metadata = load_packet(directory)
    definition = strict_json_file(path=REPO / 'config/b06_bond_debt_set_v1.json')
    request = request_for(packet, definition)
    body = wire(request)
    measurement = measure_request(body, require_reference=True)
    out.mkdir(parents=True, exist_ok=False)
    for name, value in [('request-body.json', request),
                        ('context-measurement.json', measurement)]:
        (out / name).write_bytes(wire(value))
    (out / 'prompt.txt').write_text(request['messages'][0]['content'], encoding='utf-8')
    receipt = {'record_type': 'ISSUE47_B06_COMPLETE_REQUEST_DEVELOPMENT',
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'company_id': packet['company_id'], 'report_end': metadata['report_end'],
        'source_packet_sha256': hashlib.sha256(wire(packet)).hexdigest(),
        'source_metadata_sha256': hashlib.sha256((directory / 'metadata.json').read_bytes()).hexdigest(),
        'approved_definition_sha256': hashlib.sha256((REPO / 'config/b06_bond_debt_set_v1.json').read_bytes()).hexdigest(),
        'request_sha256': measurement['request_sha256'], 'input_tokens': measurement['input_tokens'],
        'fits': measurement['fits'], 'source_value_version': metadata.get('source_value_version', 'frozen'),
        'all_prepared_source_data_retained': True, 'source_admission_credit': False,
        'model_answer_tested': False, 'runtime_wired': False, 'complete_b06_proven': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0, 'production_authorized': False}
    (out / 'metadata.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.packet.resolve(), args.out.resolve())
