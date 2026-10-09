"""Finite ordinary amendment scope proofs from original and amended filings.

This additive source component is not wired into the running V14 batch. It
distinguishes fiscal-window identity, unchanged original statement input and
governance/legal/debt interpretation. No metric value or Run is created here.
"""
from html.parser import HTMLParser
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from sec_urls import accession_document_url
from .annual_update import saved_source
from .canonical import content_hash, sha256_bytes, strict_json_file
from .deterministic_router import parse_accession_xbrl_source
from .normal_annual_input import prepare_saved_annual_input
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .sources import raw_blob_record, source_reference_record, resolve_repository_file
from .text_coverage import build_text_document
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .fiscal_year_labels import _DefinitionBlocks


POLICY_PATH = "config/annual_amendment_scope_v1.json"
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


class AmendmentScopeError(ValueError):
    pass


def _need(condition, reason):
    if not condition:raise AmendmentScopeError(reason)


def _norm(text):
    return " ".join(text.split())


class _Links(HTMLParser):
    def __init__(self, text, url):
        super().__init__()
        self.text,self.url=text,url
        self.lines=[0]+[m.end() for m in re.finditer('\n',text)]
        self.active=None;self.rows=[]

    def _offset(self):
        line,column=self.getpos();return self.lines[line-1]+column

    def handle_starttag(self, tag, attrs):
        if tag=='a':
            _need(self.active is None,"AMENDMENT_NESTED_ANCHOR")
            self.active={'href':dict(attrs).get('href',''),'parts':[],'start':self._offset()}

    def handle_data(self,data):
        if self.active is not None:self.active['parts'].append(data)

    def handle_endtag(self,tag):
        if tag=='a' and self.active is not None:
            item=self.active;self.active=None
            if item['href'] and not item['href'].startswith('#'):
                self.rows.append({'text':_norm(''.join(item['parts'])),'url':urljoin(self.url,item['href'])})


def _source(*, raw, blob, reference, filing, company_id, cik, period_end):
    doc=build_text_document(raw_bytes=raw,raw_blob=blob,source_reference=reference,
        expected_company_id=company_id,expected_cik=cik,expected_period_end=period_end)
    _need(set(doc['source_reasons']) <= {'TEXT_AMENDMENT_SOURCE_SET_REQUIRED'},"AMENDMENT_FULL_DOCUMENT_REQUIRED")
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    metadata=_ReportedFactMetadata();metadata.feed(raw.decode('utf-8-sig'));metadata.close()
    _need(metadata.ordinal==len(parsed.facts),"AMENDMENT_NATIVE_STREAM_CHANGED")
    keys={'entitycentralindexkey','documenttype','documentperiodenddate','documentfiscalyearfocus','documentfiscalperiodfocus'}
    identity=[];flags=[];other_facts=[]
    for fact in parsed.facts:
        meta=metadata.facts[fact['ordinal']];uri,local=meta['concept']
        dei=re.fullmatch(r'https?://xbrl\.sec\.gov/dei/[0-9]{4}',uri) is not None
        if dei and local.casefold()=='amendmentflag':flags.append(fact['text'])
        if dei and local.casefold() in keys:
            native={**parsed.contexts[fact['context_ref']],'dimensions':dict(parsed.contexts[fact['context_ref']]['dimensions'])}
            proof=_verified_context(native=native,metadata=metadata)
            _need(str(native['entity_identifier']).isdigit() and int(native['entity_identifier'])==int(cik)
                  and not native['dimensions'],"AMENDMENT_IDENTITY_CONTEXT_DIFFERS")
            identity.append({'name':local.casefold(),'value':fact['text'],'context':native,'context_proof':proof,'ordinal':fact['ordinal']})
        elif not dei:
            other_facts.append({'concept':[uri,local],'ordinal':fact['ordinal'],'text':fact['text'],'unit_ref':fact['unit_ref']})
    by_name={key:[f for f in identity if f['name']==key] for key in keys}
    _need(all(len(v)==1 for v in by_name.values()),"AMENDMENT_IDENTITY_FACT_SET_NOT_UNIQUE")
    _need(by_name['documenttype'][0]['value']==filing['form'],"AMENDMENT_FORM_IDENTITY_DIFFERS")
    intervals={(f['context']['period_start'],f['context']['period_end']) for f in identity}
    _need(len(intervals)==1,"AMENDMENT_IDENTITY_PERIODS_CONFLICT")
    start,end=next(iter(intervals))
    _need(end==period_end,"AMENDMENT_PERIOD_END_DIFFERS")
    links=_Links(raw.decode('utf-8-sig'),reference['source_url']);links.feed(raw.decode('utf-8-sig'));links.close()
    _need(links.active is None,"AMENDMENT_UNCLOSED_ANCHOR")
    quotations=_DefinitionBlocks(raw.decode('utf-8-sig'));quotations.feed(raw.decode('utf-8-sig'));quotations.close();quotations._flush()
    _need([b['text'] for b in quotations.blocks]==[b['text'] for b in doc['blocks']],"AMENDMENT_QUOTATION_BLOCK_STREAM_CHANGED")
    return {'document':doc,'identity':identity,'period':{'period_start':start,'period_end':end},
        'raw_amendment_flag_values':sorted(set(flags)),'non_dei_native_facts':other_facts,'links':links.rows,
        'quoted_block_indices':[i for i,b in enumerate(quotations.blocks) if b['quoted_context']],
        'raw_sha256':sha256_bytes(content=raw),'filing':filing,'source_reference':reference}


