"""Locate remaining source images offline; this is not a grant or an executor."""
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import urljoin, urlsplit


class Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img':
            data=dict(attrs)
            self.images.append({'src':data.get('src',''),'alt':data.get('alt',''),
                                'tag':self.get_starttag_text()})


def build(source_root,out):
    if out.exists():raise FileExistsError('Retain old plans')
    repo=Path(__file__).resolve().parents[4]
    previous=repo/'docs/evidence/issue47_history/d04-full-text-read-2026-10-04/complete-text-two-direction-read.json'
    report=json.loads(previous.read_bytes())
    ledger=source_root/'evidence/requests_log.csv'
    with ledger.open() as f:rows=list(csv.DictReader(f))
    plans=[]
    for document in report['documents']:
        digest=document['raw_asset_id'].split(':')[1]
        parents=[r for r in rows if r['content_sha256']==digest]
        urls={r['source_url'] for r in parents};assert len(urls)==1
        parent=parents[0];raw=(source_root/parent['repo_relative_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==digest
        parsed=Images();parsed.feed(raw.decode('utf-8-sig'));parsed.close()
        assert [(i['src'],i['alt']) for i in parsed.images]==[(i['src'],i['alt']) for i in document['images']]
        for image in parsed.images:
            url=urljoin(parent['source_url'],image['src']);parts=urlsplit(url)
            assert parts.scheme=='https' and parts.hostname=='www.sec.gov' and not parts.port and not parts.username and not parts.query and not parts.fragment
            acquired=[r for r in rows if r['source_url']==url]
            plans.append({'document_id':document['document_id'],'parent_raw_asset_id':document['raw_asset_id'],
                'parent_source_url':parent['source_url'],'parent_ledger_rows':len(parents),
                'literal_image_reference':image,'resolved_official_source_url':url,
                'existing_ledger_rows_for_image':len(acquired),'pixel_bytes_present_in_restored_export':bool(acquired),
                'meaning_inferred_from_alt_or_filename':False})
    unique=sorted({p['resolved_official_source_url'] for p in plans})
    assert len(plans)==report['images_not_read']==14 and len(unique)==14
    assert all(p['existing_ledger_rows_for_image']==0 for p in plans)
    result={'record_type':'ISSUE47_D04_UNACQUIRED_MEDIA_OWNER_REVIEW_PLAN',
        'source_ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),
        'previous_full_text_report_sha256':hashlib.sha256(previous.read_bytes()).hexdigest(),
        'images':plans,'distinct_official_urls':unique,'proposed_maximum_sec_attempts':14,
        'retry_count':0,'existing_cumulative_sec_count':1771,'existing_cap':1867,
        'hypothetical_after_14_attempts':1785,'remaining_96_is_not_authorization':True,
        'owner_resume_required':True,'media_acquisition_dependency_not_yet_wired':True,
        'ledger_restore_rebinding_or_new_root_not_approved_by_this_plan':True,
        'pixel_reading_or_full_media_acceptance_proven':False,'calls':[0,0,0],
        'new_runs':0,'new_acceptances':0,'old_withheld_null_results_unchanged':True}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'image_references':len(plans),'distinct_official_urls':len(unique),'all_unacquired':True,'calls':[0,0,0]}))


if __name__=='__main__':build(Path(sys.argv[1]),Path(sys.argv[2]))
