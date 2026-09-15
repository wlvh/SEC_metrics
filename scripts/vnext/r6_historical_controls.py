"""Declared historical primary-document controls, never current metric inputs."""
from pathlib import Path
import re

from sec_urls import submissions_url,submissions_file_url,accession_document_url,hdr_sgml_url
from .canonical import content_hash,strict_json_file,strict_json_loads,sha256_bytes,sha256_file
from .normal_source_authority import ROOT
from .normal_annual_input import _registry_rows
from .normal_governance_input import _filings,_history_index,history_body_alignment
from .normal_source_requirements import _Requirements

POLICY_PATH='config/r6_historical_control_sources_v1.json'


def need(condition,reason):
    if not condition:raise ValueError(reason)


def discover_control_sources(*,repo_root,company_id,control_id):
    policy=strict_json_file(path=ROOT/POLICY_PATH)
    controls=[c for c in policy['controls'] if c['control_id']==control_id and c['company_id']==company_id]
    need(len(controls)==1,'CONTROL_SOURCE_NOT_CONFIGURED')
    control=controls[0];companies=[c for c in _registry_rows(repo_root=ROOT) if c['company_id']==company_id]
    need(len(companies)==1,'CONTROL_COMPANY_NOT_REGISTERED');company=companies[0];cik=company['primary_cik']
    plan=_Requirements(Path(repo_root),company)
    inventory=plan.require(submissions_url(cik=int(cik)),'sec_submissions_inventory','application/json')
    filing=None;limitations=[];rows=[]
    if inventory is not None:
        data=strict_json_loads(text=inventory['raw_bytes'].decode())
        shards=_history_index(data,cik);rows=_filings(data,inventory_name=inventory['source_reference']['document_name'])
        for shard in shards:
            if shard['filingTo']<control['report_date']:continue
            source=plan.require(submissions_file_url(file_name=shard['name']),'sec_submissions_history','application/json')
            if source is None:
                limitations.append('CONTROL_RELEVANT_HISTORY_MISSING:'+shard['name']);continue
            additional=_filings(strict_json_loads(text=source['raw_bytes'].decode()),inventory_name=shard['name'])
            problem=history_body_alignment(shard=shard,rows=additional)
            if problem:limitations.append('CONTROL_HISTORY_CONFLICT:'+problem)
            rows.extend(additional)
        chosen=[f for f in rows if f['form']=='10-K' and f.get('reportDate')==control['report_date']]
        need(len(chosen)==1,'CONTROL_ANNUAL_FILING_NOT_UNIQUE_IN_SAVED_METADATA')
        filing=chosen[0]
        need(filing['filingDate']>=filing['reportDate'],'CONTROL_FILING_PRECEDES_REPORT_END')
        if not limitations:
            accession=filing['accessionNumber']
            plan.require(accession_document_url(cik=int(cik),accession=accession,document_name=filing['primaryDocument']),
                         'target_primary','text/html',accession)
            plan.require(hdr_sgml_url(cik=int(cik),accession=accession),'historical_control_header','text/plain',accession)
    body={'record_type':'HISTORICAL_SEMANTIC_CONTROL_REQUIREMENTS','company_id':company_id,'control_id':control_id,
        'control':control,'filing':filing,'requirements':list(plan.requests.values()),'limitations':limitations,
        'metadata_source_proofs':[v['proof'] for v in plan.reader.proofs.values()],
        'scope':'EXACT_HISTORICAL_PRIMARY_AND_HEADER_ONLY_NOT_LATEST_ANNUAL_OR_WHOLE_FILING',
        'normal_update_input':False,'native_result_created':False,'production_authorized':False}
    return {**body,'requirements_id':content_hash(value=body)}


