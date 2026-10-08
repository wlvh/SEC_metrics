"""Bind a manually read B06 reference without producing runtime operands.

The explicit ordinal groups below record the executor's source reading. Code
checks original bytes, finite group coverage, dimension sets and arithmetic;
it neither discovers business meaning nor approves the full debt set.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


TABLES = ['table_000043', 'table_000055', 'table_000056', 'table_000060',
          'table_000067', 'table_000071', 'table_000093', 'table_000095']

# Manual source-based classifications, not a production concept-name classifier.
GROUPS = [
    ('ASSET', [146,158,395,544,546,548,560,563,566,1015,1017], [839,840,846,998,1000,1151,1152,1153,1163,1165,1454,1455],
     'Receivables, ROU assets, their accumulated amortization11, contained nonlease assets and deferred tax assets are asset measurements. Do not net against debt or treat an invested debt instrument as issuer borrowing.'),
    ('EQUITY', [198,267,268,269,270,271,272], [862,863,864,865,866,867,868,869,916,983],
     'StockholdersEquity198 is the same-scope denominator.267–271 are component-axis amounts;272 repeats the4552 total under a different native concept. The source consolidates100%-owned subsidiaries. No extra denominator or borrowing is added.'),
    ('REPORTED_BORROWING_CARRYING', [168,178,701,791,1491], [853,858,1273,1276,1321,1734,1735,1738],
     'Current6 and noncurrent2773 carrying amounts are repeated in balance sheet/debt note.1491 is their2779 total, not a third addend. Native178/791 names mention capital leases, while the source labels Long-Term Debt and Note12 explicitly excludes capitalized leases; concept spelling alone cannot select scope.'),
    ('INSTRUMENT_POOL_BEFORE_UNALLOCATED_ADJUSTMENTS', [699,705,709,713,717,721,725,729,733,737,741,745,749,753,757,761,765,769,773,777,781], list(range(1267,1322))+[600,1738],
     'The full Note6 schedule has the same2025debenture current6/noncurrent0 plus the other instruments. These scheduled instrument amounts sum to2785 before the unallocated cost/premium lines, although many native tags say DebtInstrumentCarryingAmount. Do not allocate global adjustments to instruments without proof or sum the same current occurrence again.'),
    ('BORROWING_ADJUSTMENT', [783,789], [1318,1319,1320,1321,1738],
     '20 cost/discount subtracts and14 premium adds to the pool. They are carrying measurement adjustments, not additional instruments.'),
    ('FINANCE_LEASE_CARRYING_OR_CONTAINED_COMPONENT', [550,554,565,620], [1032,1156,1159,1163,1196,1197,1198],
     'Finance lease15=2current+13noncurrent. The1nonlease liability is already contained in13; it is retained under the approved combined-component policy, not added twice.'),
    ('OPERATING_LEASE_CARRYING_OR_CONTAINED_COMPONENT', [552,556,567,568,621], [1157,1160,1165,1198],
     'Operating3279=365current+2914noncurrent.36/356 nonlease portions are contained components of these operating balances. Their nature is disclosed; they are outside the approved finance-lease debt class.'),
    ('MIXED_LEASE_AGGREGATE', [180,558,622], [859,1156,1157,1159,1160,1161,1198],
     '2927 noncurrent lease liabilities contains13finance+2914operating;3294 total contains15finance+3279operating. These totals are not pure financing balances or new addends.'),
    ('FUTURE_LEASE_PAYMENTS', list(range(596,617)), list(range(1183,1199)),
     'Every finance/operating/total maturity column is a future payment measurement, not the carrying balance.23finance payments less8interest gives15;6327operating less3048 gives3279.'),
    ('LEASE_DISCOUNT_INTEREST', [617,618,619], [1196,1197,1198],
     '8/3048/3056 are the maturity-table discount/interest amounts, not current interest payable or new liabilities.'),
    ('FUTURE_OPERATING_OPTION_AND_UNCOMMENCED_LEASE', [623,624,625,626], [1200,1202],
     'Options/nonlease payment subsets already contained in future operating payments;40legally binding minimums for leases signed but not commenced are excluded from that table. No current finance balance inferred.'),
    ('LEASE_RATE', [632,634], [1207,1208,1209,1210,1211,1212],
     '7.15%/6.80% discount rates are pure-unit assumptions, not USD balances.'),
    ('CONTINGENT_LEASE_GUARANTEE', [642], [1220],
     '158future payments of May/disposed-business leases are guaranteed with remote significant-loss risk and payments from tenants. This does not prove a158recognized financing liability; it also does not erase the guarantee.'),
    ('CURRENT_SCHEDULE_COUPON_AND_YIELD', [698,704,708,711,716,719,723,727,731,736,739,744,747,752,756,760,764,767,772,775,780,785,787], list(range(1267,1321)),
     'Coupons and effective-yield bounds identify the schedule and its adjustments; they are pure-unit rates rather than amounts. Technical dimension names including Secured do not independently override the current source descriptions.'),
    ('EXPLICIT_ZERO_DISTINCT_CREDIT_AGREEMENT', [829,833], [590,1338,1340],
     'Both recognized end borrowings are explicitly no/zero, but ABL and BankCreditAgreement remain distinct. The latter literal limit is1million, not silently1billion. The two contexts differ in dimension order betweenHTML/XML, not dimension identity.'),
    ('STANDBY_LETTER_OF_CREDIT', [835], [568,592,1344],
     '144standby letters reduce ABL capacity; they are not outstanding cash borrowings. The source relationship is retained rather than equating a credit guarantee with a draw.'),
    ('FUTURE_BOND_PRINCIPAL', list(range(841,847)), list(range(1352,1362))+[1738],
     'Future principal maturities6+0+61+176+411+2131=2785. They support the gross pool, not six new liabilities plus existing carrying debt.'),
    ('HISTORICAL_REPAYMENT_TABLE_RATE', [851,858,863,869,877,883,887,894], list(range(1363,1396)),
     'These rates appear in repayment-table labels, including prior-year repayments; the instant native context cannot alone make the old instrument a current outstanding borrowing.'),
    ('AGGREGATE_OR_UNRESOLVED_ACCRUAL', [172,924,942,944], [855,1156,1157,1399,1404,1405,1412,1414,1415],
     '2625 is a mixed AP/accrual total containing the current finance lease2 and accrued interest48 among other obligations. Propertyrelated446 and Other194 are not sufficiently decomposed to prove all their exact debt-set overlaps. Do not exclude the entire total by its AP label or infer property446 contains the finance2 without a row-specific relation.'),
    ('FINANCING_ACCRUAL_SCOPE_UNRESOLVED', [938], [1328,1331,1399,1412,1415,1738],
     '48recognized current interest is separately presented and is not an arithmetic member of the2779bond carrying total. The precise financing source and approved debt-set treatment are still not established; neither addition nor exclusion enters runtime.'),
    ('ORDINARY_TAX_ACCRUAL', [174,934,1081,1083,1085], [856,1410,1499,1501,1502,1503],
     'Current tax/taxesotherthanincome and25tax-related interest/penalties are ordinary tax obligations.5current+20noncurrent=25 follows the source policy recognizing tax interest in income tax expense, not borrowing interest. No unsupported netting bridge to the balance-sheet tax line is made.'),
    ('EMPLOYEE_BENEFIT_OBLIGATION_AND_EQUITY_COMPONENT', [1142,1144,1190,1192], [1537,1543,1544,1546,1547,1548,1551,1552,1553],
     '1391pension benefit obligation versus1881plan assets/funded490asset;425SERP obligation split43current/382noncurrent. Prior-service0/4 are AOCI components. These employee obligations are not borrowed principal merely because discounted; no asset/debt netting.'),
    ('EMPLOYEE_BENEFIT_VALUATION_RATE', [1263,1265,1267,1269,1271,1273], list(range(1574,1580))+[1598],
     'Discount5.52%/5.54%, compensation3%/0 and interestcredit5%/0 are pure-unit plan valuation assumptions, not financing balances.'),
    ('GROSS_AND_FAIR_VALUE_BOND_MEASUREMENT', [1490,1492], [600,1734,1735,1736,1737,1738],
     '2785notional and2467fairvalue are two different measurements of the bond set whose recognized carrying amount is2779. Do not sum or substitute fairvalue for statement carrying.'),
    ('FUTURE_PURCHASE_OBLIGATION', [1535], [1762],
     '2900purchase/service/construction commitments primarily due within1year are recorded as liabilities when goods received/services rendered; the commitment total does not itself prove current borrowed debt.'),
    ('ORDINARY_TRADE_INVOICE_SUPPLIER_PROGRAM', [1546], [1764,1765,1769,1770,1771,1772],
     '116SCF supplier invoices remain merchandise AP and operating payments. Supplier sells receivables; Company is not party to the supplier/lender agreements and Company amounts/terms do not change. This actual relation supports ordinary trade classification, not the wordfinance alone.'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def semantic_context(context):
    """Compare exact expanded names as a set without rewriting source records."""
    result = {k:v for k,v in context.items() if k != 'dimensions'}
    result['dimensions'] = sorted(context['dimensions'], key=lambda d: json.dumps(
        [d['dimension_qname'],d['member_qname']],separators=(',',':')))
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('input','raw','reading-notes','request','out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    document = json.loads((args.input/'document.json').read_text())
    grid = json.loads((args.input/'table-grid.json').read_text())
    facts = json.loads((args.input/'native-current-financing-facts.json').read_text())
    metadata = json.loads((args.input/'metadata.json').read_text())
    notes = json.loads(args.reading_notes.read_text())
    raw = args.raw.read_bytes()
    assert sha(raw) == document['raw_asset_id'][7:]
    blocks = {b['block_index']:b for b in document['blocks']}
    assert set(blocks) == set(range(2140))
    assert notes['complete_supplied_visible_text_read'] is True
    assert [i for p in notes['read_packets'] for i in range(p['blocks'][0],p['blocks'][1]+1)] == list(range(2140))
    for b in blocks.values():
        assert sha(raw[b['raw_start_byte']:b['raw_end_byte']]) == b['raw_span_sha256']
    for name,digest in metadata['artifacts'].items():
        assert sha((args.input/name).read_bytes()) == digest
    primary = {r['ordinal']:r for r in facts['primary']}
    xml = {r['ordinal']:r for r in facts['xml']}
    assert len(primary) == len(xml) == 153 and set(primary) == set(xml)
    covered = [i for _,indexes,_,_ in GROUPS for i in indexes]
    assert len(covered) == len(set(covered)) == 153, ('groupcount',len(covered))
    assert set(covered) == set(primary), ('missing',sorted(set(primary)-set(covered)), 'extra',sorted(set(covered)-set(primary)))
    order_only = []
    for i,p in primary.items():
        x = xml[i]
        assert p['concept_qname'][0] == x['concept_qname'][0]
        assert p['concept_qname'][1].lower() == x['concept_qname'][1]
        assert semantic_context(p['context']) == semantic_context(x['context'])
        assert p['declared_unit'] == x['declared_unit']
        assert p['normalized_source_value'] == x['normalized_source_value']
        assert p['normalization_issue'] is x['normalization_issue'] is None
        if p['context'] != x['context']:
            order_only.append(i)
    def citations(indexes):
        return [blocks[i] for i in indexes]
    classifications = [{'kind':kind,'manual_judgment':statement,'source_blocks':citations(indexes),
                         'native_pairs':[{'primary':primary[i],'xml':xml[i]} for i in ordinals]}
                        for kind,ordinals,indexes,statement in GROUPS]
    references = [{'id':f'B06-FULL-{i+1:02}','statement':n['statement'],
                   'source_blocks':citations(n['blocks'])} for i,n in enumerate(notes['reference_notes'])]
    value = lambda i: Decimal(primary[i]['normalized_source_value'])
    instrument_ordinals = GROUPS[3][1]
    assert sum(value(i) for i in instrument_ordinals) == value(1490)
    assert value(1490)-value(783)+value(789) == value(1491) == value(168)+value(178)
    assert value(620) == value(550)+value(554) == value(614)-value(617)
    assert value(621) == value(552)+value(556) == value(615)-value(618)
    assert value(180) == value(554)+value(556)
    assert value(558) == value(622) == value(620)+value(621)
    assert sum(value(i) for i in range(841,847)) == value(1490)
    assert sum(value(i) for i in range(267,272)) == value(198) == value(272)
    tables = {t['table_id']:t for t in grid['tables']}
    body = {'record_type':'ISSUE47_B06_FULL_SUPPLIED_TEXT_EXECUTOR_REFERENCE',
            'position':'macys:2025-02-01:B06','source_reference':document['source_reference'],
            'request_sha256':sha(args.request.read_bytes()),'raw_sha256':sha(raw),
            'all_2140_supplied_text_blocks_read':True,'all_2140_raw_spans_verified':True,
            'reading_notes':notes,'reference_statements':references,
            'all_153_prepared_candidates_per_source_manually_reviewed':True,
            'candidate_classifications':classifications,'candidate_classification_is_not_exhaustive_native_fact_inventory':True,
            'all_153_html_xml_values_units_semantic_contexts_equal':True,
            'context_dimension_order_only_differences':order_only,
            'necessary_tables_read_and_preserved':[tables[i] for i in TABLES],
            'all_108_tables_read':False,'all_media_interpreted':False,
            'component_arithmetic_checked':True,'manual_operands_enter_runtime':False,
            'unresolved':[
                {'kind':'FINANCING_ACCRUAL','blocks':[1412],'detail':'48interest is separately presented and outside2779 arithmetic; precise underlying financing and debt-set treatment remain unresolved.'},
                {'kind':'ACCRUAL_DECOMPOSITION','blocks':[1405,1414,1156,1157],'detail':'Property446/Other194 exact overlap/nature not completely described. AP includes financelease2; AP label cannot prove blanket exclusion.'},
                {'kind':'SOURCE_WORDING','blocks':[353,600,1738],'detail':'Risk353 literally calls2779aggregateprincipal;600/1738 report2785gross/notional and2779carrying. Retain both wording and corroborated schedule, not silently repair353.'},
                {'kind':'FLOW_RECONCILIATION','blocks':[957,1395,1218],'detail':'CF debt repayment524 vsNote6 repayment522 and separately reportedfinanceleasefinancingcash3; no invented cash-flow bridge. Not added to ending debt.'},
                {'kind':'HISTORICAL_TITLE','blocks':[1342,1956,1960],'detail':'Currentunsecured/exchanged descriptions versus historical secured titles/technicalmembers require their own time/authority; no collateral inference from labels.'},
                {'kind':'MEDIA_AND_INCORPORATED_FILES','detail':'Other100table grids, images, and incorporated agreement/exhibit contents not semantically read through index. Full-all-media/native-union completeness not proven.'},
                {'kind':'INDEPENDENT_METHOD','detail':'No independent B06 input-only answer or authorized target-model run yet. This main-executor reference cannot be treated as independent acceptance.'}],
            'complete_b06_proven':False,'debt_total':None,'ratio':None,
            'native_run_created':False,'new_acceptances':0,'calls':[0,0,0]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'blocks':2140,'candidate_pairs':153,'manual_groups':len(GROUPS),
                      'necessary_tables':len(TABLES),'dimension_order_only':order_only,
                      'debt_total':None,'ratio':None,'calls':[0,0,0]}))


if __name__ == '__main__':
    main()
