"""Prepare a source-only B06 development packet from an earlier normal capture.

No semantic output, request body, prompt, provider/SEC call, Run or acceptance.
Reuse the full annual text/table representation rather than add a sentence
pattern for a relationship outside the financing note. Replay normal B06
admission from saved sources and compare exact source bindings to the capture.
"""
import argparse
import hashlib
import json
import re
import socket
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]
from tools.prepare_c02_table_context import assert_matches, model_view, wire
from vnext.continuous_request_context import _load_tokenizer
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.governance_signals import _qname, _source_value
from vnext.historical_debt_results import historical_b06_preparation
from vnext.historical_xbrl_parse import xbrl_parsed_once
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.table_grid import build_table_grid
from vnext.text_coverage import build_text_document
from vnext.text_results_v2 import _ReportedFactMetadata, _verified_context


def sha(value):
    return hashlib.sha256(value).hexdigest()


def prepare(capture, source_root, out):
    if out.exists():
        raise FileExistsError('Use a new output directory; retain old packets')
    prepared = json.loads((capture / 'prepared.json').read_bytes())
    sources = json.loads((capture / 'sources.json').read_bytes())
    raw = {kind: (capture / (kind + '.bin')).read_bytes() for kind in ('primary', 'xml')}
    end = prepared['filing']['reportDate']
    assert prepared['table_input']['target_period']['period_end'] == end
    assert prepared['filing']['form'] == '10-K'
    # Annual preparation has only its own index/primary/companyfacts proofs;
    # the XML belongs to the complete B06 source walk's binding. Rebuild that
    # normal admission instead of assuming XML is in the annual proof list.
    with checkpoint_replayed_once(), xbrl_parsed_once():
        admitted = historical_b06_preparation(repo_root=source_root,
            company_id=prepared['company_id'], prepared=prepared)
    for kind in raw:
        source = sources[kind]
        assert sha(raw[kind]) == source['captured_sha256']
        assert source['raw_blob']['raw_asset_id'] == source['source_reference']['raw_asset_id'] == 'sha256:' + sha(raw[kind])
        assert source['raw_blob']['byte_length'] == len(raw[kind])
        ref = source['source_reference']
        assert ref['company_id'] == prepared['company_id']
        assert ref['accession'] == prepared['filing']['accessionNumber']
        assert admitted[kind]['raw_bytes'] == raw[kind]
        assert admitted[kind]['raw_blob'] == source['raw_blob']
        assert admitted[kind]['source_reference'] == ref
    document = build_text_document(raw_bytes=raw['primary'], raw_blob=sources['primary']['raw_blob'],
        source_reference=sources['primary']['source_reference'], expected_company_id=prepared['company_id'],
        expected_cik=prepared['entity'], expected_period_end=end)
    assert document['source_state'] == 'COMPLETE_LOCAL_DOCUMENT'
    derived = build_table_grid(html_bytes=raw['primary'], parent_raw_asset_ids=[document['raw_asset_id']],
                               storage_uri='evidence/b06-development-full-primary-table-context.json')
    view = model_view(document, derived)
    assert_matches(view, document, derived)
    inventories = {}
    # Retain the existing inventory's broad candidate class, and interest/
    # accrual source candidates that it misses. This includes unrelated tax
    # and equity items; membership is not a debt/asset/commitment decision.
    potential = re.compile(r'debt|borrow|loan|lease|credit|facility|financing|funding|obligation|promissory|seniornotes|subordinatednotes|debentures|interest|accru', re.I)
    for kind in raw:
        parsed = parse_accession_xbrl_source(raw_bytes=raw[kind])
        meta = _ReportedFactMetadata(); meta.feed(raw[kind].decode('utf-8-sig')); meta.close()
        assert meta.ordinal == len(parsed.facts)
        rows = []
        for f in parsed.facts:
            context = parsed.contexts[f['context_ref']]
            info = meta.facts[f['ordinal']]
            if not (context['period_start'] == context['period_end'] == end
                    and f['unit_ref'] and potential.search(info['concept'][1])):
                continue
            # Keep other entities visible if supplied; do not silently drop
            # or combine them with the registrant.
            proof = _verified_context(native={**context, 'dimensions':dict(context['dimensions'])}, metadata=meta)
            try:
                value, issue = _source_value(f, info), None
            except ValueError as error:
                value, issue = None, str(error)
            rows.append({'ordinal': f['ordinal'], 'concept_qname':list(info['concept']),
                         'source_text':f['text'], 'context_ref':f['context_ref'],
                         'context':proof, 'declared_unit':meta.units.get(f['unit_ref']),
                         'numeric_attributes':info['attrs'], 'normalized_source_value':value,
                         'format_qname':list(_qname(info['attrs']['format'], info['namespaces']))
                             if info['attrs'].get('format') else None,
                         'nil_attributes':[{ 'attribute_qname':list(_qname(k, info['namespaces'])),
                                             'value':v } for k,v in info['attrs'].items()
                             if _qname(k, info['namespaces']) == ('http://www.w3.org/2001/XMLSchema-instance', 'nil')],
                         'normalization_issue':issue, 'semantic_role_assigned':False})
        inventories[kind] = rows
    packet = {'record_type':'B06_FULL_PRIMARY_AND_CURRENT_FINANCING_SOURCE_DEVELOPMENT',
              'company_id':prepared['company_id'], 'entity':prepared['entity'],
              'target_period':prepared['table_input']['target_period'], 'filing':prepared['filing'],
              'sources':sources, 'primary_text_and_table_layout':view,
              'current_potential_financing_native_facts':inventories,
              'all_current_instant_facts_claimed':False,
              'native_candidate_class_is_not_financing_completeness':True,
              'all_media_interpreted':False, 'semantic_role_assigned':False}
    tokenizer, fallback = _load_tokenizer()
    assert tokenizer is not None, fallback
    literal = wire(packet)
    out.mkdir(parents=True)
    for name, obj in [('document.json',document), ('table-grid.json',derived),
                      ('view.json',view), ('native-current-financing-facts.json',inventories),
                      ('source-only-package.json',packet),
                      ('normal-b06-source-binding.json',admitted['input_binding'])]:
        (out/name).write_bytes(wire(obj))
    metadata = {'record_type':'ISSUE47_B06_FINANCING_SOURCE_CONTEXT_DEVELOPMENT',
                'company_id':prepared['company_id'], 'report_end':end,
                'source_reference_ids':{k:sources[k]['source_reference']['source_reference_id'] for k in raw},
                'raw_sha256':{k:sha(raw[k]) for k in raw}, 'block_count':view['block_count'],
                'table_count':len(derived['tables']),
                'expanded_cells':sum(t['row_count']*t['column_count'] for t in derived['tables']),
                'native_candidate_counts':{k:len(v) for k,v in inventories.items()},
                'source_only_payload_bytes':len(literal),
                'source_only_reference_tokens':len(tokenizer.encode(literal.decode()).ids),
                'source_only_measurement_is_not_complete_request_measurement':True,
                'block_text_and_expanded_text_header_grids_identical':True,
                'normal_b06_saved_source_admission_rebuilt':True,
                'normal_input_binding_id':admitted['input_binding']['input_binding_id'],
                'artifacts':{p.name:sha(p.read_bytes()) for p in sorted(out.iterdir())},
                'runtime_wired':False, 'provider_trial':False, 'new_runs':0,'new_acceptances':0,
                'calls':[0,0,0], 'production_authorized':False}
    (out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({k:metadata[k] for k in ['block_count','table_count','native_candidate_counts','source_only_reference_tokens','runtime_wired','calls']}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    with patch.object(socket, 'socket', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        prepare(a.capture, a.source_root, a.out)
