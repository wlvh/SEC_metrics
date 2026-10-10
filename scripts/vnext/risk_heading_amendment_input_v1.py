"""Explicit selected-original Item 1A input, separate from financial clearance.

Only a fully identified Part III addition with no Item 1A amendment section
and no unexplained risk-section reference is supported. No headings, metric
answer, acquisition, subject continuity or general no-effect claim is supplied.
"""
from datetime import datetime
from pathlib import Path
import re

from .annual_amendment_scope import AmendmentScopeError, _need, _words
from .annual_amendment_scope_v2 import inspect_annual_amendment_scope
from .amendment_note_layout import part_iii_pattern, paragraph_blocks, paragraph_text
from .canonical import content_hash, strict_json_file
from .normal_annual_input_v2 import exact_json_value

INPUT_CLASS = 'SELECTED_ORIGINAL_ITEM_1A_HEADINGS'
NOTE_POLICY_PATH = 'config/instant_balance_amendment_v1.json'
PROCESSING_FILES = (
    'scripts/vnext/risk_heading_amendment_input_v1.py',
    'scripts/vnext/annual_amendment_scope.py',
    'scripts/vnext/annual_amendment_scope_v2.py',
    'scripts/vnext/amendment_note_layout.py',
    'scripts/vnext/text_coverage.py',
    'scripts/vnext/text_results_v2.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/canonical.py',
    'scripts/vnext/deterministic_router.py',
    'scripts/vnext/fiscal_year_labels.py',
    'config/annual_amendment_scope_v1.json',
    NOTE_POLICY_PATH,
)


def _identity(source, company_id):
    ref=source['reference'];filing=source['filing']
    _need(ref['company_id']==company_id and ref['accession']==filing['accessionNumber']
          and ref['document_name']==filing['primaryDocument'], 'RISK_AMENDMENT_SOURCE_FILING_REFERENCE_DIFFERS')


def _note_identity(scope):
    # Reuse only the existing complete source-note grammar, not the financial
    # policy's input classes, decisions or correction/statement algorithms.
    root=Path(__file__).resolve().parents[2]
    policy=strict_json_file(path=root/NOTE_POLICY_PATH)
    grammar={k:policy[k] for k in ('part_iii_note_pattern','alias_list_pattern')}
    match=re.fullmatch(part_iii_pattern(grammar['part_iii_note_pattern']),scope['explanatory_note']['text'])
    _need(match is not None,'RISK_AMENDMENT_COMPLETE_NOTE_UNSUPPORTED')
    _need(re.fullmatch(grammar['alias_list_pattern'],match['aliases']) is not None,
          'RISK_AMENDMENT_NOTE_ALIAS_LIST_UNSUPPORTED')
    old=scope['original'];new=scope['amendment']
    _need(any(_words(match['registrant'])==_words(name)==_words(match['scope_name'])
              for name in new['document']['registrant_names']), 'RISK_AMENDMENT_NOTE_SUBJECT_CONFLICT')
    _need(datetime.strptime(match['end'],'%B %d, %Y').date().isoformat()==old['filing']['reportDate']
          and datetime.strptime(match['filed'],'%B %d, %Y').date().isoformat()==old['filing']['filingDate'],
          'RISK_AMENDMENT_NOTE_ORIGINAL_IDENTITY_CONFLICT')
    blocks=new['document']['blocks'];note=scope['explanatory_note']
    banners=[b for b in blocks[:note['start']]
             if re.fullmatch(r'\(?Amendment No\. [0-9]+\)?',b['text'])]
    expected='Amendment No. '+match['number']
    _need(len(banners)==1 and banners[0]['text'] in {expected,'('+expected+')'}
          and banners[0]['block_index'] not in new['quoted_block_indices'],
          'RISK_AMENDMENT_NOTE_NUMBER_CONFLICT')
    return {'declared_identity':dict(match.groupdict()),'banner':banners[0],
            'note_grammar_hash':content_hash(value=grammar)}


def _mentions_risk_section(text):
    if re.search(r'\brisk factors\b',text,re.I):return True
    # SEC item identifiers, lists and ranges are mechanical references, not
    # a classification of the assertion's meaning. Unexplained references to
    # the selected item remain unresolved regardless of the surrounding verb.
    identifier=r'[0-9]+[A-Z]?'
    separator=r'(?:,\s*(?:and\s+|or\s+)?|and\s+|or\s+|through\s+|to\s+|[-–—]\s*)'
    pattern=re.compile(r'\bitems?\s*('+identifier+r'(?:\s*'+separator+identifier+r')*)',re.I)
    def key(value):
        number=re.fullmatch(r'([0-9]+)([A-Z]?)',value,re.I)
        return int(number[1]),number[2].casefold()
    target=(1,'a')
    for reference in pattern.finditer(text):
        value=reference[1]
        if target in [key(i) for i in re.findall(identifier,value,re.I)]:return True
        for interval in re.finditer('('+identifier+r')\s*(?:through|to|[-–—])\s*('+identifier+')',value,re.I):
            if key(interval[1])<=target<=key(interval[2]):return True
    return False


