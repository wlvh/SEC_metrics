"""Formatting cannot drop note text, relax scope, or rewrite source blocks."""
from hashlib import sha256
import re
import unittest

from vnext import annual_amendment_scope as scope
from vnext.amendment_note_layout import paragraph_blocks, part_iii_pattern, conditional_recovery_patterns
from vnext.instant_balance_amendment import POLICY as INSTANT_POLICY, _cover_matches
from vnext.text_coverage import _Blocks


def document(body):
    text='<html><body>'+body+'</body></html>'
    raw=text.encode('utf-8');parser=_Blocks(text);parser.feed(text);parser.close();parser._flush()
    blocks=[]
    for index,b in enumerate(parser.blocks):
        start=len(text[:b['start']].encode('utf-8'));end=len(text[:b['end']].encode('utf-8'))
        blocks.append({'text':b['text'],'linked':b['linked'],'block_index':index,
            'raw_start_byte':start,'raw_end_byte':end,'raw_span_sha256':sha256(raw[start:end]).hexdigest()})
    return raw,{'blocks':blocks}


class AmendmentNoteLayoutTest(unittest.TestCase):
    def test_inline_fragments_are_three_paragraphs_not_thirteen_blocks(self):
        parts=['Paramount Global is filing on Form ', '10-K/A', ' its original Form ', '10-K',
               ' for the year ended December 31, 2024, as an amendment to ', '10-K',
               ' solely to amend Part III Items 10 through 14 of ', '10-K', ' rather than a proxy.']
        first='<div>'+''.join(p if i%2==0 else '<div style="display:inline">'+p+'</div>' for i,p in enumerate(parts))+'</div>'
        raw,doc=document('<p>EXPLANATORY NOTE</p>'+first+
            '<div>Except as stated, no other change to Form <div style="display:inline">10-K.</div></div>'+
            '<p>“Company” means this registrant and its subsidiaries.</p><p>PART III</p>')
        self.assertEqual(len(doc['blocks']),14)
        with self.assertRaisesRegex(scope.AmendmentScopeError,'SCOPE_UNSUPPORTED'):scope._note(doc)
        note=scope._note(doc,raw=raw)
        self.assertEqual((note['start'],note['end']),(0,13))
        self.assertEqual(len(paragraph_blocks(note['blocks'][1:],raw)),3)
        self.assertEqual(note['blocks'],doc['blocks'][:13])
        self.assertEqual(note['text'],' '.join(b['text'] for b in doc['blocks'][1:13]))
        self.assertTrue(all(sha256(raw[b['raw_start_byte']:b['raw_end_byte']]).hexdigest()==b['raw_span_sha256'] for b in note['blocks']))

    def test_eight_real_body_paragraphs_are_still_refused(self):
        raw,doc=document('<p>EXPLANATORY NOTE</p>'+''.join('<p>Statement '+str(i)+'</p>' for i in range(8))+'<p>PART III</p>')
        with self.assertRaisesRegex(scope.AmendmentScopeError,'SCOPE_UNSUPPORTED'):scope._note(doc,raw=raw)

    def test_substantive_and_block_styled_gaps_cannot_join(self):
        for middle in ('<p>','<span style="display:block">',' omitted statement '):
            raw=('first'+middle+'second').encode()
            blocks=[{'raw_start_byte':0,'raw_end_byte':5},{'raw_start_byte':len(raw)-6,'raw_end_byte':len(raw)}]
            self.assertEqual(len(paragraph_blocks(blocks,raw)),2)

    def test_raw_ranges_must_be_ordered_and_inside_original_bytes(self):
        for blocks in ([{'raw_start_byte':0,'raw_end_byte':20}],
                       [{'raw_start_byte':1,'raw_end_byte':5},{'raw_start_byte':4,'raw_end_byte':7}]):
            with self.assertRaisesRegex(ValueError,'SOURCE_RANGE'):paragraph_blocks(blocks,b'original')

    def test_legacy_short_note_has_the_same_shape_text_and_blocks(self):
        raw,doc=document('<p>EXPLANATORY NOTE</p><p>Only a governance addition.</p><p>PART III</p>')
        self.assertEqual(scope._note(doc),scope._note(doc,raw=raw))

    def test_proxy_clause_is_equivalent_but_other_purposes_are_not(self):
        pattern=part_iii_pattern(INSTANT_POLICY['part_iii_note_pattern'])
        text=('Paramount Global (the “Company”), a Delaware corporation, is filing this Amendment No. 1 on Form 10-K/A '
              '(this “Amendment”) to its Annual Report on Form 10-K for the year ended December 31, 2024, originally filed '
              'with the Securities and Exchange Commission (the “SEC”) on February 26, 2025 (the “Initial Form 10-K”), '
              'to amend Part III, Items 10, 11, 12, 13 and 14 of the Initial Form 10-K to include the information required by such Items. '
              'Except as explicitly set forth herein, this Amendment does not otherwise change, modify or update the disclosures in, '
              'or exhibits to, the Initial Form 10-K. References to “Paramount,” the “Company,” “we,” “us” and “our” '
              'refer to Paramount Global and its consolidated subsidiaries, unless the context otherwise requires.')
        original=re.fullmatch(INSTANT_POLICY['part_iii_note_pattern'],text)
        self.assertIsNotNone(original)
        self.assertEqual(re.fullmatch(pattern,text).groupdict(),original.groupdict())
        changed=text.replace('to amend Part III','solely to amend Part III').replace('such Items.','such Items, rather than incorporate such information into Part III by reference to a proxy statement.').replace('References to ','References in this document to ')
        self.assertIsNotNone(re.fullmatch(pattern,changed))
        for bad in (changed+' We also revise financial statements.', changed.replace('Items 10, 11, 12, 13 and 14','Items 7, 10, 11, 12, 13 and 14'), changed.replace('does not otherwise change','does otherwise change')):
            self.assertIsNone(re.fullmatch(pattern,bad))

    def test_unknown_layout_is_rejected_before_source_reading(self):
        with self.assertRaisesRegex(scope.AmendmentScopeError,'LAYOUT_UNSUPPORTED'):
            scope.inspect_annual_amendment_scope(original={},amendment={},company_id='constructed',cik='1',note_layout='guess')

    def test_fragmented_cover_matches_keep_all_original_source_blocks(self):
        raw,doc=document('<div>Correction <div style="display:inline">of an error</div> not reported. ☐</div>')
        pattern=r'Correction of an error not reported\. ☐'
        self.assertEqual(_cover_matches(doc['blocks'],raw,pattern,'blocks-v1'),[])
        matched=_cover_matches(doc['blocks'],raw,pattern,'inline-paragraphs-v2')
        self.assertEqual(len(matched),1)
        self.assertEqual(matched[0]['source_blocks'],doc['blocks'])
        self.assertEqual(matched[0]['block_indices'],[0,1,2])
        self.assertNotIn('raw_span_sha256',matched[0])
        bad_raw,bad_doc=document('<div>Correction <div style="display:inline">of an error</div> not reported. ☐ We also restate cash.</div>')
        self.assertEqual(_cover_matches(bad_doc['blocks'],bad_raw,pattern,'inline-paragraphs-v2'),[])

    def test_defined_statutory_alias_keeps_only_the_same_conditional_clause(self):
        text=('✓ Clawback Policy: In addition to maintaining a clawback policy as required by the Exchange Act Rule 10D-1 and Nasdaq listing standards '
              '(which we apply beyond executive officers to other senior executives of the Company), provide for forfeiture, repayment or adjustment '
              'of incentive compensation in the event of a financial restatement without regard to misconduct in our NEOs’ employment agreements')
        patterns=conditional_recovery_patterns(INSTANT_POLICY['conditional_recovery_block_patterns'])
        self.assertTrue(any(re.fullmatch(p,text,re.I) for p in patterns))
        expanded=text.replace('Exchange Act Rule','Securities Exchange Act of 1934, as amended (the “Exchange Act”) Rule')
        self.assertTrue(any(re.fullmatch(p,expanded,re.I) for p in patterns))
        for wrong in (expanded+' We have restated cash.',expanded.replace('in the event of a','following our current'),expanded.replace('Securities Exchange Act of 1934','Another Act of 1934')):
            self.assertFalse(any(re.fullmatch(p,wrong,re.I) for p in patterns))
