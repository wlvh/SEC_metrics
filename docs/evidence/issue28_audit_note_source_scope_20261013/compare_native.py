"""Compare non-DEI source facts/contexts/units; this grants no input clearance."""
import collections,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_governance_input import _Sources
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.text_results_v2 import _ReportedFactMetadata, _verified_context


def canonical_native(source,document):
    filing=document['filing'];start=time.monotonic()
    reader=_Sources(source,'marriott_international','1048286')
    primary=reader.read(document['source_reference']['source_url'],accession=filing['accessionNumber'],
        role='audit_compare_primary',media_type='text/html')
    raw=primary['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw)
    meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
    counts=collections.Counter();details={}
    for fact in parsed.facts:
        attrs=meta.facts[fact['ordinal']];qname=attrs['concept']
        if qname[0].startswith(('http://xbrl.sec.gov/dei/','https://xbrl.sec.gov/dei/')):continue
        native=parsed.contexts[fact['context_ref']]
        context=_verified_context(native=native,metadata=meta)
        context={k:v for k,v in context.items() if k not in {'context_ref'}}
        unit=meta.units.get(fact['unit_ref']) if fact['unit_ref'] else None
        canonical={'concept':qname,'context':context,'unit':unit,'text':fact['text'],
            'scale':fact['scale'],'sign':fact['sign'],'attributes':{k:v for k,v in attrs.items()
                if k not in {'concept','context_ref','unit_ref'}}}
        key=json.dumps(canonical,sort_keys=True,ensure_ascii=False,default=list)
        counts[key]+=1;details[key]=canonical
    return counts,details,{'all_facts':len(parsed.facts),'non_dei_occurrences':sum(counts.values()),
        'distinct_non_dei':len(counts),'elapsed_seconds':time.monotonic()-start}


if __name__=='__main__':
    source=Path(sys.argv[1]);data=json.loads(Path(sys.argv[2]).read_text())
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
        a,ad,ast=canonical_native(source,data['documents'][0]);b,bd,bst=canonical_native(source,data['documents'][1])
    removed=a-b;added=b-a
    result={'original':ast,'amendment':bst,'identical_non_dei_multiset':a==b,
        'removed':[{'count':n,'fact':ad[k]} for k,n in removed.items()],
        'added':[{'count':n,'fact':bd[k]} for k,n in added.items()],
        'source_admission_granted':False,'calls':[0,0,0]}
    Path(sys.argv[3]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'removed','added'}},indent=2))
    print('removed',len(removed),'added',len(added))
