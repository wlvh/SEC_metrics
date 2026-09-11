"""Source-bound amendment impact evidence, separate from original as-filed Runs.

Reviewed complete documents authorize a data-impact conclusion, not production.
A company, accession, keyword or local caller dictionary never grants it.
"""
import re,xml.etree.ElementTree as ET
from datetime import date,datetime
from .canonical import sha256_bytes,sha256_file,strict_json_file,content_hash
from .r5_b06_structured import need

def _norm(element):return ' '.join(' '.join(element.itertext()).split())

def document_identity(raw,expected_form,cik,period):
    root=ET.fromstring(raw);elements=list(root.iter())
    facts=[e for e in elements if e.tag.split('}')[-1] in {'nonNumeric','nonFraction'}]
    def one(name):
        values={_norm(e) for e in facts if e.attrib.get('name')=='dei:'+name}
        need(len(values)==1,'AMENDMENT_DEI_IDENTITY_UNKNOWN');return values.pop()
    need(one('DocumentType')==expected_form and int(one('EntityCentralIndexKey'))==int(cik),'AMENDMENT_ISSUER_OR_FORM_CHANGED')
    end=re.sub(r'\s+,',',',one('DocumentPeriodEndDate'))
    try:parsed=date.fromisoformat(end).isoformat()
    except ValueError:parsed=datetime.strptime(end,'%B %d, %Y').date().isoformat()
    need(parsed==period,'AMENDMENT_PERIOD_CHANGED')
    headings=[_norm(e) for e in elements if e.tag.split('}')[-1]=='div' and len(_norm(e))<180 and re.match(r'^(?:PART\s+(?:III|IV)|Item\s+\d+\.|SIGNATURES)',_norm(e),re.I)]
    return {'complete_text_sha256':sha256_bytes(content=_norm(root).encode()),'element_count':len(elements),
            'inline_fact_count':len(facts),'non_dei_names':sorted({e.attrib.get('name','') for e in facts if not e.attrib.get('name','').startswith('dei:')}),
            'headings':headings,'amendment_flag':one('AmendmentFlag')}

def verify_reviewed_impact(*,original_raw,amendment_raw,original,amendment,cik,decision):
    need(decision['metric_id']=='B06' and decision['decision']=='NO_CHANGE_TO_ORIGINAL_DEBT_EQUITY_DISCLOSURE','AMENDMENT_IMPACT_UNAPPROVED')
    need(sha256_bytes(content=original_raw)==decision['original']['sha256'] and sha256_bytes(content=amendment_raw)==decision['amendment']['sha256'],'AMENDMENT_REVIEWED_BYTES_CHANGED')
    fields=['form','accessionNumber','reportDate','filingDate','primaryDocument']
    need(all(original[k]==decision['original']['filing'][k] and amendment[k]==decision['amendment']['filing'][k] for k in fields),'AMENDMENT_ORIGINAL_RELATION_CHANGED')
    need(original['reportDate']==amendment['reportDate']==decision['target_period_end'] and amendment['filingDate']>=original['filingDate'],'AMENDMENT_ORIGINAL_RELATION_CHANGED')
    original_view=document_identity(original_raw,'10-K',cik,original['reportDate'])
    view=document_identity(amendment_raw,'10-K/A',cik,amendment['reportDate'])
    need(view['complete_text_sha256']==decision['amendment']['complete_normalized_text_sha256'] and view['headings']==[x['text'] for x in decision['amendment']['body_headings']] and view['inline_fact_count']==decision['amendment']['inline_fact_count'],'AMENDMENT_COMPLETE_SCOPE_CHANGED')
    # Structural negative checks supplement, never replace, the independent
    # full-document impact judgment and exact byte binding.
    need(all(name.startswith('ecd:') for name in view['non_dei_names']),'AMENDMENT_FINANCIAL_FACTS_PRESENT')
    need(not any(re.match(r'Item\s+(?:[1-9]|7A|9A)\.',h,re.I) for h in view['headings']),'AMENDMENT_FINANCIAL_SECTION_PRESENT')
    return {'decision':'NO_B06_SOURCE_IMPACT','original_sha256':sha256_bytes(content=original_raw),'amendment_sha256':sha256_bytes(content=amendment_raw),
            'metric_id':'B06','original_identity':original_view,'amendment_identity':view,'review_record_id':content_hash(value=decision),
            'changed_scope':decision['changed_scope'],'reference_evidence':decision['reference_evidence'],
            'preserved_anomalies':['DEI_AMENDMENT_FLAG_FALSE_DESPITE_10KA'] if view['amendment_flag']=='false' else [],'production_permission':False}

def assess(*,data,selected,policy):
    from .annual_input import _saved_source
    from .annual_update import _rows
    from sec_urls import accession_document_url
    if not selected['later_amendments']:return [],[]
    path=data/policy['amendment_review_file'];need(sha256_file(path=path)==policy['amendment_review_sha256'],'AMENDMENT_REVIEW_FILE_CHANGED')
    review=strict_json_file(path=path);rows=_rows(data);cik=int(selected['entity']);original=selected['filing'];out=[];blockers=[]
    for amendment in selected['later_amendments']:
        try:
            op,ob=_saved_source(repo_root=data,rows=rows,url=accession_document_url(cik=cik,accession=original['accessionNumber'],document_name=original['primaryDocument']),accession=original['accessionNumber'])
            ap,ab=_saved_source(repo_root=data,rows=rows,url=accession_document_url(cik=cik,accession=amendment['accessionNumber'],document_name=amendment['primaryDocument']),accession=amendment['accessionNumber'])
            matches=[d for d in review['decisions'] if d['original']['sha256']==sha256_bytes(content=ob) and d['amendment']['sha256']==sha256_bytes(content=ab)]
            need(len(matches)==1,'AMENDMENT_COMPLETE_SOURCE_REVIEW_REQUIRED')
            result=verify_reviewed_impact(original_raw=ob,amendment_raw=ab,original=original,amendment=amendment,cik=cik,decision=matches[0]);result.update(original_source=op,amendment_source=ap,reviewer=review['reviewer'],review_file_sha256=policy['amendment_review_sha256']);out.append(result)
        except (ValueError,FileNotFoundError,ET.ParseError) as e:
            blockers.append('AMENDMENT_IMPACT_UNRESOLVED');out.append({'decision':'UNRESOLVED','amendment':amendment,'reason':str(e)})
    return out,sorted(set(blockers))
