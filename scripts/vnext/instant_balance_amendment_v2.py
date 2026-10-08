"""Explicit paragraph source property; no company result or legacy re-signing."""
import re
from datetime import datetime
from . import instant_balance_amendment as legacy
from .instant_balance_amendment import (InstantAmendmentError, POLICY, POLICY_PATH,
    _need, _correction_flag)
from .annual_amendment_scope import _words
from .annual_amendment_scope_v2 import inspect_annual_amendment_scope
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT

def _text_units(blocks, raw, note_layout):
    if note_layout=='inline-paragraphs-v2':
        from .amendment_note_layout import paragraph_blocks, paragraph_text
        groups=paragraph_blocks(blocks,raw)
        return [{'text':paragraph_text(group,raw),'source_blocks':group,
                 'block_indices':[b['block_index'] for b in group]}
                for group in groups]
    return blocks

def _cover_matches(blocks, raw, pattern, note_layout):
    return [b for b in _text_units(blocks,raw,note_layout) if re.fullmatch(pattern,b['text'])]

def _part_iii_details(scope,raw):
    note=scope['explanatory_note'];new=scope['amendment'];old=scope['original']
    pattern=POLICY['part_iii_note_pattern']
    if scope.get('note_layout')=='inline-paragraphs-v2':
        from .amendment_note_layout import part_iii_pattern
        pattern=part_iii_pattern(pattern)
    match=re.fullmatch(pattern,note['text'])
    _need(match is not None,'INSTANT_AMENDMENT_COMPLETE_NOTE_UNSUPPORTED')
    _need(re.fullmatch(POLICY['alias_list_pattern'],match['aliases']) is not None,
          'INSTANT_AMENDMENT_NOTE_ALIAS_LIST_UNSUPPORTED')
    names=new['document']['registrant_names']
    _need(any(_words(match['registrant'])==_words(n)==_words(match['scope_name']) for n in names),
          'INSTANT_AMENDMENT_NOTE_SUBJECT_CONFLICT')
    _need(datetime.strptime(match['end'],'%B %d, %Y').date().isoformat()==old['filing']['reportDate']
          and datetime.strptime(match['filed'],'%B %d, %Y').date().isoformat()==old['filing']['filingDate'],
          'INSTANT_AMENDMENT_NOTE_ORIGINAL_IDENTITY_CONFLICT')
    blocks=new['document']['blocks'];quoted=set(new['quoted_block_indices'])
    banners=[b for b in blocks[:note['start']] if re.fullmatch(r'(?:Amendment No\. [0-9]+|\(Amendment No\. [0-9]+\))',b['text'])]
    expected='Amendment No. '+match['number']
    _need(len(banners)==1 and banners[0]['text'] in {expected,'('+expected+')'}
          and banners[0]['block_index'] not in quoted,
          'INSTANT_AMENDMENT_NOTE_NUMBER_CONFLICT')
    layout=scope.get('note_layout','blocks-v1')
    corrections=_cover_matches(blocks[:note['start']],raw,POLICY['error_correction_cover_pattern'],layout)
    correction_indices=(corrections[0].get('block_indices',[corrections[0].get('block_index')]) if len(corrections)==1 else [])
    _need(len(corrections)==1 and not (set(correction_indices)&quoted),
          'INSTANT_AMENDMENT_CORRECTION_COVER_UNSUPPORTED')
    restatements=_cover_matches(blocks[:note['start']],raw,POLICY['restatement_cover_pattern'],layout)
    restatement_indices=(restatements[0].get('block_indices',[restatements[0].get('block_index')]) if len(restatements)==1 else [])
    _need(len(restatements)==1 and not (set(restatement_indices)&quoted),
          'INSTANT_AMENDMENT_RESTATEMENT_COVER_UNSUPPORTED')
    declarations=scope['details']['no_new_financial_statement_declarations']
    _need(len(declarations)==1 and re.fullmatch(POLICY['no_new_statements_pattern'],declarations[0]['text'])
          and declarations[0]['block_index'] not in quoted,
          'INSTANT_AMENDMENT_NO_STATEMENTS_DECLARATION_UNSUPPORTED')
    flag=_correction_flag(raw,scope)
    # Candidate language is checked across the whole document, not just Part III
    # navigation. Only the exact conditional compensation clause is removed;
    # nearby assertions and any other correction remain in the residual text.
    financial=re.compile(POLICY['financial_subject_pattern'],re.I)
    revision=re.compile(POLICY['revision_pattern'],re.I)
    conditional_patterns=POLICY['conditional_recovery_block_patterns']
    if layout=='inline-paragraphs-v2':
        from .amendment_note_layout import conditional_recovery_patterns
        conditional_patterns=conditional_recovery_patterns(conditional_patterns)
    conflicts=[];conditionals=[]
    for block in _text_units(blocks,raw,layout):
        indices=block.get('block_indices',[block.get('block_index')])
        if set(indices)<=set(correction_indices):continue
        text=block['text']
        if re.search(POLICY['balance_statement_pattern'],text,re.I):
            conflicts.append(block);continue
        if not financial.search(text) or not revision.search(text):continue
        remaining=text
        conditional_block=(not (set(indices)&quoted) and any(
            re.fullmatch(pattern,text,re.I) for pattern in conditional_patterns))
        if not conditional_block:
            conflicts.append(block);continue
        for pattern in POLICY['conditional_recovery_patterns']:
            for m in list(re.finditer(pattern,remaining,re.I))[::-1]:
                tail=remaining[m.end():]
                if re.search(POLICY['current_status_suffix_pattern'],tail,re.I):continue
                conditionals.append({'block':block,'conditional_clause':m[0]})
                remaining=remaining[:m.start()]+remaining[m.end():]
        if financial.search(remaining) and revision.search(remaining):conflicts.append(block)
    _need(not conflicts,'INSTANT_AMENDMENT_FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED:'+
          ','.join(str(i) for b in conflicts for i in b.get('block_indices',[b.get('block_index')])))
    return {'note_identity':dict(match.groupdict()),'correction_cover':corrections[0],'restatement_cover':restatements[0],
            'native_correction_flag':flag,'no_new_statements_declaration':declarations[0],
            'conditional_compensation_references':conditionals,'unresolved_correction_blocks':conflicts}