def prepare_control_source(*,repo_root,company_id,control_id):
    """Complete selected historical HTML, with SEC-header identity proof.

    This has no companion-XBRL/whole-filing absence or current-result credit.
    Ordinary inline-identity rules are not weakened or reused for this mode.
    """
    from .text_coverage import _Blocks,_byte_offsets
    from .r6_semantic_source import _group
    from .regulatory_investigation_candidates import _quotation_ranges
    from .normal_governance_input import _Sources
    from .ordinary_source_authority import verify_ordinary_source_proofs
    discovery=discover_control_sources(repo_root=repo_root,company_id=company_id,control_id=control_id)
    need(not discovery['limitations'] and all(r['saved_status']=='VERIFIED_SAVED_SOURCE' for r in discovery['requirements']),
         'CONTROL_ORIGINAL_SOURCES_NOT_AVAILABLE')
    filing=discovery['filing'];need(filing['isInlineXBRL']==0,'CONTROL_EXPECTS_NONINLINE_HISTORICAL_PRIMARY')
    company=next(c for c in _registry_rows(repo_root=ROOT) if c['company_id']==company_id);cik=company['primary_cik']
    reader=_Sources(Path(repo_root),company_id,cik);primary=reader.primary(filing)
    header=reader.read(hdr_sgml_url(cik=int(cik),accession=filing['accessionNumber']),
        role='historical_control_header',accession=filing['accessionNumber'],media_type='text/plain')
    raw_header=header['raw_bytes'].decode('utf-8-sig');raw=primary['raw_bytes'];text=raw.decode('utf-8-sig')
    def one(tag):
        values=re.findall(r'<'+tag+r'>([^\r\n<>]*)',raw_header,re.I)
        need(len(values)==1,'CONTROL_HEADER_FIELD_NOT_UNIQUE:'+tag);return values[0].strip()
    need(one('ACCESSION-NUMBER')==filing['accessionNumber'] and one('TYPE')==one('FORM-TYPE')=='10-K'
         and int(one('CIK'))==int(cik) and one('PERIOD')==filing['reportDate'].replace('-','')
         and one('FILING-DATE')==filing['filingDate'].replace('-',''), 'CONTROL_HEADER_IDENTITY_CHANGED')
    name=one('CONFORMED-NAME');parser=_Blocks(text);parser.feed(text);parser.close();parser._flush()
    need(not parser.structural_errors and (parser.html_count,parser.body_count,parser.html_closed,parser.body_closed)==(1,1,1,1),
         'CONTROL_PRIMARY_STRUCTURE_INCOMPLETE')
    compact=lambda s:re.sub(r'[^a-z0-9]','',s.casefold())
    need(compact(name) in compact(' '.join(b['text'] for b in parser.blocks[:100])),
         'CONTROL_PRIMARY_HEADER_REGISTRANT_MISMATCH')
    bom=3 if raw.startswith(b'\xef\xbb\xbf') else 0
    offsets=_byte_offsets(text,[p for b in parser.blocks for p in (b['start'],b['end'])]);quoted=_quotation_ranges(raw)
    blocks=[]
    for index,b in enumerate(parser.blocks):
        start,end=offsets[b['start']]+bom,offsets[b['end']]+bom
        blocks.append({'block_index':index,'text':b['text'],'raw_start_byte':start,'raw_end_byte':end,
            'raw_span_sha256':sha256_bytes(content=raw[start:end]),
            'html_quotation_context':any(a<end and start<z for a,z in quoted)})
    document_id=content_hash(value={'primary':primary['source_reference'],'header':header['source_reference'],
        'filing':filing,'blocks':blocks,'scope':discovery['scope']})
    units=_group(blocks,lambda rows:{'blocks':rows},document_id,'VISIBLE_TEXT')
    language=re.compile(strict_json_file(path=ROOT/'catalog/r6/going_concern_source_rules_v1.json')['language_pattern'],re.I)
    document={'document_id':document_id,'filing':filing,'source_reference':primary['source_reference'],
        'raw_blob':primary['raw_blob'],'registrant_name_binding':{'basis':'SEC_METADATA_HEADER_AND_PRIMARY_COVER',
            'registrant_name':name,'cik':cik,'header_source_reference':header['source_reference']},
        'language_candidate_block_indices':[b['block_index'] for b in blocks if language.search(b['text'])],
        'native_candidate_ordinals':[],'source_unit_ids':[u['unit_id'] for u in units],
        'native_scope':'COMPANION_XBRL_NOT_INCLUDED_IN_THIS_PRIMARY_DOCUMENT_CONTROL'}
    proofs=discovery['metadata_source_proofs'];admission=verify_ordinary_source_proofs(data_root=Path(repo_root),proofs=proofs)
    fiscal_year=int(filing['reportDate'][:4])
    prepared={'entity':cik,'table_input':{'target_period':{'period_start':None,'period_end':filing['reportDate'],
        'fiscal_year':fiscal_year,'basis':'HISTORICAL_REPORT_END_ONLY_NO_NUMERIC_DURATION_CLAIM'}},
        'fiscal_year_label_resolution':{'selected_fiscal_year':fiscal_year,'basis':'DECLARED_ANNUAL_REPORT_PERIOD',
            'original_dei_fiscal_year':None,'original_companyfacts_fiscal_year_values':[],
            'metadata_conflict_retained':False}}
    body={'record_type':'D04_HISTORICAL_PRIMARY_CONTROL_SOURCE','metric_id':'D04','company_id':company_id,
        'prepared_annual_input':prepared,'documents':[document],'units':units,
        'required_unit_ids':[u['unit_id'] for u in units],'source_proofs':proofs,'source_admission':admission,
        'control':discovery['control'],'control_scope':discovery['scope'],'source_serialization_complete':True,
        'source_freshness_verified':False,'whole_filing_absence_credit':False,'normal_update_input':False,
        'semantic_coverage_verified':False,'native_result_created':False,'production_authorized':False,
        'control_module_sha256':sha256_file(path=Path(__file__)),'calls':{'provider':0,'paid':0,'sec':0}}
    return {**body,'semantic_source_id':content_hash(value=body)}
