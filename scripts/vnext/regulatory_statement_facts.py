"""Bounded aggregate involvement facts, separate from case-level detail.

Reuse the existing source aliases, sentence boundaries and discourse checks.
No match means this grammar is not applicable; it never proves no proceedings.
These facts are implementation inputs, not standalone D03 acceptance records.
"""
import re

from .canonical import content_hash
from .regulatory_investigation_candidates import _PATTERNS, _sentences, _self_aliases


def aggregate_involvement_facts(*, text, aliases, quoted=False, context=()):
    """Recognize an explicit present aggregate governmental-action relation.

    ``aliases`` must come from the existing complete source identity parser.
    The caller retains the containing block and adjacent context; a model's
    proposed subject, case name or confidence is never an input to this rule.
    """
    names = {a['text'].casefold(): a for a in aliases}
    if not names:
        return []
    alternatives = '|'.join(re.escape(a['text']) for a in sorted(
        aliases, key=lambda a: len(a['text']), reverse=True))
    predicate = re.compile(
        r'^(?P<subject>' + alternatives + r')\s+(?:is|are)\s+'
        r'(?:named\s+as\s+(?:a\s+)?defendant\s+or\s+(?:is|are)\s+)?'
        r'(?:otherwise\s+|currently\s+)?involved\s+in\s+'
        r'(?P<inventory>(?:(?:many|various|civil|governmental|legal|and)\s+)*'
        r'(?:proceedings|matters))\s*[,;:]?\s*'
        r'(?P<inclusions>(?:including|which\s+include)\s+.+)', re.I)
    # Government must govern the investigation/enforcement phrase itself,
    # not merely occur elsewhere in a paragraph about private litigation.
    relation = re.compile(
        r'\b(?:(?:government(?:al)?|regulatory)\s+investigations?'
        r'|investigations?\s+(?:and\s+enforcement\s+actions?\s+)?by\s+'
        r'(?:(?:U\.S\.|non-U\.S\.|and)\s+)*(?:government(?:al)?|regulatory)\s+authorities)\b', re.I)
    rows = []
    for start, end, sentence in _sentences(text):
        match = predicate.fullmatch(sentence.rstrip('.'))
        if match is None:
            continue
        action = relation.search(match.group('inclusions'))
        if action is None:
            continue
        before_action = match.group('inclusions')[:action.start()]
        if re.search(r'(?:^including|^which\s+include|,|as\s+well\s+as|\band)\s*$',
                     before_action, re.I) is None:
            # Litigation *about* government investigations is not itself a
            # disclosed participation in those investigations.
            continue
        # Restrict this rule to an asserted inclusion list. Modals, denials,
        # quoted speech or resolutions require the general interpretation path.
        reasons = []
        if quoted or _PATTERNS['discourse_qualification'].search(sentence) or any(
                _PATTERNS['discourse_qualification'].search(c)
                or _PATTERNS['reported_speech_intro'].search(c) for c in context):
            reasons.append('QUOTED_OR_QUALIFIED_DISCOURSE')
        if re.search(r'\b(?:may|might|could|would|if|possible|potential|not|no|never|except|excluding)\b',
                     match.group('inclusions'), re.I):
            reasons.append('INCLUSION_NOT_UNCONDITIONALLY_AFFIRMATIVE')
        if re.match(r'\s+(?:conducted\s+)?by\s+(?:private|internal|customers|our\s+own)\b',
                    match.group('inclusions')[action.end():], re.I):
            reasons.append('ACTION_ACTOR_CONFLICT')
        if _PATTERNS['resolution'].search(sentence) or any(
                _PATTERNS['linked_resolution'].search(c)
                and _PATTERNS['resolution'].search(c)
                and not _PATTERNS['explicit_unrelated'].search(c) for c in context):
            reasons.append('LINKED_RESOLUTION_REQUIRES_INTERPRETATION')
        body = {'rule_id': 'AFFIRMATIVE_AGGREGATE_GOVERNMENT_INVOLVEMENT_V1',
                'statement_text': sentence,
                'visible_block_character_span': {'start': start, 'end': end},
                'subject_binding': names[match.group('subject').casefold()],
                'assertion': 'AFFIRMATIVE' if not reasons else 'REQUIRES_INTERPRETATION',
                'subject': 'SOURCE_BOUND_REGISTRANT',
                'reported_time': 'CURRENT_AS_REPORTED' if not reasons else 'UNRESOLVED',
                'detail_level': 'AGGREGATE_INVOLVEMENT',
                'government_action_phrase': action.group(),
                'case_identity': None, 'case_count': None, 'event_dates': [],
                'case_details_extracted': False,
                'unlawfulness_or_guilt_asserted': False,
                'status': 'SOURCE_REPORTED_FACT' if not reasons else 'SEMANTIC_REVIEW_REQUIRED',
                'reason_codes': reasons, 'whole_source_coverage_proven': False,
                'native_result_created': False}
        rows.append({**body, 'fact_id': content_hash(value=body)})
    return rows


def check_aggregate_classification(*, facts, kind, reported_status):
    """Reject erasure of a proven fact; do not silently repair model output."""
    proven = [f for f in facts if f['status'] == 'SOURCE_REPORTED_FACT']
    if proven and (kind != 'CURRENT_REGULATORY_ACTION'
                   or reported_status != 'ONGOING_AS_REPORTED'):
        raise ValueError('D03_AFFIRMATIVE_AGGREGATE_FACT_CLASSIFICATION_CONFLICT')
    return proven


def aggregate_facts_from_source(source):
    """Use the full source's own names, aliases, blocks and quotation marks."""
    result = []
    for document in source['documents']:
        blocks = [b for u in source['units']
                  if u['document_id'] == document['document_id'] and u['kind'] == 'VISIBLE_TEXT'
                  for b in u['payload']['blocks']]
        identity = {'registrant_names': document['registrant_name_binding']['accepted_source_names'],
                    'blocks': blocks, 'text_document_id': document['document_id'],
                    'raw_asset_id': document['raw_blob']['raw_asset_id'],
                    'source_reference_id': document['source_reference']['source_reference_id']}
        aliases = _self_aliases(identity)
        for index, block in enumerate(blocks):
            # Existing bounded neighbors retain reported speech and linked
            # resolution evidence without treating unrelated future risks as
            # a denial of this sentence's present-tense statement.
            neighbors = [b['text'] for b in blocks[max(0, index - 1):index + 3] if b is not block]
            for fact in aggregate_involvement_facts(text=block['text'], aliases=aliases,
                    quoted=block['html_quotation_context'], context=neighbors):
                body = {**fact, 'document_id': document['document_id'],
                        'source_reference_id': identity['source_reference_id'],
                        'block_index': block['block_index'],
                        'raw_start_byte': block['raw_start_byte'],
                        'raw_end_byte': block['raw_end_byte'],
                        'raw_span_sha256': block['raw_span_sha256']}
                result.append({**body, 'source_fact_id': content_hash(value=body)})
    return result
