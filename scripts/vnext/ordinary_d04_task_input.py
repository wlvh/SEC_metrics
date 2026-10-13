"""D04 change comparison over complete selected originals, never an AI answer."""
from pathlib import Path

from sec_urls import accession_document_url, submissions_url
from .annual_update import saved_source
from .canonical import content_hash, strict_json_loads
from .normal_annual_input import _registry_rows, select_filing
from .normal_annual_input_v2 import prepare_saved_annual_input
from .ordinary_source_authority import verify_ordinary_source_proofs
from .ordinary_task_input import parsed_d04_document
from .sources import raw_blob_record, source_reference_record


def fingerprint(*, source_root, company_id, prepared_annual_input=None):
    """Select/authenticate input mechanically and parse every annual document.

    No business candidate selector, request preparation, model or Calculator
    runs. Parsing is only needed for a new saved comparison or changed bytes.
    """
    root=Path(source_root)
    annual=prepared_annual_input or prepare_saved_annual_input(repo_root=root,company_id=company_id,ordinary_registered=True)
    if annual['company_id']!=company_id:
        raise ValueError('D04_TASK_INPUT_COMPANY_CHANGED')
    filings=[annual['filing'],*sorted(annual['amendments'],
        key=lambda f:(f['filingDate'],f['accessionNumber']))]
    proofs=list(annual['source_proofs']);documents=[]
    fields=('accessionNumber','form','reportDate','filingDate','primaryDocument')
    # A prepared caller cannot silently omit an amendment from the selected
    # set. Recheck the saved catalog mechanically, without metric selection,
    # model requests or calculation. Its current failed outcome still fails.
    companies=[row for row in _registry_rows(repo_root=root) if row['company_id']==company_id]
    if len(companies)!=1 or int(companies[0]['primary_cik'])!=int(annual['entity']):
        raise ValueError('D04_TASK_INPUT_ENTITY_CHANGED')
    inventory=saved_source(repo_root=root,url=submissions_url(cik=int(annual['entity'])))
    if inventory is None:raise ValueError('D04_TASK_INPUT_SELECTION_SOURCE_MISSING')
    selected=select_filing(company=companies[0],
        submissions=strict_json_loads(text=inventory['raw'].decode('utf-8')))
    expected=[selected['filing'],*sorted(selected['amendments'],
        key=lambda f:(f['filingDate'],f['accessionNumber']))]
    if [{k:f[k] for k in fields} for f in filings]!=[{k:f[k] for k in fields} for f in expected]:
        raise ValueError('D04_TASK_INPUT_SELECTION_CHANGED')
    if inventory['proof'] not in proofs:proofs.append(inventory['proof'])
    for filing in filings:
        url=accession_document_url(cik=int(annual['entity']),accession=filing['accessionNumber'],
                                   document_name=filing['primaryDocument'])
        item=saved_source(repo_root=root,url=url,accession=filing['accessionNumber'])
        if item is None:raise ValueError('D04_TASK_INPUT_SOURCE_MISSING:'+url)
        proof=item['proof']
        if proof not in proofs:proofs.append(proof)
        blob=raw_blob_record(repo_root=root,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
        ref=source_reference_record(raw_blob=blob,company_id=company_id,source_url=url,
            accession=filing['accessionNumber'],document_name=filing['primaryDocument'],
            source_role='target_primary' if filing['form']=='10-K' else 'annual_amendment',
            request_attempt_id=proof['request_attempt_id'])
        parsed=parsed_d04_document(raw_bytes=item['raw'],raw_blob=blob,source_reference=ref,
            expected_company_id=company_id,expected_cik=annual['entity'],
            expected_period_end=annual['table_input']['target_period']['period_end'],
            allow_annual_amendment=filing['form']=='10-K/A')
        if parsed['parsed_input']['identity']['form']!=filing['form']:
            raise ValueError('D04_TASK_INPUT_DOCUMENT_FORM_CHANGED')
        documents.append({'filing':{k:filing[k] for k in fields},'source_url':url,
            'parsed_input_sha256':parsed['parsed_input_sha256']})
    verify_ordinary_source_proofs(data_root=root,proofs=proofs)
    body={'method':'ORDINARY_D04_COMPLETE_TASK_INPUT_V1','company_id':company_id,
        'entity':annual['entity'],'subject_policy':annual['subject_policy'],
        'target_period':annual['table_input']['target_period'],'documents':documents}
    # Non-HTML task dependencies remain conservative raw comparisons. Only
    # primary submissions may change without changing selected annual inputs.
    html={d['source_url'] for d in documents};metadata=submissions_url(cik=int(annual['entity']))
    body['other_source_content']=[{k:p[k] for k in ('source_url','accession','document_name','content_sha256')}
        for p in proofs if p['source_url'] not in html and p['source_url']!=metadata]
    body['other_source_content'].sort(key=lambda p:(p['source_url'],p['accession'],p['document_name']))
    return {**body,'task_input_id':content_hash(value=body),'source_proofs':proofs,
            'source_admission_or_result_credit':False}


def same_task(previous,current):
    for value in (previous,current):
        body={k:v for k,v in value.items() if k not in {
            'task_input_id','source_proofs','source_admission_or_result_credit'}}
        if (body.get('method')!='ORDINARY_D04_COMPLETE_TASK_INPUT_V1'
                or content_hash(value=body)!=value.get('task_input_id')):
            raise ValueError('D04_TASK_INPUT_ID_CHANGED')
    return previous['task_input_id']==current['task_input_id']
