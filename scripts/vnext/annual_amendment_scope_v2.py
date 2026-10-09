"""Explicit paragraph successor; old source readers remain readable unchanged."""
import re
from datetime import datetime
from . import annual_amendment_scope as legacy
from .annual_amendment_scope import (AmendmentScopeError, POLICY, _need, _source,
    _words, _item15, _link_note_identity)
from .canonical import content_hash
from .normal_annual_input_v2 import exact_json_value

def _note(doc, raw=None):
    blocks=doc['blocks'];indices=[i for i,b in enumerate(blocks) if not b['linked'] and re.fullmatch(POLICY['explanatory_heading_pattern'],b['text'],re.I)]
    _need(len(indices)==1,"AMENDMENT_EXPLANATORY_NOTE_NOT_UNIQUE")
    start=indices[0]
    end=next((i for i in range(start+1,len(blocks)) if re.fullmatch(POLICY['part_heading_pattern'],blocks[i]['text'],re.I)
        or blocks[i]['text'].upper().startswith('CAUTIONARY NOTE')),len(blocks))
    count = end-start
    if raw is not None:
        from .amendment_note_layout import paragraph_blocks
        count = 1 + len(paragraph_blocks(blocks[start+1:end], raw))
    _need(start+1<end and count<=8,"AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED")
    text=' '.join(b['text'] for b in blocks[start+1:end])
    if raw is not None:
        from .amendment_note_layout import paragraph_text
        text=' '.join(paragraph_text(group,raw) for group in paragraph_blocks(blocks[start+1:end],raw))
    return {'start':start,'end':end,'blocks':blocks[start:end],'text':text}