def _note(doc):
    blocks=doc['blocks'];indices=[i for i,b in enumerate(blocks) if not b['linked'] and re.fullmatch(POLICY['explanatory_heading_pattern'],b['text'],re.I)]
    _need(len(indices)==1,"AMENDMENT_EXPLANATORY_NOTE_NOT_UNIQUE")
    start=indices[0]
    end=next((i for i in range(start+1,len(blocks)) if re.fullmatch(POLICY['part_heading_pattern'],blocks[i]['text'],re.I)
        or blocks[i]['text'].upper().startswith('CAUTIONARY NOTE')),len(blocks))
    _need(start+1<end and end-start<=8,"AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED")
    return {'start':start,'end':end,'blocks':blocks[start:end],'text':' '.join(b['text'] for b in blocks[start+1:end])}


def _item15(doc):
    blocks=doc['blocks']
    parts=[i for i,b in enumerate(blocks) if not b['linked'] and re.fullmatch(r'PART\s+IV',b['text'],re.I)]
    _need(bool(parts),'AMENDMENT_PART_IV_NOT_FOUND')
    # The table of contents can repeat an unlinked Item15 label; its earlier
    # PartIV is not the document's actual final PartIV body.
    part=max(parts)
    starts=[i for i,b in enumerate(blocks) if i>part and not b['linked'] and re.match(r'Item\s+15\.',b['text'],re.I)]
    _need(len(starts)==1,"AMENDMENT_ITEM15_NOT_UNIQUE")
    start=starts[0];end=next((i for i in range(start+1,len(blocks)) if re.match(r'Item\s+16\.',blocks[i]['text'],re.I)
        or blocks[i]['text'].upper()=='SIGNATURES'),len(blocks))
    result=[];omitted=[];i=start
    while i<end:
        # Only an actual page-number/linked-TOC pair may disappear from a copy.
        if (i+1<end and re.fullmatch(r'[0-9]+',blocks[i]['text'])
                and blocks[i+1]['text'].casefold()=='table of contents' and blocks[i+1]['linked']):
            omitted.extend(blocks[i:i+2]);i+=2;continue
        result.append(blocks[i]);i+=1
    return {'blocks':result,'pagination_omitted':omitted,'start':start,'end':end}