def _risk_references(scope, raw):
    """Retain references; unsupported assertions are unresolved, not reclassified.

    The sole allowed risk-section mention is the explicit initial-10-K citation
    in the forward-looking caution section. Arbitrary new Item 1A prose cannot
    acquire unchanged-input credit merely by lacking a numbered heading.
    """
    blocks=scope['amendment']['document']['blocks']
    start=scope['explanatory_note']['end']
    caution=(start if start<len(blocks) and blocks[start]['text'].upper().startswith('CAUTIONARY NOTE') else None)
    part3=next((i for i in range(start+1,len(blocks))
                if blocks[i]['text'].upper()=='PART III' and not blocks[i]['linked']),None)
    citation=re.compile(r'These risks, uncertainties and other factors are discussed in [“\"]Item\s+1A\. Risk Factors[”\"] in our Initial Form 10-K\.')
    records=[];unresolved=[]
    for group in paragraph_blocks(blocks,raw):
        text=paragraph_text(group,raw)
        if not _mentions_risk_section(text):continue
        indices=[b['block_index'] for b in group]
        matches=list(citation.finditer(text));residual=citation.sub('',text)
        inside=(caution is not None and part3 is not None and all(caution<i<part3 for i in indices))
        quoted=bool(set(indices)&set(scope['amendment']['quoted_block_indices']))
        accepted=inside and bool(matches) and not _mentions_risk_section(residual) and not quoted
        item={'source_blocks':group,'block_indices':indices,'text':text,
              'initial_filing_citations':[m.group() for m in matches],
              'caution_window':{'heading_block':caution,'end_block_exclusive':part3},
              'status':'INITIAL_FILING_CROSS_REFERENCE' if accepted else 'UNRESOLVED_RISK_SECTION_REFERENCE'}
        records.append(item)
        if not accepted:unresolved.append(item)
    return records,unresolved


def _assess_risk_heading_amendment(*, original, amendment, company_id, cik):
    """Consume existing raw/blob/reference/filing source frames, never saved answers.

    Authentication/byte/identity failures propagate. Only a proved source frame
    can produce a source-limitation record; the caller checks every amendment
    and independently owns source acquisition, heading extraction and results.
    """
    _identity(original,company_id);_identity(amendment,company_id)
    scope=inspect_annual_amendment_scope(original=original,amendment=amendment,
        company_id=company_id,cik=cik,note_layout='inline-paragraphs-v2')
    old=scope['original'];new=scope['amendment'];details={};issues=[]
    try:
        _need(scope['fiscal_window_unchanged'] and not scope['issues'], 'RISK_AMENDMENT_SOURCE_SCOPE_UNRESOLVED')
        _need(scope['classification']=='PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
              'RISK_AMENDMENT_KIND_UNSUPPORTED')
        details['note_identity']=_note_identity(scope)
        section=old['document']['sections']['ITEM_1A']
        _need(section['status']=='LOCATED','RISK_AMENDMENT_ORIGINAL_ITEM_1A_NOT_UNIQUE')
        details['original_item_1a_section']=section
        _need(new['document']['sections']['ITEM_1A']['status']=='MISSING', 'RISK_AMENDMENT_NEW_ITEM_1A_SECTION')
        references,unresolved=_risk_references(scope,amendment['raw'])
        details.update(risk_section_references=references,unresolved_risk_section_references=unresolved)
        _need(not unresolved,'RISK_AMENDMENT_RISK_SECTION_REFERENCE_UNRESOLVED')
    except (AmendmentScopeError,ValueError) as error:
        issues.append({'reason':str(error),'error_type':type(error).__name__})
    body=exact_json_value({'record_type':'RISK_HEADING_AMENDMENT_INPUT_SCOPE','schema_version':1,
        'company_id':company_id,'cik':str(int(cik)),'metric_ids':['D01'],'input_class':INPUT_CLASS,
        'classification':'PART_III_ADDITION_WITH_NO_AMENDED_ITEM_1A' if not issues else 'UNRESOLVED',
        'decision':'PROPOSED_INPUT_SCOPE' if not issues else 'WITHHELD',
        'development_proposal_only':True,
        'fiscal_window_unchanged':scope['fiscal_window_unchanged'],
        'original':{k:old[k] for k in ('filing','period','raw_sha256','source_reference')},
        'amendment':{k:new[k] for k in ('filing','period','raw_sha256','source_reference')},
        'source_scope':scope,'details':details,'issues':issues,
        'whole_amendment_semantic_no_effect_asserted':False,
        'financial_input_clearance':False,'subject_continuity_proven':False,
        'metric_result_created':False,'source_acquisition_credit':False,'production_authorized':False})
    return {**body,'scope_id':content_hash(value=body)}


def inspect_risk_heading_amendment(*, original, amendment, company_id, cik):
    """Retain the source assessment without granting unfinished route credit.

    The bounded development batch has an unclosed named-reference coverage
    error. A structurally clean source is a proposal, never current D01 input
    permission. This public gate must stay closed until a different adequately
    validated source-impact method replaces the stopped list recognizer.
    """
    proposal=_assess_risk_heading_amendment(original=original,amendment=amendment,
        company_id=company_id,cik=cik)
    body={k:v for k,v in proposal.items() if k!='scope_id'}
    body.update(decision='WITHHELD',assessment_decision=proposal['decision'],
        proposal_scope_id=proposal['scope_id'],validation_route_suspended=True,
        issues=[*proposal['issues'],{'reason':'RISK_AMENDMENT_INPUT_ROUTE_SUSPENDED_REFERENCE_COVERAGE',
                                    'error_type':'IncompleteSourceImpactValidation'}])
    return {**body,'scope_id':content_hash(value=body)}
