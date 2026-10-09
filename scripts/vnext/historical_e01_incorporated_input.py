"""Development successor E01 input with separately bound incorporated sources.

The original item-only request, answer, registration and Run remain unchanged.
This module prepares data and checks quote locations; it never calls a model,
classifies M&A, registers an answer or creates a metric result.
"""
from copy import deepcopy
from pathlib import Path

from .canonical import content_hash, sha256_bytes, strict_json_file, strict_json_loads
from .composite_scope import index_source_structure
from .historical_event_attachments import attachment_dependencies, POLICY_PATH
from .historical_ma_confirmation import QUOTE_CHARACTERS
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs

CONTRACT = 'E01_SUPPLIED_ITEM_AND_INCORPORATED_TEXT_V2_DEVELOPMENT'
DECISIONS = ('REPORTS_A_TRANSACTION', 'DOES_NOT_REPORT_A_TRANSACTION',
             'CANNOT_TELL_FROM_SUPPLIED_TEXT')


def _need(condition, reason):
    if not condition:
        raise ValueError('E01_INCORPORATED_INPUT_' + reason)


def _text_source(item_id, reference_id, text, role):
    body = {'item_id': item_id, 'source_reference_id': reference_id,
            'role': role, 'text': text,
            'text_sha256': sha256_bytes(content=text.encode('utf-8'))}
    return {**body, 'source_text_id': content_hash(value=body)}


def prepare_incorporated_e01_input(*, data_root, predecessor_source):
    """Keep the complete saved candidate pool; add only declared attachments."""
    root = Path(data_root)
    original = predecessor_source['request']
    _need(original['metric_id'] == 'E01' and original['contract'] == 'E01_CONTENT_CONFIRMATION_V1'
          and original['company_id'] == predecessor_source['company_id'], 'PREDECESSOR_KIND')
    _need(content_hash(value={k: v for k, v in original.items() if k != 'request_id'})
          == original['request_id'], 'PREDECESSOR_REQUEST_CHANGED')
    verify_ordinary_source_proofs(data_root=root, proofs=predecessor_source['source_proofs'])
    items = deepcopy(original['items'])
    _need(len({i['item_id'] for i in items}) == len(items), 'DUPLICATE_ITEM')
    for item in items:
        _need('sha256:' + sha256_bytes(content=item['text'].encode('utf-8'))
              == item['text_sha256'], 'ITEM_TEXT_CHANGED')
        item['supplied_sources'] = [_text_source(item['item_id'],
            item['primary_source_reference_id'], item['text'], 'parent_item')]
    policy = strict_json_file(path=ROOT/POLICY_PATH)
    declared = [d for d in policy['items'] if d['company_id'] == original['company_id']
                and d['report_end'] == original['window']['period_end']]
    selected = {i['item_id']: i for i in items}
    added_records, proofs, links = [], list(predecessor_source['source_proofs']), []
    for declaration in declared:
        _need(declaration['item_id'] in selected, 'DECLARED_PARENT_OUTSIDE_POOL')
        item = selected[declaration['item_id']]
        _need(item['accession'] == declaration['accession'], 'PARENT_ACCESSION_CHANGED')
        cik = declaration['parent_url'].split('/data/', 1)[1].split('/', 1)[0]
        dependencies = attachment_dependencies(repo_root=root,
            company_id=original['company_id'], report_ends=[declaration['report_end']],
            requirements=[{'source_url': declaration['parent_url'],
                'accession': item['accession'], 'dependency_class': 'FISCAL_EVENT_FILING',
                'primary_cik': original['target_cik'], 'registrant_cik': cik}])
        dependency = next(d for d in dependencies if d['parent_item_id'] == item['item_id'])
        _need(dependency['saved_status'] == 'VERIFIED_SAVED_SOURCE', 'DECLARED_SOURCE_MISSING')
        reader = _Sources(root, original['company_id'], cik)
        source = reader.read(dependency['source_url'], accession=item['accession'],
                             role='incorporated_EX99', media_type='text/html')
        raw = source['raw_bytes']
        structure = index_source_structure(source_bytes=raw)
        blocks = structure['blocks']
        _need(bool(blocks), 'EMPTY_ATTACHMENT_TEXT')
        text = '\n'.join(block['visible_text'] for block in blocks)
        supplied = _text_source(item['item_id'], source['source_reference']['source_reference_id'],
                                text, 'incorporated_attachment')
        supplied.update(raw_asset_id=source['raw_blob']['raw_asset_id'],
                        raw_html=raw.decode('utf-8-sig'), text_blocks=blocks,
                        complete_document_supplied=True, source_url=dependency['source_url'],
                        supplied_media='HTML_AND_COMPLETE_VISIBLE_TEXT',
                        external_assets_fetched=False)
        item['supplied_sources'].append(supplied)
        added_records.extend(reader.records.values())
        proofs.extend(entry['proof'] for entry in reader.proofs.values())
        links.append(dependency)
    _need(bool(links), 'NO_DECLARED_ATTACHMENT_FOR_WINDOW')
    proofs = list({content_hash(value=p): p for p in proofs}.values())
    verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    prompt = ('Classify every supplied item under definition, using its complete parent item text '
              'and only the separately supplied incorporated sources for that same item. '
              'Do not infer content of absent sources, linked documents or image pixels. '
              'Return item_decisions, exactly one per item: '
              '{item_id, decision, source_text_id, quote}. decision is REPORTS_A_TRANSACTION, '
              'DOES_NOT_REPORT_A_TRANSACTION or CANNOT_TELL_FROM_SUPPLIED_TEXT. '
              'Quote 20 to 600 exact characters from the chosen supplied source text; '
              'source_text_id must belong to that item. This is development input only.')
    body = {'record_type': 'HISTORICAL_E01_INCORPORATED_DEVELOPMENT_INPUT',
            'contract': CONTRACT, 'metric_id': 'E01', 'company_id': original['company_id'],
            'target_cik': original['target_cik'], 'window': deepcopy(original['window']),
            'definition': deepcopy(original['definition']), 'items': items, 'system_prompt': prompt,
            'predecessor_request_id': original['request_id'],
            'response_protocol': {'decisions': list(DECISIONS), 'quote_characters': list(QUOTE_CHARACTERS)},
            'attachment_dependencies': links, 'source_proofs': proofs,
            'added_source_records': added_records, 'target_model_execution_authorized': False,
            'model_executed': False, 'metric_result_created': False, 'production_authorized': False}
    body['source_id'] = content_hash(value={'items': items, 'source_proofs': proofs})
    return {**body, 'request_id': content_hash(value=body)}


