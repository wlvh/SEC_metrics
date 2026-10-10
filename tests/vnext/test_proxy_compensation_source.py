"""Small no-inline proxy controls; no source acquisition or model answer."""
import copy
import unittest
from pathlib import Path
from sec_urls import accession_document_url
from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash,sha256_bytes
from vnext.records import validate_record
from vnext.sources import source_reference_record
from vnext.specs import compile_spec_file
from vnext.observations import scope_key
from vnext.proxy_compensation_source import (SPEC_PATH,ProxyCompensationError,
    resolve_proxy_compensation_table,row_amounts_by_arithmetic)
from vnext.proxy_source_identity import (ProxySourceIdentityError,proxy_cover,cover_name_in_effect,
    governance_source_document)

FILING={'form':'DEF 14A','accessionNumber':'0001234567-22-000001',
        'primaryDocument':'proxy.htm','filingDate':'2022-04-01','reportDate':''}
INVENTORY={'cik':1234567,'name':'Example Corporation','formerNames':[]}
CHIEF=['Jane Doe Chief Executive Officer','2021','1,000,000','500,000','1,500,000']


def arguments(raw):
    blob=validate_record(record={'record_type':'RAW_BLOB','raw_asset_id':'sha256:'+sha256_bytes(content=raw),
        'byte_length':len(raw),'media_type':'text/html','storage_uri':'evidence/constructed/proxy.htm'})
    ref=source_reference_record(raw_blob=blob,company_id='company',
        source_url=accession_document_url(cik=1234567,accession=FILING['accessionNumber'],document_name=FILING['primaryDocument']),
        accession=FILING['accessionNumber'],document_name=FILING['primaryDocument'],source_role='governance_proxy',request_attempt_id='constructed')
    scope={'entity_scope':'registrant'}
    return {'raw_bytes':raw,'raw_blob':blob,'source_reference':ref,'filing':dict(FILING),
        'inventory':copy.deepcopy(INVENTORY),'company_id':'company','cik':'1234567',
        'target':{'company_id':'company','period_start':'2021-01-01','period_end':'2021-12-31',
                  'scope':scope,'scope_key':scope_key(scope=scope)},'fiscal_year':2021,
        'compiled_spec':compile_spec_file(path=REPO_ROOT/SPEC_PATH,dependency_specs={})}

def _cover(*, marks=None, name="Example Corporation", caption="(Name of Registrant as Specified In Its Charter)"):
    """A minimal Schedule 14A cover, one block per line, marks beside their options."""
    marks = {"PRELIMINARY": "\u2610", "CONFIDENTIAL": "\u2610", "DEFINITIVE": "\u2612",
             "ADDITIONAL": "\u2610", "SOLICITING": "\u2610", **(marks or {})}
    lines = ["UNITED STATES", "SCHEDULE 14A", "Check the appropriate box:",
             marks["PRELIMINARY"] + " Preliminary Proxy Statement",
             marks["CONFIDENTIAL"] + " Confidential, for Use of the Commission Only",
             marks["DEFINITIVE"] + " Definitive Proxy Statement",
             marks["ADDITIONAL"] + " Definitive Additional Materials",
             marks["SOLICITING"] + " Soliciting Material under \u00a7240.14a-12",
             name, caption, "Payment of Filing Fee", "Proxy statement body."]
    body = "".join("<p>" + line + "</p>" for line in lines if line)
    return ("<html><body>" + body + "</body></html>").encode("utf-8")


def _proxy(table_rows, *, title="SUMMARY COMPENSATION TABLE", context="", header=None):
    """A constructed proxy: a definitive cover, a title, and one table."""
    header = header or ["Name and Principal Position", "Year", "Salary ($)", "Bonus ($)", "Total ($)"]
    cells = lambda row: "".join("<td>" + cell + "</td>" for cell in row)  # noqa: E731
    table = "<table><tr>" + cells(header) + "</tr>" + "".join(
        "<tr>" + cells(row) + "</tr>" for row in table_rows) + "</table>"
    blocks = ("<p>" + title + "</p>" if title else "") + ("<p>" + context + "</p>" if context else "")
    return _cover().replace(b"Proxy statement body.</p>", ("Proxy statement body.</p>" + blocks + table).encode())



