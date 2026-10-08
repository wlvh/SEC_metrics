"""Package the executor's limited, already-read source reference.

These judgments are development documentation, never runtime operands.
Only source byte locators, native identities and table grids are computed.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(packet, capture, out, prior_reference=None):
    if out.exists():
        raise FileExistsError('Use a fresh output file; preserve earlier references')
    document = json.loads((packet / 'document.json').read_bytes())
    grid = json.loads((packet / 'table-grid.json').read_bytes())
    native = json.loads((packet / 'native-current-financing-facts.json').read_bytes())
    metadata = json.loads((packet / 'metadata.json').read_bytes())
    raw = (capture / 'primary.bin').read_bytes()
    assert sha(raw) == metadata['raw_sha256']['primary']
    assert document['period_end'] == '2025-02-01'
    statements = [
        {'id':'R01', 'blocks':[568], 'statement':'The ABL facility limit is USD 3,000 million. USD 144 million standby letters of credit reduce borrowing capacity to USD 2,856 million. A further USD 397 million inventory borrowing-base restriction reduces borrowing availability to USD 2,459 million. Capacity and availability are distinct; neither is a borrowed balance.'},
        {'id':'R02', 'blocks':[590,1338], 'statement':'The Company borrowed and repaid USD 301 million under the revolving ABL facility during FY2024. No ABL borrowings were outstanding at February 1, 2025 or February 3, 2024. The flow is not an ending liability.'},
        {'id':'R03', 'blocks':[1340], 'statement':'A separate bank credit agreement, amended March 22, 2023, provides for revolving borrowings and letters of credit up to USD 1 million as literally printed. No revolving loans were outstanding at either stated fiscal-year end. Do not combine its limit with the ABL facility or silently correct the printed limit.'},
        {'id':'R04', 'blocks':[1344], 'statement':'Other standby letters of credit are USD 144 million at February 1, 2025 and USD 148 million at February 3, 2024. Note 6 alone states these balances; the capacity relationship is in MD&A B568.'},
        {'id':'R05', 'blocks':[592,1183,1184,1185,1186,1187,1188,1189,1190,1191,1192,1193,1194,1195,1196,1197,1198], 'statement':'Finance-lease future payments total USD 23 million; less USD 8 million interest gives USD 15 million recognized lease liabilities. The MD&A USD 23 million financing obligation is future payments, not an additional current carrying liability.'},
        {'id':'R06', 'blocks':[1145,1146,1147,1148,1149,1154,1155,1156,1158,1159,1163], 'statement':'Current finance-lease liabilities are USD 2 million in accounts payable/accrued liabilities and noncurrent finance-lease liabilities USD 13 million in long-term lease liabilities. USD 1 million non-lease components are included in the noncurrent reported finance liability, not separately added.'},
        {'id':'R07', 'blocks':[575,1761,1762], 'statement':'USD 2,900 million purchase commitments primarily concern merchandise and other goods/services, mainly due within one year. The source says liabilities are recorded when goods are received or services rendered. This commitment total is not an additional proved borrowing balance.'},
        {'id':'R08', 'blocks':list(range(1399,1416)), 'statement':'Note 7 separately reports USD 48 million accrued interest within accounts payable and accrued liabilities at February 1, 2025, versus USD 53 million previously. Official InterestPayableCurrent in HTML/XML supports USD 48 million. This is a recognized current payable, distinct from the MD&A future USD 1.4 billion interest commitments. The earlier financing candidate class omits it; its precise relationship to the approved debt set remains to be demonstrated, not silently added or excluded.'},
    ]
    citations = []
    for n in sorted({n for s in statements for n in s['blocks']}):
        b = document['blocks'][n]
        assert b['block_index'] == n
        assert sha(raw[b['raw_start_byte']:b['raw_end_byte']]) == b['raw_span_sha256']
        citations.append(b)
    pairs = {}
    for ordinal in [550,554,614,617,829,833,835,938,1535]:
        pair = {k:next(r for r in rows if r['ordinal'] == ordinal) for k,rows in native.items()}
        assert pair['primary']['concept_qname'][1].casefold() == pair['xml']['concept_qname'][1]
        # Dimension order differs between HTML and XML. Retain both originals
        # and compare exact resolved QNames as an unordered dimension set.
        def context_identity(c):
            return {**{k:v for k,v in c.items() if k != 'dimensions'},
                'dimensions':sorted((d['dimension_qname'][0], d['dimension_qname'][1],
                    d['member_qname'][0], d['member_qname'][1]) for d in c['dimensions'])}
        assert context_identity(pair['primary']['context']) == context_identity(pair['xml']['context'])
        assert pair['primary']['declared_unit'] == pair['xml']['declared_unit']
        if ordinal in [829,833]:
            assert pair['primary']['source_text'] == 'no'
            assert pair['primary']['format_qname'] == ['http://www.xbrl.org/inlineXBRL/transformation/2020-02-12','fixed-zero']
            assert pair['xml']['normalized_source_value'] == '0'
            assert pair['primary']['normalization_issue'] == 'C03_ZERO_TRANSFORM_TEXT_CONFLICT'
        else:
            assert pair['primary']['normalized_source_value'] == pair['xml']['normalized_source_value']
        pairs[str(ordinal)] = pair
    tables = [t for t in grid['tables'] if t['table_id'] in {'table_000055','table_000060'}]
    assert len(tables) == 2
    result = {
        'record_type':'ISSUE47_B06_EXECUTOR_LIMITED_ORIGINAL_REFERENCE',
        'source_packet_metadata':metadata,
        'reading_scope':{'md_and_a_blocks':[[560,597]], 'debt_note_blocks':[[1335,1347]],
            'accrued_liabilities_blocks':[[1399,1415]],
            'lease_classification_and_maturity_blocks':[[1145,1165],[1183,1202]],
            'purchase_commitments_blocks':[[1761,1762]],
            'all_2140_blocks_semantically_read':False,
            'all_current_candidates_per_source_semantically_classified':False,
            'all_media_interpreted':False},
        'reference_statements':statements, 'raw_block_citations':citations,
        'complete_necessary_lease_grids':tables, 'native_source_pairs':pairs,
        'arithmetic_usd_millions':{'capacity':'3000 - 144 = 2856',
            'availability':'2856 - 397 = 2459', 'lease_carrying':'23 - 8 = 2 + 13 = 15'},
        'existing_borrowing_component_reference':'../bond-sections/source-probe-summary.json',
        'full_b06_complete':False, 'automatic_business_completion':False,
        'provider_trial':False, 'runtime_wired':False, 'calls':[0,0,0],
        'new_runs':0, 'new_acceptances':0, 'production_authorized':False,
        'limitation':'This is a limited executor reference, not an exhaustive fact inventory or independent input-only response. The manual operands in the earlier downstream diagnostic never enter the runtime.'}
    if prior_reference is not None:
        prior = json.loads(prior_reference.read_bytes())
        assert prior['source_packet_metadata']['raw_sha256'] == metadata['raw_sha256']
        assert prior['reference_statements'] == statements[:-1]
        old_blocks = {b['block_index']:b for b in prior['raw_block_citations']}
        new_blocks = {b['block_index']:b for b in citations}
        assert all(new_blocks[n] == b for n,b in old_blocks.items())
        assert all(pairs[n] == p for n,p in prior['native_source_pairs'].items())
        result = {k:v for k,v in result.items() if k not in {'reference_statements',
            'raw_block_citations','complete_necessary_lease_grids','native_source_pairs'}}
        result.update({'incremental_reference':True,
            'base_reference':{'file':prior_reference.name,'sha256':sha(prior_reference.read_bytes()),
                'unchanged_statements':len(statements)-1,'unchanged_citations':len(old_blocks),
                'unchanged_native_pairs':len(prior['native_source_pairs'])},
            'reference_statements':statements[-1:],
            'raw_block_citations':[b for b in citations if b['block_index'] not in old_blocks],
            'native_source_pairs':{n:p for n,p in pairs.items() if n not in prior['native_source_pairs']},
            'combined_reference_totals':{'statements':len(statements),'source_citations':len(citations),'native_pairs':len(pairs)}})
    out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'statements':len(statements),'source_citations':len(citations),'native_pairs':len(pairs),'complete_b06':False,'calls':[0,0,0]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--prior-reference',type=Path)
    a = parser.parse_args()
    build(a.packet,a.capture,a.out,a.prior_reference)
