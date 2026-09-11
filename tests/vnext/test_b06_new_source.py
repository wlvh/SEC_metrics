"""Targeted semantic tests derive TEST_ONLY sources, with fresh identities."""
import copy
from pathlib import Path
from functools import lru_cache
import unittest
from unittest.mock import patch
from vnext import b06_disclosure as d
from vnext.canonical import sha256_bytes
from vnext.annual_input import _saved_source
from vnext.annual_update import _rows
from sec_urls import accession_document_url
from tests.vnext.test_r5_b06_scope import material,ROOT

@lru_cache(maxsize=2)
def development(cid):
    _,x=material(cid)
    url=accession_document_url(cik=int(x['target']['entity']),accession=x['target']['accession'],document_name=x['source']['document_name'].replace('_htm.xml','.htm'))
    _,primary=_saved_source(repo_root=ROOT,rows=_rows(ROOT),url=url,accession=x['target']['accession'])
    return {**x,'primary':primary}


def derived(args,replace):
    """Only semantic test input: no journal enrolment and no real SEC credit."""
    args=copy.deepcopy(args)
    for before,after in replace:
        args['raw']=args['raw'].replace(before,after)
        args['primary']=args['primary'].replace(before,after)
    args['source']['raw_asset_id']='sha256:'+sha256_bytes(content=args['raw'])
    args['source']['source_reference_id']='source:test:'+sha256_bytes(content=args['raw'])
    return args


def zero_supplier_test_source(a):
    import re
    a=copy.deepcopy(a)
    a['raw']=re.sub(rb'(<us-gaap:SupplierFinanceProgramObligationCurrent\b[^>]*>)[^<]+',lambda m:m[1]+b'0',a['raw'])
    a['source']['raw_asset_id']='sha256:'+sha256_bytes(content=a['raw'])
    return a


def run(args,proposal=None):
    if proposal is None:proposal=d.propose(raw=args['raw'],primary=args['primary'],target=args['target'])
    return d.verify(**args,proposal=proposal)