def inspect_instant_balance_amendment(*,original,amendment,company_id,cik,
                                      note_layout='blocks-v1'):
    if note_layout == 'blocks-v1':
        return legacy.inspect_instant_balance_amendment(original=original, amendment=amendment, company_id=company_id, cik=cik)
    _need(strict_json_file(path=ROOT/POLICY_PATH)==POLICY,'INSTANT_AMENDMENT_POLICY_CHANGED_DURING_PROCESS')
    scope=inspect_annual_amendment_scope(original=original,amendment=amendment,company_id=company_id,cik=cik,
        **({} if note_layout=='blocks-v1' else {'note_layout':note_layout}))
    issues=[];details={};decision='WITHHELD'
    try:
        _need(scope['fiscal_window_unchanged'] and not scope['issues'],'INSTANT_AMENDMENT_SOURCE_SCOPE_UNRESOLVED')
        if 'ORIGINAL_STATEMENT_VALUES' in scope['unchanged_input_classes']:
            details={'inherited_unchanged_original_statement_scope':scope['scope_id']}
        else:
            _need(scope['classification']=='PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
                  'INSTANT_AMENDMENT_KIND_UNSUPPORTED')
            details=_part_iii_details(scope,amendment['raw'])
        decision='INPUT_PROPERTY_PROVEN'
    except (InstantAmendmentError,ValueError) as error:
        issues.append({'reason':str(error),'error_type':type(error).__name__})
    body=exact_json_value({'record_type':'INSTANT_BALANCE_AMENDMENT_SCOPE','company_id':company_id,
        'input_class':POLICY['input_class'],'metric_ids':POLICY['metric_ids'],'decision':decision,
        'original_scope_id':scope['scope_id'],'original_accession':original['filing']['accessionNumber'],
        'amendment_accession':amendment['filing']['accessionNumber'],'details':details,'issues':issues,
        'policy_sha256':sha256_file(path=ROOT/POLICY_PATH),'source_acquisition_credit':False,
        'annual_continuity_proven':False,'debt_completeness_proven':False,'metric_result_created':False,
        'production_authorized':False})
    if note_layout!='blocks-v1':body['note_layout']=note_layout
    return {**body,'instant_scope_id':content_hash(value=body)}
