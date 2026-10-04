"""Package limited executor judgments; never supply runtime operands."""
import argparse
import hashlib
import json
from pathlib import Path


def build(packet, capture, out):
    if out.exists():
        raise FileExistsError('Preserve previous references')
    document = json.loads((packet / 'document.json').read_bytes())
    raw = (capture / 'primary.bin').read_bytes()
    native = json.loads((packet / 'native-current-financing-facts.json').read_bytes())
    statements = [
        {'id': 'R09', 'blocks': list(range(1267,1322)) + list(range(1399,1416)) + list(range(1734,1740)),
         'statement': 'The company separately reports USD 48 million of accrued interest in Note 7 accounts payable/accrued liabilities. Note 6 bond principal USD 2,785 million minus USD 20 million unamortized issue costs/discount plus USD 14 million premium equals USD 2,779 million carrying borrowing (current USD 6 million plus noncurrent USD 2,773 million), independently corroborated in Note 12. The USD 48 million is not an arithmetic member of that reported USD 2,779 million. This establishes separate presentation and measurement, not an approved instruction to add or exclude interest from B06. Debt-set treatment of a separately recognized financing accrual remains unresolved.'},
        {'id': 'R10', 'blocks': [854] + list(range(1763,1773)),
         'statement': 'Supplier programs leave the Company obligations, amounts and scheduled payment terms unchanged; the Company is not party to the supplier-financial institution agreements. Outstanding USD 116 million is within merchandise accounts payable; USD 112 million beginning plus USD 854 million invoices minus USD 850 million paid equals USD 116 million ending. These source facts support the reported trade-payable nature under the approved ordinary-trade exclusion without conducting an expanded supply-chain reclassification. The taxonomy name alone does not decide nature.'},
        {'id': 'R11', 'blocks': list(range(851,871)),
         'statement': 'The consolidated balance sheet reports USD 4,552 million total shareholders equity and separately presents short-term debt, long-term debt, long-term lease liabilities, merchandise accounts payable, and accounts payable/accrued liabilities. The complete accounts-payable total cannot be added as debt: it contains operating and other reported categories, including the separately identified finance-lease and interest components. The current undimensioned native StockholdersEquity in both sources independently supports USD 4,552 million; a future ratio must use this same scope.'},
    ]
    citations = []
    for n in sorted({n for s in statements for n in s['blocks']}):
        b = document['blocks'][n]
        assert b['block_index'] == n
        assert hashlib.sha256(raw[b['raw_start_byte']:b['raw_end_byte']]).hexdigest() == b['raw_span_sha256']
        citations.append(b)
    pairs = {}
    for ordinal in [168,178,198,783,789,938,1490,1491,1546]:
        pairs[str(ordinal)] = {k:next(r for r in rows if r['ordinal']==ordinal) for k,rows in native.items()}
        assert pairs[str(ordinal)]['primary']['normalized_source_value'] == pairs[str(ordinal)]['xml']['normalized_source_value']
    result = {'record_type':'ISSUE47_B06_EXECUTOR_RELATIONSHIP_REFERENCE_INCREMENT',
        'source_sha256':hashlib.sha256(raw).hexdigest(),
        'base_references':['../b06-older-years/financing-context/executor-source-reference.json',
                           '../b06-older-years/financing-context/executor-source-reference-v3.json'],
        'statements':statements,'raw_block_citations':citations,'native_source_pairs':pairs,
        'reading_scope':'Necessary balance-sheet, Note6 debt schedule, Note7 accrual, Note12 carrying/fair value and Note15 supplier terms. All 152 candidate entries were inspected as source values; this is not a full semantic classification of every document block or medium.',
        'interest_debt_set_disposition':'UNRESOLVED','complete_b06_proven':False,
        'runtime_operands':False,'calls':[0,0,0],'new_runs':0,'new_acceptances':0}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',type=Path,required=True)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.packet,args.capture,args.out)
