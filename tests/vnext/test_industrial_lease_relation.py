"""Small real parser inputs, plus exact source-relation controls; no installation."""
from copy import deepcopy
import re
import unittest

from vnext.canonical import sha256_bytes
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.financial_structured import _InlineTableIndex, _fact_cells
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.industrial_lease_relation import inspect_inclusion

NS = ('xmlns:xbrli="http://www.xbrl.org/2003/instance" '
      'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
      'xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:f="urn:test-company" '
      'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
      'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"')


def fixture(*, scale='0', carrier='25', peer='25', lease='10', unit='usd', entity='1', end='2025-12-31',
            duplicate_lease=False, outside_lease=False, note_entity='1', note_end='2025-12-31'):
    def context(id, who, instant, extra=''):
        return ('<xbrli:context id="'+id+'"><xbrli:entity><xbrli:identifier '
          'scheme="http://www.sec.gov/CIK">'+who+'</xbrli:identifier></xbrli:entity>'
          '<xbrli:period><xbrli:instant>'+instant+'</xbrli:instant></xbrli:period>'
          '<xbrli:scenario><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">'
          'f:CompanyExcludingCreditMember</xbrldi:explicitMember>'+extra+'</xbrli:scenario></xbrli:context>')
    contexts = context('c','1','2025-12-31') + context('k',entity,end,
        '<xbrldi:explicitMember dimension="us-gaap:LongtermDebtTypeAxis">'
        'us-gaap:NotesPayableOtherPayablesMember</xbrldi:explicitMember>')
    contexts += ('<xbrli:context id="n"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'+note_entity+
        '</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate>'
        '<xbrli:endDate>'+note_end+'</xbrli:endDate></xbrli:period></xbrli:context>')
    units = ('<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
             '<xbrli:unit id="gbp"><xbrli:measure>iso4217:GBP</xbrli:measure></xbrli:unit>')
    def f(name,ctx,value,scale='0',unit='usd'):
        return '<ix:nonFraction name="us-gaap:'+name+'" contextRef="'+ctx+'" unitRef="'+unit+'" scale="'+scale+'" decimals="INF">'+value+'</ix:nonFraction>'
    primary = ('<html '+NS+'>'+contexts+units+'<ix:nonNumeric name="us-gaap:DebtDisclosureTextBlock" contextRef="n">'
        '<p>The carrying amounts are as follows (in dollars).</p><table><tr><td>2025</td><td>2025</td></tr>'
        '<tr><td>Other debt (including finance leases) (a)</td><td>'+f('OtherLoansPayableCurrent','k',carrier,scale,unit)+'</td></tr>'
        '<tr><td>Total current debt</td><td>'+f('LongTermDebtCurrent','c','100')+'</td></tr>'
        '<tr><td>Other debt (including finance leases) (a)</td><td>'+f('OtherLoansPayableNoncurrent','k','50')+'</td></tr>'
        '<tr><td>Total noncurrent debt</td><td>'+f('LongTermDebtNoncurrent','c','200')+'</td></tr></table>'
        +( '</ix:nonNumeric>' if outside_lease else '')
        +f('FinanceLeaseLiabilityCurrent','c',lease)+f('FinanceLeaseLiabilityNoncurrent','c','20')
        +( '' if outside_lease else '</ix:nonNumeric>')
        +(f('FinanceLeaseLiabilityCurrent','c',lease) if duplicate_lease else '')+'</html>').encode()
    xml = ('<xbrli:xbrl '+NS+'>'+contexts+units + ''.join(
      '<us-gaap:'+name+' contextRef="'+ctx+'" unitRef="'+u+'" decimals="INF">'+value+'</us-gaap:'+name+'>'
      for name,ctx,u,value in [('OtherLoansPayableCurrent','k',unit,peer),('LongTermDebtCurrent','c','usd','100'),
        ('OtherLoansPayableNoncurrent','k','usd','50'),('LongTermDebtNoncurrent','c','usd','200'),
        ('FinanceLeaseLiabilityCurrent','c','usd',lease),('FinanceLeaseLiabilityNoncurrent','c','usd','20')])+'</xbrli:xbrl>').encode()
    native={};sources={}
    for kind,raw in [('primary',primary),('xml',xml)]:
        parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode());meta.close()
        native[kind]=(parsed,meta);sources[kind]={'raw_bytes':raw,'source_reference':{'raw_asset_id':'sha256:'+sha256_bytes(content=raw),'source':'TEST_ONLY'}}
    parsed=native['primary'][0];index=_InlineTableIndex(primary);index.feed(primary.decode());index.close()
    cells=_fact_cells(index,parsed,{3,5});parents={};leases={'primary':{},'xml':{}}
    for role,ord,value in [('current_debt',3,'100'),('noncurrent_debt',5,'200')]:
        table,cell=cells[ord]
        parents[role]={'value':value,'source_reports':{'primary':[{'ordinal':ord,'value':value,'unit':'USD',
            'context':dict(parsed.contexts['c'])}]},'visible_table_evidence':[{'ordinal':ord,'table':table,'cell':cell,'column_headers':[{'row_index':0}]}]}
    for kind,(p,m) in native.items():
        for fact in p.facts:
            name=m.facts[fact['ordinal']]['concept'][1].casefold()
            if name in ('financeleaseliabilitycurrent','financeleaseliabilitynoncurrent'):
                leases[kind].setdefault(name,[]).append({'ordinal':fact['ordinal'],'value':fact['text'],'decimals':'INF'})
    return {'primary':sources['primary'],'parsed':parsed,'reported_components':parents,'lease_reports':leases,
            'native_sources':native,'index':index,'sources':sources}


