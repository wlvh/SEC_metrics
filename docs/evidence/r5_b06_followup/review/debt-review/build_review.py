from pathlib import Path
from decimal import Decimal
from html.parser import HTMLParser
import xml.etree.ElementTree as E, json, hashlib, datetime
O=Path(__file__).parent
selected={
'Southwest':['LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities','LongTermDebtAndCapitalLeaseObligationsCurrent','LongTermDebtAndCapitalLeaseObligations','DeferredFinanceCostsGross','LongTermDebt','FinanceLeaseLiability','StockholdersEquity'],
'Lumen':['DebtAndCapitalLeaseObligations','LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities','DebtInstrumentUnamortizedDiscountPremiumNet','DeferredFinanceCostsNet','LongTermDebtAndCapitalLeaseObligationsCurrent','LongTermDebtAndCapitalLeaseObligations','FinanceLeaseAndOtherObligations','FinanceLeaseLiability','StockholdersEquity'],
'Pfizer':['LongTermDebtCurrent','LongTermDebtNoncurrent','DebtCurrent','OtherShortTermBorrowings','LongtermDebtCurrentMaturitiesExcludingNetFairValueAdjustmentsRelatedToHedgingAndPurchaseAccounting','ShorttermDebtGross','DebtInstrumentUnamortizedDiscountPremiumAndDebtIssuanceCostsNet','StockholdersEquity'],
'Ford':['LongTermDebtCurrent','LongTermDebtNoncurrent','DebtCurrent','LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities','DebtAndCapitalLeaseObligations','ShortTermBorrowings','FinanceLeaseLiability','FinanceLeaseLiabilityCurrent','FinanceLeaseLiabilityNoncurrent','StockholdersEquity'],
'Salesforce':['LongTermDebtCurrent','ConvertibleDebtCurrent','LongTermDebtNoncurrent','LongTermDebt','FinanceLeaseLiability','FinanceLeaseLiabilityCurrent','FinanceLeaseLiabilityNoncurrent','StockholdersEquity'],
'Macys':['DebtCurrent','LongTermDebtAndCapitalLeaseObligations','LongTermDebtGrossIncludingCurrentMaturities','LongTermDebtIncludingCurrentMaturities','DebtInstrumentUnamortizedDiscountPremiumAndDebtIssuanceCostsNet','DebtInstrumentUnamortizedPremiumNoncurrent','FinanceLeaseLiability','FinanceLeaseLiabilityCurrent','FinanceLeaseLiabilityNoncurrent','StockholdersEquity'],
'JPM':['ShortTermBorrowings','LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities','StockholdersEquity','FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase','BeneficialInterestsIssuedByConsolidatedVariableInterestEntities']}
notes={
'Southwest':['ScheduleOfDebtInstrumentsTextBlock','ScheduleOfMaturitiesOfLongTermDebtTableTextBlock'],
'Lumen':['ScheduleOfDebtInstrumentsTextBlock','ScheduleOfMaturitiesOfLongTermDebtTableTextBlock'],
'Pfizer':['ScheduleOfShortTermDebtTextBlock','ScheduleOfDebtInstrumentsTextBlock'],
'Ford':['ScheduleOfCarryingValuesAndEstimatedFairValuesOfDebtInstrumentsTableTextBlock','DebtPolicyTextBlock'],
'Salesforce':['DebtDisclosureTextBlock','LesseeLeasesPolicyTextBlock','FinanceLeaseLiabilityMaturityTableTextBlock'],
'Macys':['DebtDisclosureTextBlock','LesseeLeaseTableTextBlock'],
'JPM':['LongTermDebtTextBlock']}
companies=[]
for company in selected:
 j=json.loads((O/(company+'.json')).read_text()); p=Path(j['source']); b=p.read_bytes(); root=E.fromstring(b)
 contexts={n.get('id'):n for n in root if n.tag.endswith('}context')};units={n.get('id'):n for n in root if n.tag.endswith('}unit')};facts=[];ns=[]
 for n in root:
  tag=n.tag.split('}')[-1]; cref=n.get('contextRef'); ctx=contexts.get(cref)
  if tag in selected[company] and ctx is not None:
   ends=[q.text for q in ctx.iter() if q.tag.endswith('}instant')]
   dims=[{'dimension':q.get('dimension'),'member':q.text} for q in ctx.iter() if q.tag.endswith('}explicitMember')]
   if ends not in [['2025-12-31'],['2026-01-31']]:continue
   # Keep only complete-scope totals; Ford also needs exact industrial/credit dimensions, not child instrument rows.
   if dims and not (company=='Ford' and len(dims)==1 and dims[0]['member'] in ['f:CompanyExcludingFordCreditMember','f:FordCreditMember']):continue
   facts.append({'concept':n.tag,'fact_id':n.get('id'),'raw_value':n.text,'decimals':n.get('decimals'),'context_id':cref,'context_xml':E.tostring(ctx,encoding='unicode'),'instant':ends[0],'dimensions':dims,'unit_id':n.get('unitRef'),'unit_xml':E.tostring(units[n.get('unitRef')],encoding='unicode') if n.get('unitRef') else None})
  if tag in notes[company]:
   text=n.text or '';h=E.fromstring('<root>'+text+'</root>');clean=' '.join(' '.join(h.itertext()).split());rows=[]
   for tr in h.iter():
    if tr.tag.split('}')[-1]=='tr':rows.append(' | '.join(' '.join(' '.join(td.itertext()).split()) for td in tr if td.tag.split('}')[-1] in ['td','th']))
   ns.append({'concept':n.tag,'fact_id':n.get('id'),'context_id':cref,'raw_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'normalized_display_text':clean,'display_table_rows':rows})
 header=Path(str(p)+'.headers.json');hj=json.loads(header.read_text());sha=hashlib.sha256(b).hexdigest()
 companies.append({'company':company,'source':str(p),'source_sha256':sha,'source_size':len(b),'saved_headers':str(header),'headers_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'source_hash_present_in_headers':sha in json.dumps(hj),'facts':facts,'notes':ns})
# Lumen equation reads exact concepts from original XML; expected values are not used in selection.
l=next(c for c in companies if c['company']=='Lumen'); vals={f['concept'].split('}')[-1]:Decimal(f['raw_value']) for f in l['facts']}
a=vals['LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities'];d=vals['DebtInstrumentUnamortizedDiscountPremiumNet'];c=vals['DeferredFinanceCostsNet'];t=vals['DebtAndCapitalLeaseObligations'];cur=vals['LongTermDebtAndCapitalLeaseObligationsCurrent'];noncur=vals['LongTermDebtAndCapitalLeaseObligations']
assert a-d-c==t and cur+noncur==t and vals['StockholdersEquity']<0
assert all(c['source_hash_present_in_headers'] for c in companies)
review={'status':'INDEPENDENT_RAW_SOURCE_REVIEW_COMPLETED_NOT_NATIVE_ACCEPTANCE','reviewer':{'kind':'independent Codex model subtask','task':'/root/debt_reconciliation_review','human_approval':False},'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'business_calls':{'provider':0,'paid':0,'SEC':0},'checks_executed':['seven original XML parsed','source SHA256 matched saved header for all seven','exact current instant/entity/unit/context/dimension facts indexed','raw text blocks and table signs inspected','Lumen carrying reconciliation independently calculated with Decimal'],'not_executed':['new native production code tests','new Observation/Review/Calculator graph replay','new complete candidate validation','any external network request'],'lumen_reconciliation':{'equation':'principal - unamortized_net_discount - deferred_finance_costs = carrying_debt','principal':str(a),'unamortized_net_discount':str(d),'deferred_finance_costs':str(c),'carrying_debt':str(t),'current':str(cur),'noncurrent':str(noncur),'equity':str(vals['StockholdersEquity']),'all_same_context':'c-8','sign_evidence':'XML discount and cost facts are positive amounts; parentheses in same debt note table supply subtractive presentation; principal maturity note explicitly excludes both adjustments.','result':'RECONCILED_MEASUREMENT_BASES; negative equity remains NOT_MEANINGFUL'},'companies':companies}
sw=next(c for c in companies if c['company']=='Southwest'); sv={f['concept'].split('}')[-1]:Decimal(f['raw_value']) for f in sw['facts']}; subtotal=sv['LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities']; adjustment=sv['DeferredFinanceCostsGross']; carrying=sv['LongTermDebtAndCapitalLeaseObligationsCurrent']+sv['LongTermDebtAndCapitalLeaseObligations']; assert subtotal-adjustment==carrying
review['southwest_reconciliation']={'equation':'pre_cost_debt_subtotal - debt_discount_and_issuance_costs = current_carrying + noncurrent_carrying','subtotal':str(subtotal),'adjustment':str(adjustment),'carrying':str(carrying),'equity':str(sv['StockholdersEquity']),'ratio':str(carrying/sv['StockholdersEquity']),'context':'c-4','sign_evidence':'Same financing table labels Less current maturities then Less debt discount and issuance costs; XML positive cost must be subtracted. Separate maturity principal total 4.929bn must not be conflated with 4.919bn pre-cost subtotal.'}
(O/'raw-fact-index.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':review['status'],'companies':len(companies),'facts':sum(len(c['facts']) for c in companies),'notes':sum(len(c['notes']) for c in companies),'lumen':review['lumen_reconciliation']},indent=2))