class ProxyCompensationSourceTest(unittest.TestCase):
    def resolve(self,raw):return resolve_proxy_compensation_table(**arguments(raw))

    def test_nonempty_control_and_native_amount_locator(self):
        answer=self.resolve(_proxy([CHIEF]))
        self.assertEqual('1500000',answer['result']['value'])
        self.assertEqual('1,500,000',answer['selection']['candidates'][0]['amount']['text'])
        self.assertEqual([0,0,0],answer['business_calls'])

    def test_wrong_sum_currency_title_and_scaling_remain_withheld(self):
        cases=[(_proxy([CHIEF[:-1]+['1,600,000']]),'C03_PROXY_SCT_TOTAL_IS_NOT_THE_SUM_OF_ITS_COMPONENTS'),
               (_proxy([CHIEF],title='2020 SUMMARY COMPENSATION TABLE'),'C03_PROXY_SCT_NOT_ESTABLISHED'),
               (_proxy([CHIEF],context='Amounts are in Canadian dollars.'),'C03_PROXY_SCT_NOT_ESTABLISHED'),
               (_proxy([CHIEF],context='Amounts in millions.'),'C03_PROXY_SCT_NOT_ESTABLISHED'),
               (_proxy([CHIEF],header=['Name and Principal Position','Year','Salary','Bonus','Total']),'C03_PROXY_SCT_DOLLAR_NOT_ESTABLISHED')]
        for raw,reason in cases:
            with self.subTest(reason=reason):
                answer=self.resolve(raw);self.assertEqual(reason,answer['selection']['reason_code']);self.assertIsNone(answer['result']['value'])

    def test_multiple_people_and_subsidiary_ceo_do_not_first_win(self):
        another=['Other Person Co-CEO','2021','100','50','150']
        self.assertEqual('C03_PROXY_SCT_MORE_THAN_ONE_CHIEF_EXECUTIVE',self.resolve(_proxy([CHIEF,another]))['selection']['reason_code'])
        for title in ('Assistant to the CEO','CEO CIB','Chairman & CEO, Another Subsidiary'):
            wrong=[title,*CHIEF[1:]]
            self.assertEqual('C03_PROXY_SCT_NOT_FOUND',self.resolve(_proxy([wrong]))['selection']['reason_code'])

    def test_actual_annual_scope_does_not_change_to_calendar_year(self):
        args=arguments(_proxy([CHIEF]));args['target'].update(period_start='2021-01-31',period_end='2022-01-29')
        answer=resolve_proxy_compensation_table(**args)
        self.assertEqual('2022-01-29',answer['result']['period_end'])
        self.assertEqual('TABLE_YEAR_EQUALS_PINNED_FISCAL_YEAR',answer['selection']['period_basis'])

    def test_source_subject_target_inventory_and_complete_body_are_checked(self):
        base=arguments(_proxy([CHIEF]))
        for change in ('source','company','cik','inventory','target','form'):
            args=copy.deepcopy(base)
            if change=='source':args['raw_bytes']+=b'changed'
            elif change=='company':args['company_id']='other'
            elif change=='cik':args['cik']='7654321'
            elif change=='inventory':args['inventory']['cik']=7654321
            elif change=='target':args['target']['company_id']='other'
            else:args['filing']['form']='10-K'
            with self.subTest(change=change),self.assertRaises(ValueError):resolve_proxy_compensation_table(**args)
        with self.assertRaisesRegex(ProxyCompensationError,'SOURCE_DOCUMENT_INCOMPLETE'):
            self.resolve(_proxy([CHIEF]).replace(b'</body></html>',b''))

    def test_inline_document_does_not_fallback_to_the_table(self):
        raw=_proxy([CHIEF]).replace(b'<body>',b'<body><ix:header></ix:header>')
        with self.assertRaisesRegex(ProxyCompensationError,'ONLY_FOR_A_PROXY_WITHOUT_INLINE_XBRL'):self.resolve(raw)

    def test_native_total_locator_still_matches_after_trailing_footnote_cell(self):
        answer=self.resolve(_proxy([CHIEF+['7']],header=['Name and Principal Position','Year','Salary ($)','Bonus ($)','Total ($)','Note']))
        candidate=answer['selection']['candidates'][0]
        self.assertEqual('1500000',answer['result']['value'])
        self.assertEqual('1,500,000',candidate['amount']['text'])
        from vnext.table_grid import resolve_cell
        observed=answer['observation']['source_binding']
        recovered=resolve_cell(derived_asset=answer['derived_assets'][0],locator=observed['table_locator'])
        self.assertEqual('1,500,000',recovered['text'])
        self.assertEqual(recovered['raw_text'],observed['reported_raw_text'])

    def test_name_helper_is_a_c02_dependency_not_a_new_global_dependency(self):
        from vnext import ordinary_current_update as update
        from unittest.mock import patch
        path='scripts/vnext/organization_name_core.py'
        c02=update._configuration(REPO_ROOT,'marriott_international','C02')
        income=update._configuration(REPO_ROOT,'marriott_international','B01')
        self.assertIn(path,c02['processing_files']);self.assertNotIn(path,income['processing_files'])
        original=update.sha256_file
        def changed(*,path):return 'changed-name-version' if path.name=='organization_name_core.py' else original(path=path)
        with patch.object(update,'sha256_file',side_effect=changed):
            self.assertNotEqual(c02,update._configuration(REPO_ROOT,'marriott_international','C02'))
            self.assertEqual(income,update._configuration(REPO_ROOT,'marriott_international','B01'))

    def test_cover_and_dated_names_remain_distinct_from_amount(self):
        args=arguments(_proxy([CHIEF]));args['inventory']['name']='Another Corporation'
        with self.assertRaisesRegex(ProxySourceIdentityError,'NOT_THE_SEC_NAME_ON_FILING_DATE'):
            resolve_proxy_compensation_table(**args)
        inv={'name':'New Corporation','formerNames':[{'name':'Example Corporation','from':'2020-01-01','to':'2022-02-28'}]}
        cover=proxy_cover(raw_bytes=_proxy([CHIEF]),filing=FILING)
        with self.assertRaises(ProxySourceIdentityError):cover_name_in_effect(cover=cover,inventory=inv,filing=FILING)
        self.assertEqual('Example Corporation',cover_name_in_effect(cover=cover,inventory=inv,filing={**FILING,'filingDate':'2021-04-01'})['cover_registrant_name'])

if __name__=='__main__':unittest.main()