class IndustrialLeaseRelationTest(unittest.TestCase):
    def alter_carrier_namespace(self, args, *, alias=False):
        raw=args['sources']['xml']['raw_bytes']
        def change(match):
            part=match[0]
            if alias:
                part=part.replace(b'<xbrli:context id="k">', b'<xbrli:context id="k" xmlns:g="http://fasb.org/us-gaap/2025" xmlns:ff="urn:test-company">')
                return part.replace(b'us-gaap:StatementBusinessSegmentsAxis',b'g:StatementBusinessSegmentsAxis').replace(b'f:CompanyExcludingCreditMember',b'ff:CompanyExcludingCreditMember')
            return part.replace(b'<xbrli:context id="k">', b'<xbrli:context id="k" xmlns:f="urn:other-company">')
        raw,n=re.subn(rb'<xbrli:context id="k">.*?</xbrli:context>',change,raw,flags=re.S)
        self.assertEqual(1,n)
        p=parse_accession_xbrl_source(raw_bytes=raw);m=_ReportedFactMetadata();m.feed(raw.decode());m.close()
        args['native_sources']['xml']=(p,m);args['sources']['xml']['raw_bytes']=raw
        args['sources']['xml']['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=raw)

    def test_same_member_qname_with_different_prefix_is_preserved(self):
        args=fixture();self.alter_carrier_namespace(args,alias=True)
        self.assertEqual('REPORTED_INCLUDED',inspect_inclusion(**args)['status'])

    def test_same_member_text_with_wrong_namespace_is_not_same_scope(self):
        args=fixture();self.alter_carrier_namespace(args)
        self.assertEqual('UNRESOLVED',inspect_inclusion(**args)['status'])

    def test_direct_own_amount_and_scale_support_inclusion(self):
        result=inspect_inclusion(**fixture())
        self.assertEqual('REPORTED_INCLUDED',result['status']);self.assertEqual('0',result['additional_debt_amount'])
        e=result['relationships'][0]['evidence'][0]
        self.assertEqual('25',e['carrier_reports']['primary']['value']);self.assertEqual('0',e['carrier_reports']['primary']['reported_scale'])
        self.assertFalse(result['complete_B06'])

    def test_own_carrier_scale_not_parent_scale(self):
        # Native agreement cannot override the table's explicit dollars.
        self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(scale='3',carrier='0.025',peer='25'))['status'])
        self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(scale='-3',carrier='25',peer='0.025'))['status'])
        self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(scale='3',carrier='25',peer='25000'))['status'])

    def test_containing_row_smaller_than_lease_even_below_parent_total(self):
        self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(lease='30'))['status'])

    def test_currency_period_or_subject_change_does_not_bind(self):
        for args in ({'unit':'gbp'},{'entity':'2'},{'end':'2024-12-31'}):
            self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(**args))['status'])

    def test_xml_carrier_amount_conflict_cannot_be_ignored(self):
        with self.assertRaisesRegex(ValueError,'DEBT_SAME_PRECISION_CONFLICT'):
            inspect_inclusion(**fixture(peer='24'))

    def test_caption_of_current_segment_cannot_prove_noncurrent(self):
        args=fixture();table=args['reported_components']['noncurrent_debt']['visible_table_evidence'][0]['table']
        table['rows'][3]['cells'][0]['text']='Other debt'
        self.assertEqual('UNRESOLVED',inspect_inclusion(**args)['status'])

    def test_excluding_caption_is_not_inclusion(self):
        args=fixture()
        for parent in args['reported_components'].values():
            for row in parent['visible_table_evidence'][0]['table']['rows']:
                row['cells'][0]['text']=row['cells'][0]['text'].replace('including','excluding')
        self.assertEqual('UNRESOLVED',inspect_inclusion(**args)['status'])

    def test_missing_peer_is_not_zero(self):
        args=fixture();args['lease_reports']['xml']={}
        self.assertEqual('UNRESOLVED',inspect_inclusion(**args)['status'])

    def test_same_value_disclosed_elsewhere_does_not_erase_note_support(self):
        self.assertEqual('REPORTED_INCLUDED',inspect_inclusion(**fixture(duplicate_lease=True))['status'])

    def test_lease_outside_debt_note_cannot_supply_relationship(self):
        self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(outside_lease=True))['status'])

    def test_debt_note_subject_or_period_must_match(self):
        for args in ({'note_entity':'2'},{'note_end':'2024-12-31'}):
            self.assertEqual('UNRESOLVED',inspect_inclusion(**fixture(**args))['status'])

if __name__=='__main__':unittest.main()