def inspect_annual_amendment_scope(*, original, amendment, company_id, cik,
                                   note_layout='blocks-v1'):
    """Inspect hash-bound source arguments; this pure API grants no acquisition."""
    if note_layout == 'blocks-v1':
        return legacy.inspect_annual_amendment_scope(original=original, amendment=amendment, company_id=company_id, cik=cik)
    _need(note_layout in {'blocks-v1','inline-paragraphs-v2'}, 'AMENDMENT_NOTE_LAYOUT_UNSUPPORTED')
    _need(original['filing']['form']=='10-K' and amendment['filing']['form']=='10-K/A',"AMENDMENT_SOURCE_FORMS_REQUIRED")
    end=original['filing']['reportDate']
    _need(amendment['filing']['reportDate']==end and amendment['filing']['filingDate']>=original['filing']['filingDate'],
          "AMENDMENT_SAME_FILING_PERIOD_REQUIRED")
    old=_source(**original,company_id=company_id,cik=cik,period_end=end)
    new=_source(**amendment,company_id=company_id,cik=cik,period_end=end)
    period_equal=old['period']==new['period']
    note=_note(new['document'], **({'raw':amendment['raw']} if note_layout!='blocks-v1' else {}));text=note['text']
    unquoted=not (set(range(note['start'],note['end'])) & set(new['quoted_block_indices']))
    has_no_change=any(re.search(pattern,text,re.I) for pattern in POLICY['no_change_patterns'])
    rule='UNRESOLVED';details={};issues=[]
    link=re.search(POLICY['link_purpose_pattern'],text,re.I)
    part3_pattern=POLICY['part_iii_purpose_pattern']
    if note_layout!='blocks-v1':
        from .amendment_note_layout import part_iii_pattern
        part3_pattern=part_iii_pattern(part3_pattern)
    part3=re.search(part3_pattern,text,re.I)
    if link and has_no_change and unquoted:
        a,b=_item15(old['document']),_item15(new['document'])
        texts_equal=[x['text'] for x in a['blocks']]==[x['text'] for x in b['blocks']]
        # The amended cover must be the original cover with only the form and
        # amendment-number banner changed. No extra financial prose is dropped.
        cover=[b['text'] for b in new['document']['blocks'][:note['start']]]
        normalized=[t.replace('FORM 10-K/A','FORM 10-K') for t in cover if re.fullmatch(r'Amendment No\. [0-9]+',t,re.I) is None]
        original_cover=[b['text'] for b in old['document']['blocks'][:len(normalized)]]
        cover_equal=normalized==original_cover
        old_links={(x['text'],x['url']) for x in old['links']};new_links={(x['text'],x['url']) for x in new['links']}
        removed=old_links-new_links;added=new_links-old_links
        changed_names={x[0] for x in removed|added}
        description=re.sub(r'^the\s+','',link.group('description'),flags=re.I)
        corrected=[name for name in changed_names if name.startswith(description)]
        allowed= len(corrected)==1 and all(name in corrected or re.search(POLICY['certificate_link_pattern'],name,re.I) for name in changed_names)
        paired=all(sum(x[0]==name for x in removed)==sum(x[0]==name for x in added)==1 for name in changed_names)
        paragraphs=note['blocks'][1:]
        first=paragraphs[0]['text']
        first_link=re.search(POLICY['link_purpose_pattern'],first,re.I)
        suffix=first[first_link.end():].strip() if first_link else ''
        note_identity = _link_note_identity(first, first_link, new)
        exhibit_rows = [i for i, block in enumerate(b['blocks'])
                        if block['text'] in corrected]
        exhibit_bound = (len(exhibit_rows) == 1 and exhibit_rows[0] > 0
                         and b['blocks'][exhibit_rows[0]-1]['text'] == link.group('exhibit'))
        # Do not accept an extra purpose hidden behind "unless expressly
        # stated". The remaining paragraphs must be the bounded certificates.
        exact_note=(first_link is not None and note_identity and exhibit_bound and suffix==POLICY['link_note_disclaimer']
                    and len(paragraphs)==2 and re.fullmatch(POLICY['certification_note_pattern'],paragraphs[1]['text'],re.I) is not None)
        blocks=new['document']['blocks']
        between=[x['text'] for x in blocks[note['end']:b['start']]]
        signature=blocks[b['end']:]
        signature_match=(re.fullmatch(POLICY['signature_tail_pattern'],' '.join(x['text'] for x in signature[3:]))
                         if len(signature)>=4 else None)
        signature_ok=(len(signature)>=4 and signature[0]['text']=='SIGNATURES'
                      and signature[1]['text']==POLICY['signature_preamble']
                      and any(_words(signature[2]['text'])==_words(name) for name in new['document']['registrant_names'])
                      and signature_match is not None)
        if signature_ok:
            signature_ok=datetime.strptime(signature_match['date'],'%B %d, %Y').date().isoformat()==new['filing']['filingDate']
        layout_ok=between==['PART IV'] and signature_ok
        details={'item15_visible_text_equal':texts_equal,'cover_equal_except_amendment_banner':cover_equal,
            'original_item15':a,'amended_item15':b,'exhibit':link.group('exhibit'),'changed_link_texts':sorted(changed_names),
            'removed_links':sorted(removed),'added_links':sorted(added),'only_declared_exhibit_and_certificate_links':allowed and paired}
        details['complete_note_has_only_link_correction_and_certifications']=exact_note
        details['note_subject_period_and_amendment_number_match_source'] = note_identity
        details['declared_exhibit_matches_changed_link_row'] = exhibit_bound
        details['remaining_body_is_part_iv_and_bound_signature']=layout_ok
        if texts_equal and cover_equal and allowed and paired and exact_note and layout_ok and not new['non_dei_native_facts']:
            rule='EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15'
        else:issues.append('EXHIBIT_CORRECTION_HAS_UNRECONCILED_SOURCE_DIFFERENCES')
    elif part3 and has_no_change and unquoted:
        headings=[b for b in new['document']['blocks'] if not b['linked'] and re.fullmatch(POLICY['part_heading_pattern'],b['text'],re.I)]
        parts={b['text'].upper() for b in headings}
        item_headers=[b for b in new['document']['blocks'] if not b['linked'] and re.match(POLICY['item_heading_pattern'],b['text'],re.I)]
        items={re.match(POLICY['item_heading_pattern'],b['text'],re.I).group(1) for b in item_headers}
        statements=[b for b in new['document']['blocks'] if re.search(POLICY['no_financial_statement_pattern'],b['text'],re.I)]
        details={'parts':sorted(parts),'items':sorted(items),'no_new_financial_statement_declarations':statements}
        only_governance_facts=all(re.fullmatch(r'https?://xbrl\.sec\.gov/ecd/[0-9]{4}',f['concept'][0]) for f in new['non_dei_native_facts'])
        details['non_dei_facts_are_governance_taxonomy']=only_governance_facts
        if parts=={'PART III','PART IV'} and items=={'10','11','12','13','14','15'} and len(statements)==1 and only_governance_facts:
            rule='PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS'
        else:issues.append('PART_III_ONLY_SOURCE_SCOPE_NOT_PROVEN')
    else:issues.append('AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN')
    if not period_equal:issues.append('AMENDMENT_FISCAL_WINDOW_CHANGED')
    permitted = rule!='UNRESOLVED' and period_equal and not issues
    unchanged=[POLICY['event_input_class']] if period_equal else []
    if permitted and rule=='EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15':
        unchanged.append(POLICY['original_statement_input_class'])
    body={'record_type':'ANNUAL_AMENDMENT_SOURCE_SCOPE','schema_version':1,'company_id':company_id,
        'original':old,'amendment':new,'explanatory_note':note,'classification':rule,'details':details,'issues':issues,
        'fiscal_window_unchanged':period_equal,'unchanged_input_classes':unchanged,
        'original_statement_admission_requires_further_review':not (permitted and rule=='EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15'),
        'not_covered_metric_ids':POLICY['not_covered_metric_ids'],'policy_hash':content_hash(value=POLICY),
        'source_acquisition_credit':False,'native_run_created':False,'production_authorized':False}
    if note_layout!='blocks-v1':body['note_layout']=note_layout
    body=exact_json_value(body)
    return {**body,'scope_id':content_hash(value=body)}
