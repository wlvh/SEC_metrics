"""Propose new development instructions; never repair/register an old answer."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

REPO=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from tools.prepare_c02_table_context import wire
from vnext.continuous_request_context import measure_request

INSTRUCTIONS='''
Additional development instructions (same definition and output contract):
A source quote is a short evidence anchor, not a copy of the full disclosure.
Normally choose one contiguous 20-160-character span supporting your decision.
Never exceed the existing 300 decoded-character maximum, even when a full
sentence or paragraph is longer. Do not concatenate noncontiguous phrases,
paraphrase, or alter punctuation. The full original block remains in the input.
For a block shorter than 20 characters, copy that entire block. OUT_OF_SCOPE
still carries null. Complete every required decision and inspect other blocks.

Apply the given claims/reserve definition to disclosed self-insurance reserves
for the registrant's liability and workers-compensation claims, including their
recognition policy and the heading that introduces it. Do not reject such a
claims disclosure merely because no individually named lawsuit is present.
An income-tax measurement or uncertain-tax-position accounting paragraph does
not become a legal disclosure merely by mentioning an administrative settlement
or listing litigation/fines among measurement categories. Preserve a disclosed
actual legal claim or proceeding when the source establishes it; do not exclude
all tax-related disputes as a class. These are distinctions within the supplied
definition, not permission to count every use of claims, tax or insurance.
'''


def prepare(export, out):
    if out.exists():
        raise FileExistsError('Preserve existing requests')
    manifest=json.loads((export/'export.json').read_bytes())
    archive=export/manifest['archive']['name'];raw=archive.read_bytes()
    assert len(raw)==manifest['archive']['size'] and hashlib.sha256(raw).hexdigest()==manifest['archive']['sha256']
    index=[];out.mkdir(parents=True)
    with tarfile.open(archive,'r:gz') as tar:
        def checked(name):
            member=tar.getmember(name);assert member.isfile() and not member.issym() and not member.islnk()
            raw=tar.extractfile(member).read();expected=manifest['archive']['members'][name]
            assert len(raw)==expected['size'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
            return raw
        for member in tar.getmembers():
            if not member.name.endswith('/semantic-request.json'):
                continue
            semantic=json.loads(checked(member.name))
            if semantic.get('metric_id')!='D02':
                continue
            prefix=member.name.rpartition('/')[0]
            request_names=[m.name for m in tar.getmembers() if m.name.startswith(prefix+'/invocation_control/requests/') and m.isfile()]
            assert len(request_names)==1
            original=checked(request_names[0]);body=json.loads(original)
            assert body['messages'][0]['content']==semantic['system_prompt']
            assert json.loads(body['messages'][1]['content'])=={
                k:v for k,v in semantic.items() if k!='system_prompt'}
            original_user=body['messages'][1]['content']
            body['messages'][0]['content']+=INSTRUCTIONS
            proposal=wire(body);measurement=measure_request(proposal,require_reference=True)
            assert body['messages'][1]['content']==original_user
            name=semantic['company_id']+'-'+semantic['period_end']
            destination=out/name;destination.mkdir()
            (destination/'request-body.json').write_bytes(proposal)
            (destination/'context-measurement.json').write_bytes(wire(measurement))
            index.append({'position':name,'original_archive_request_path':request_names[0],
                'original_request_sha256':hashlib.sha256(original).hexdigest(),
                'new_development_request_sha256':measurement['request_sha256'],
                'unchanged_user_message_sha256':hashlib.sha256(original_user.encode()).hexdigest(),
                'source_blocks':len(semantic['blocks']),'must_decide':len(semantic['must_decide']),
                'only_outer_system_message_changed':True,'input_tokens':measurement['input_tokens'],'fits':measurement['fits']})
    receipt={'record_type':'ISSUE47_D02_NEW_INSTRUCTION_DEVELOPMENT_PROPOSALS','positions':index,
        'instruction_sha256':hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
        'old_source_request_ids_are_provenance_only_not_new_execution_identity':True,
        'same_source_blocks_order_definition_and_response_contract':True,
        'old_responses_not_loaded_or_trimmed':True,'automatic_business_registration':False,
        'model_answers_tested':False,'runtime_wired':False,'calls':[0,0,0],'new_runs':0,'new_acceptances':0}
    (out/'proposal-index.json').write_text(json.dumps(receipt,indent=1)+'\n')
    (out/'instruction-addendum.txt').write_text(INSTRUCTIONS)
    print(json.dumps({'positions':len(index),'all_fit':all(x['fits'] for x in index),'calls':[0,0,0]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();prepare(args.export,args.out)
