"""Limited Part III amendment effect on original current-instant balances.

The older amendment proof remains unchanged. This successor checks the entire
limited-purpose note, native correction flag, explicit no-statements Item 15,
and unresolved financial correction language. It never grants annual, debt,
governance or acquisition approval.
"""
from datetime import datetime
from pathlib import Path
import re

from .annual_amendment_scope import inspect_annual_amendment_scope,prepare_saved_amendment_scopes,_words
from .canonical import content_hash,sha256_file,strict_json_file
from .deterministic_router import parse_accession_xbrl_source
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata,_verified_context

POLICY_PATH='config/instant_balance_amendment_v1.json'
POLICY=strict_json_file(path=ROOT/POLICY_PATH)


class InstantAmendmentError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise InstantAmendmentError(reason)


def _correction_flag(raw,scope):
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    metadata=_ReportedFactMetadata();metadata.feed(raw.decode('utf-8-sig'));metadata.close()
    _need(metadata.ordinal==len(parsed.facts),'INSTANT_AMENDMENT_NATIVE_STREAM_CHANGED')
    found=[]
    for fact in parsed.facts:
        meta=metadata.facts[fact['ordinal']];uri,name=meta['concept']
        if name!=POLICY['error_correction_concept']:continue
        _need(re.fullmatch(r'https?://xbrl\.sec\.gov/dei/[0-9]{4}',uri) is not None,
              'INSTANT_AMENDMENT_CORRECTION_FLAG_NAMESPACE')
        ctx=parsed.contexts[fact['context_ref']];native={**ctx,'dimensions':dict(ctx['dimensions'])}
        context_proof=_verified_context(native=native,metadata=metadata)
        fmt=meta['attrs'].get('format','').split(':')
        _need(len(fmt)==2 and meta['namespaces'].get(fmt[0])=='http://www.sec.gov/inlineXBRL/transformation/2015-08-31'
              and fmt[1]=='boolballotbox' and fact['text']=='☐',
              'INSTANT_AMENDMENT_CORRECTION_FLAG_NOT_EXPLICITLY_FALSE')
        _need(str(native['entity_identifier']).isdigit()
              and int(native['entity_identifier'])==int(scope['amendment']['document']['cik'])
              and not native['dimensions'] and not native['typed_dimension_count']
              and {k:native[k] for k in ('period_start','period_end')}==scope['amendment']['period'],
              'INSTANT_AMENDMENT_CORRECTION_FLAG_CONTEXT')
        found.append({'fact':dict(fact),'namespace':uri,'native_context':native,'context_proof':context_proof})
    _need(len(found)==1,'INSTANT_AMENDMENT_CORRECTION_FLAG_NOT_UNIQUE')
    return found[0]


def _part_iii_details(scope,raw):
    note=scope['explanatory_note'];new=scope['amendment'];old=scope['original']
    match=re.fullmatch(POLICY['part_iii_note_pattern'],note['text'])
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
    corrections=[b for b in blocks[:note['start']] if re.fullmatch(POLICY['error_correction_cover_pattern'],b['text'])]
    _need(len(corrections)==1 and corrections[0]['block_index'] not in quoted,
          'INSTANT_AMENDMENT_CORRECTION_COVER_UNSUPPORTED')
    restatements=[b for b in blocks[:note['start']] if re.fullmatch(POLICY['restatement_cover_pattern'],b['text'])]
    _need(len(restatements)==1 and restatements[0]['block_index'] not in quoted,
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
    conflicts=[];conditionals=[]
    for block in blocks:
        if block['block_index']==corrections[0]['block_index']:continue
        text=block['text']
        if re.search(POLICY['balance_statement_pattern'],text,re.I):
            conflicts.append(block);continue
        if not financial.search(text) or not revision.search(text):continue
        remaining=text
        for pattern in POLICY['conditional_recovery_patterns']:
            for m in list(re.finditer(pattern,remaining,re.I))[::-1]:
                tail=remaining[m.end():]
                if re.search(POLICY['current_status_suffix_pattern'],tail,re.I):continue
                conditionals.append({'block':block,'conditional_clause':m[0]})
                remaining=remaining[:m.start()]+remaining[m.end():]
        if financial.search(remaining) and revision.search(remaining):conflicts.append(block)
    _need(not conflicts,'INSTANT_AMENDMENT_FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED:'+
          ','.join(str(b['block_index']) for b in conflicts))
    return {'note_identity':dict(match.groupdict()),'correction_cover':corrections[0],'restatement_cover':restatements[0],
            'native_correction_flag':flag,'no_new_statements_declaration':declarations[0],
            'conditional_compensation_references':conditionals,'unresolved_correction_blocks':conflicts}


def inspect_instant_balance_amendment(*,original,amendment,company_id,cik):
    scope=inspect_annual_amendment_scope(original=original,amendment=amendment,company_id=company_id,cik=cik)
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
    return {**body,'instant_scope_id':content_hash(value=body)}


def prepare_instant_balance_amendment_input(*,repo_root:Path,company_id:str):
    path=resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(path.read_bytes()==(ROOT/POLICY_PATH).read_bytes(),'INSTANT_AMENDMENT_INSTALLED_POLICY_CHANGED')
    packet=prepare_saved_amendment_scopes(repo_root=repo_root,company_id=company_id)
    blobs={r['raw_asset_id']:r for r in packet['source_records'] if r['record_type']=='RAW_BLOB'}
    checks=[]
    for scope in packet['scopes']:
        arguments={}
        for role in ('original','amendment'):
            source=scope[role];blob=blobs[source['source_reference']['raw_asset_id']]
            arguments[role]={'raw':resolve_repository_file(repo_root=repo_root,repo_relative_path=blob['storage_uri']).read_bytes(),
                             'blob':blob,'reference':source['source_reference'],'filing':source['filing']}
        checks.append(inspect_instant_balance_amendment(**arguments,company_id=company_id,cik=packet['prepared_input']['entity']))
    body=exact_json_value({**packet,'record_type':'INSTANT_BALANCE_AMENDMENT_INPUT',
        'input_class':POLICY['input_class'],'metric_ids':POLICY['metric_ids'],'checks':checks,
        'decision':'INPUT_PROPERTY_PROVEN' if all(c['decision']=='INPUT_PROPERTY_PROVEN' for c in checks) else 'WITHHELD',
        'instant_policy_sha256':sha256_file(path=path),'module_sha256':sha256_file(path=Path(__file__)),
        'annual_continuity_proven':False,'metric_result_created':False})
    return {**body,'instant_input_id':content_hash(value=body)}