def validate_incorporated_answer(*, request, raw_output):
    """Mechanical checks only; passing them is not semantic acceptance."""
    _need(request.get('contract') == CONTRACT, 'WRONG_CONTRACT')
    output = strict_json_loads(text=raw_output.decode('utf-8') if isinstance(raw_output, bytes)
                              else raw_output)
    _need(type(output) is dict and set(output) == {'item_decisions'}
          and type(output['item_decisions']) is list, 'ANSWER_SHAPE')
    supplied = {item['item_id']: {s['source_text_id']: s['text']
                                for s in item['supplied_sources']} for item in request['items']}
    decisions = {}
    for row in output['item_decisions']:
        _need(type(row) is dict and set(row) == {'item_id', 'decision', 'source_text_id', 'quote'},
              'DECISION_SHAPE')
        _need(all(type(row[k]) is str for k in ('item_id', 'decision', 'source_text_id', 'quote')),
              'DECISION_FIELD_TYPE')
        item = row['item_id']
        _need(item in supplied and item not in decisions, 'WRONG_OR_REPEATED_ITEM')
        _need(row['decision'] in DECISIONS, 'UNKNOWN_DECISION')
        _need(row['source_text_id'] in supplied[item], 'SOURCE_OUTSIDE_ITEM')
        quote = row['quote']
        _need(type(quote) is str and QUOTE_CHARACTERS[0] <= len(quote) <= QUOTE_CHARACTERS[1],
              'QUOTE_LENGTH')
        _need(quote in supplied[item][row['source_text_id']], 'QUOTE_NOT_IN_SOURCE')
        decisions[item] = dict(row)
    _need(set(decisions) == set(supplied), 'UNANSWERED_ITEMS')
    return decisions