def inspect_annual_amendment_scope(*, original, amendment, company_id, cik):
    """Inspect hash-bound source arguments; this pure API grants no acquisition."""
    _need(original['filing']['form']=='10-K' and amendment['filing']['form']=='10-K/A',"AMENDMENT_SOURCE_FORMS_REQUIRED")
    end=original['filing']['reportDate']
    _need(amendment['filing']['reportDate']==end and amendment['filing']['filingDate']>=original['filing']['filingDate'],
          "AMENDMENT_SAME_FILING_PERIOD_REQUIRED")
    old=_source(**original,company_id=company_id,cik=cik,period_end=end)
    new=_source(**amendment,company_id=company_id,cik=cik,period_end=end)
    period_equal=old['period']==new['period']
    note=_note(new['document']);text=note['text']
    unquoted=not (set(range(note['start'],note['end'])) & set(new['quoted_block_indices']))
    has_no_change=any(re.search(pattern,text,re.I) for pattern in POLICY['no_change_patterns'])
    rule='UNRESOLVED';details={};issues=[]
    link=re.search(POLICY['link_purpose_pattern'],text,re.I)
    part3=re.search(POLICY['part_iii_purpose_pattern'],text,re.I)
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
        def words(value):
            return ' '.join(re.sub(r'[^a-z0-9\s]',' ',value.casefold()).split())
        named_subject=any(words(first).startswith(words(name)+' the company is filing this amendment no ')
                          for name in new['document']['registrant_names'])
        # Do not accept an extra purpose hidden behind "unless expressly
        # stated". The remaining paragraphs must be the bounded certificates.
        exact_note=(first_link is not None and named_subject and suffix==POLICY['link_note_disclaimer']
                    and len(paragraphs)==2 and re.fullmatch(POLICY['certification_note_pattern'],paragraphs[1]['text'],re.I) is not None)
        blocks=new['document']['blocks']
        between=[x['text'] for x in blocks[note['end']:b['start']]]
        signature=blocks[b['end']:]
        signature_match=(re.fullmatch(POLICY['signature_tail_pattern'],' '.join(x['text'] for x in signature[3:]))
                         if len(signature)>=4 else None)
        signature_ok=(len(signature)>=4 and signature[0]['text']=='SIGNATURES'
                      and signature[1]['text']==POLICY['signature_preamble']
                      and any(words(signature[2]['text'])==words(name) for name in new['document']['registrant_names'])
                      and signature_match is not None)
        if signature_ok:
            signature_ok=datetime.strptime(signature_match['date'],'%B %d, %Y').date().isoformat()==new['filing']['filingDate']
        layout_ok=between==['PART IV'] and signature_ok
        details={'item15_visible_text_equal':texts_equal,'cover_equal_except_amendment_banner':cover_equal,
            'original_item15':a,'amended_item15':b,'exhibit':link.group('exhibit'),'changed_link_texts':sorted(changed_names),
            'removed_links':sorted(removed),'added_links':sorted(added),'only_declared_exhibit_and_certificate_links':allowed and paired}
        details['complete_note_has_only_link_correction_and_certifications']=exact_note
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
    body=exact_json_value(body)
    return {**body,'scope_id':content_hash(value=body)}


def prepare_saved_amendment_scopes(*, repo_root: Path, company_id: str):
    prepared=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    proofs=list(prepared['source_proofs']);sources=[]
    for filing in [prepared['filing'],*prepared['amendments']]:
        url=accession_document_url(cik=int(prepared['entity']),accession=filing['accessionNumber'],document_name=filing['primaryDocument'])
        saved=saved_source(repo_root=repo_root,url=url,accession=filing['accessionNumber'])
        _need(saved is not None,'AMENDMENT_SOURCE_NOT_SAVED:'+url)
        proof=saved['proof'];proofs.append(proof)
        blob=raw_blob_record(repo_root=repo_root,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
        reference=source_reference_record(raw_blob=blob,company_id=company_id,source_url=url,accession=filing['accessionNumber'],
            document_name=filing['primaryDocument'],source_role='annual_source_identity',request_attempt_id=proof['request_attempt_id'])
        sources.append({'raw':saved['raw'],'blob':blob,'reference':reference,'filing':filing})
    proofs=list({content_hash(value=p):p for p in proofs}.values())
    admission=verify_saved_source_proofs(data_root=repo_root,proofs=proofs)
    scopes=[inspect_annual_amendment_scope(original=sources[0],amendment=s,company_id=company_id,cik=prepared['entity']) for s in sources[1:]]
    return {'prepared_input':prepared,'source_proofs':proofs,'source_admission':admission,'scopes':scopes,
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