class B06NewSourceTest(unittest.TestCase):
    def test_development_modes_rebuild_real_source_relations(self):
        for cid,value in [('southwest_airlines','4901000000'),('salesforce','14974000000')]:
            args=development(cid)
            if cid=='southwest_airlines':
                # Current PR42 source exposes a supplier-finance amount whose
                # borrowing nature is not established. Preserve that new gap.
                with self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_ITEM'):run(args)
                args=zero_supplier_test_source(args)
            p=run(args);self.assertEqual(value,p['carrying_amount']);self.assertTrue(p['complete'])
            self.assertEqual(d.REQUIRED,p['coverage']);self.assertTrue(p['disclosure_inventory']);self.assertEqual('NOT_EVALUATED_AT_SEMANTIC_LAYER',p['source_credit'])
    def test_same_arithmetic_but_explicit_lease_exclusion_rejects_at_relation(self):
        a=derived(development('southwest_airlines'),[(b'Finance leases are included in',b'Finance leases are not included in')])
        # Every amount and equation remains unchanged. New test source/proposal
        # identities eliminate old-hash and stale-quotation early rejection.
        self.assertNotEqual(a['raw'],development('southwest_airlines')['raw'])
        with self.assertRaisesRegex(ValueError,'FINANCE_LEASE_RELATIONSHIP_CONFLICT'):run(a)
    def test_selected_model_cannot_grant_inclusion_or_nonoverlap(self):
        a=development('salesforce');p=d.propose(raw=a['raw'],primary=a['primary'],target=a['target']);p['model_id']='INCLUSIVE_RECONCILED_COSTS'
        with self.assertRaises(ValueError):run(a,p)
        a=derived(a,[(b'accrued expenses and other liabilities and other noncurrent liabilities, respectively',b'current debt and noncurrent debt, respectively')])
        with self.assertRaisesRegex(ValueError,'SEPARATE_LEASE_RELATIONSHIP_CONFLICT'):run(a)
    def test_custom_outside_calculation_allowlist_cannot_disappear(self):
        a=copy.deepcopy(development('salesforce'))
        # Use an existing custom namespace and target native context. Rebuild
        # valid XML and identities; keep original model/formula/amounts intact.
        import xml.etree.ElementTree as ET
        root=ET.fromstring(a['raw']);ref=next(n.attrib['contextRef'] for n in root.iter() if n.tag.endswith('}FinanceLeaseLiability') and n.text=='535000000')
        ns=next(n.tag.split('}')[0][1:] for n in root.iter() if 'contextRef' in n.attrib and 'salesforce' in n.tag)
        extra=('<crm:IndependentShortTermFinancing contextRef=\"'+ref+'\" unitRef=\"usd\" decimals=\"-6\">12000000</crm:IndependentShortTermFinancing>').encode()
        pos=a['raw'].rfind(b'</');a['raw']=a['raw'][:pos]+extra+a['raw'][pos:];a['source']['raw_asset_id']='sha256:'+sha256_bytes(content=a['raw'])
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_ITEM'):run(a)
    def test_approval_fields_and_duplicate_formula_not_part_of_proposal(self):
        a=development('salesforce');p=d.propose(raw=a['raw'],primary=a['primary'],target=a['target'])
        for k,v in [('complete',True),('approved',True),('formula',['borrowing','finance_lease','finance_lease']),('scope_class','narrow')]:
            with self.subTest(field=k),self.assertRaisesRegex(ValueError,'PROPOSAL_CANNOT_ASSERT'):run(a,{**p,k:v})
    def test_asset_payment_wrong_year_and_entity_do_not_become_liability(self):
        original=development('salesforce')
        for before,after in [(b'FinanceLeaseLiability',b'FinanceLeaseRightOfUseAsset'),(b'FinanceLeaseLiability',b'FinanceLeaseLiabilityPaymentsDue')]:
            with self.subTest(after=after),self.assertRaisesRegex(ValueError,'DEBT_FACT_MISSING|CONFLICT'):run(derived(original,[(before,after)]))
        for k,v in [('period_end','2020-01-31'),('entity','1')]:
            a=copy.deepcopy(original);a['target'][k]=v
            with self.assertRaises(ValueError):run(a)
    def test_missing_primary_or_note_is_not_zero(self):
        a=copy.deepcopy(development('salesforce'));a['primary']=a['primary'][:-100]
        with self.assertRaisesRegex(ValueError,'PRIMARY_TRUNCATED'):run(a)
        a=derived(development('salesforce'),[(b'FinanceLeaseLiability',b'MissingLeaseLiability')])
        with self.assertRaisesRegex(ValueError,'DEBT_FACT_MISSING'):run(a)
    def test_forged_matching_ledger_has_no_admission(self):
        import io,tempfile,socket
        import sec_http
        from vnext.b06_new_source import _verify_source
        class Response(io.BytesIO):
            status=200
            headers={'Content-Type':'text/html','X-Test-Identity':'SYNTHETIC_NOT_SEC'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=development('salesforce');url=a['source']['source_url'];body=b'<html>caller-created financing evidence</html>'
            client=sec_http.SecHttpClient(workdir=root,config_path=ROOT/'config/sec_config.json',log_path=root/'evidence/requests_log.csv');client.config={**client.config,'max_retries':0}
            with patch.object(sec_http,'urlopen',side_effect=lambda **_:Response(body)),patch.object(socket.socket,'connect',side_effect=AssertionError('test forbids network')):
                client.fetch(url=url,purpose='TEST_ONLY_SELF_CREATED_LEDGER',local_path=root/'evidence/caller.xml')
            # The old raw/hash/header/ledger checks genuinely pass here.
            proof,loaded=_saved_source(repo_root=root,rows=_rows(root),url=url,accession=a['source']['accession']);self.assertEqual(loaded,body)
            with patch('vnext.b06_source_admission._trusted_entries',return_value=({'stage_id':'test'},[])):
                with self.assertRaisesRegex(ValueError,'TRUSTED_ACQUISITION_OR_IMPORT_REQUIRED'):_verify_source(root,proof)
    def test_reverse_subject_exclusion_and_inclusion_are_conflicts(self):
        for cid,sentence in [('southwest_airlines',b'The amounts in the debt table exclude all finance leases.'),('salesforce',b'The borrowings total includes all finance leases.')]:
            a=development(cid);needle=b'Finance leases are included in' if cid=='southwest_airlines' else b'Assets (also referred to as ROU assets)'
            changed=derived(a,[(needle,sentence+b' '+needle)])
            with self.assertRaisesRegex(ValueError,'RELATIONSHIP_CONFLICT'):run(changed)
    def test_custom_tax_loan_and_credit_facility_remain_unresolved(self):
        import re
        a=development('salesforce');parsed=d.parse_accession_xbrl_source(raw_bytes=a['raw'])
        f=next(f for f in parsed.facts if f['qualified_name']=='us-gaap:financeleaseliability' and parsed.contexts[f['context_ref']]['period_end']==a['target']['period_end'])
        for name in ['TaxFinancingLoan','EmergencyCreditFacility']:
            x=copy.deepcopy(a);tag=('<crm:'+name+' contextRef="'+f['context_ref']+'" unitRef="usd" decimals="0">99000000</crm:'+name+'>').encode();pos=x['raw'].rfind(b'</');x['raw']=x['raw'][:pos]+tag+x['raw'][pos:];x['source']['raw_asset_id']='sha256:'+sha256_bytes(content=x['raw'])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_ITEM'):run(x)
    def test_added_balance_sheet_financing_row_cannot_inherit_coverage(self):
        a=copy.deepcopy(development('salesforce'));pos=a['primary'].find(b'Total current liabilities');start=a['primary'].rfind(b'<tr',0,pos)
        # Match native table column spans so the new amount reaches the same
        # target year column; it is a real additional row, not damaged markup.
        a['primary']=a['primary'][:start]+b'<tr><td colspan="3">Independent short-term financing</td><td colspan="3">99</td></tr>'+a['primary'][start:]
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_ITEM'):run(a)
    def test_primary_only_sign_conflict_is_not_whitespace(self):
        a=copy.deepcopy(development('salesforce'));changed=a['primary'].replace(b'>535<',b'>(535)<');self.assertNotEqual(changed,a['primary']);a['primary']=changed
        with self.assertRaisesRegex(ValueError,'PRIMARY_NOTE_SOURCE_CONFLICT_OR_MISSING'):run(a)
    def test_dynamic_amounts_are_reread_with_new_test_identity(self):
        # Scale every monetary fact and every visible monetary inline fact as a
        # consistent new TEST_ONLY financial statement, retaining relationships.
        # Equity left unchanged makes the recomputed ratio sensitive to change.
        from decimal import Decimal
        import re
        a=copy.deepcopy(development('salesforce'))
        old=run(a)
        # Doubling only the complete finance lease current/noncurrent/total set
        # keeps borrowing composition intact and changes the true debt total.
        mapping={'535000000':'1070000000','275000000':'550000000','260000000':'520000000','569000000':'1138000000','34000000':'68000000','289000000':'578000000','120000000':'240000000','76000000':'152000000','58000000':'116000000','26000000':'52000000'}
        for before,after in mapping.items():a['raw']=a['raw'].replace(('>'+before+'<').encode(),('>'+after+'<').encode())
        # Source-level numeric facts are changed; embedded lease note values and
        # primary inline values follow the same amounts (no stored proof reuse).
        for before,after in [('535','1,070'),('275','550'),('260','520'),('569','1,138'),('34','68'),('289','578'),('120','240'),('76','152'),('58','116'),('26','52')]:
            for field in ['raw','primary']:
                a[field]=re.sub(rb'(?<=>)(\()?'+before.encode()+rb'(\))?(?=<)',lambda m:(m[1] or b'')+after.encode()+(m[2] or b''),a[field])
                a[field]=re.sub(rb'(?<=&gt;)(\()?'+before.encode()+rb'(\))?(?=(?:&#160;)?&lt;)',lambda m:(m[1] or b'')+after.encode()+(m[2] or b''),a[field])
        a['source']['raw_asset_id']='sha256:'+sha256_bytes(content=a['raw'])
        updated=run(a);self.assertEqual(Decimal(old['carrying_amount'])+Decimal('535000000'),Decimal(updated['carrying_amount']))

if __name__=='__main__':unittest.main()
