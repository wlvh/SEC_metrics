"""Fresh D04 source interpretations; old feasibility responses stay diagnostic."""
from copy import deepcopy
import re

from .canonical import content_hash, strict_json_file, strict_json_loads, sha256_file
from .capacity_semantic_review import shared_source_groups, _shared_units, _restore_units
from .capacity_utilization_source import need
from .normal_source_authority import ROOT
from .r6_semantic_review import _source_items, _validate_source_response
from .r6_semantic_source import _bytes

POLICY_PATH = 'catalog/r6/semantic_review_v4.json'
COMPLETE_POLICY_PATH = 'catalog/r6/semantic_review_v5.json'
COMPLETE_RESPONSE_VERSION = 'D04_COMPLETE_UNITS_V1'
SPEC_PATH = 'catalog/r6/D04_going_concern_assessment_v1.md'
CURRENT_KINDS = {'DOUBT_DISCLOSED', 'DOUBT_ALLEVIATED', 'NO_DOUBT_DECLARATION'}


def _specific_continuation_activity(sentence):
    """Distinguish the action's object from continued existence of an entity."""
    if re.search(r'\b(?:doubt|going[ -]concern)\b', sentence, re.I):
        return False
    complement = re.search(r'\bability\s+to\s+continue\s+(?:to\s+)?'
        r'(?P<action>attract(?:ing)?|recruit(?:ing)?|invest(?:ing)?|fund(?:ing)?)\b(?P<object>.+)', sentence, re.I)
    if complement is None:
        return False
    action, obj = complement.group('action').casefold(), complement.group('object')
    if action.startswith(('attract', 'recruit')):
        return re.search(r'\b(?:employees|talent|subscribers|users)\b', obj, re.I) is not None
    if action.startswith('invest'):
        return re.match(r'\s+in\b.+\bbusiness(?:es)?\b', obj, re.I) is not None
    return re.match(r'\s+through\b.+\b(?:financing|securiti[sz]ation)\b', obj, re.I) is not None


def _assertion_clauses(sentence):
    """Separate explicit coordinated assertions, retaining subordinators.

    A comma alone is not a boundary (dates and if-antecedents contain commas).
    A coordinating conjunction followed by an explicit subject is a boundary;
    attached if/unless/although clauses remain with their governing assertion.
    This is a limited grammar, not a general English parser.
    """
    boundary = re.compile(r';\s*|(?:,\s*|\s+)(?:and|but|yet)\s+(?='
        r'(?:these|those|this|that|we|there|it|our|management|the\s+company)\b)', re.I)
    antecedent = re.match(r'\s*(?:if|unless|provided\s+that)\b[^,]+,', sentence, re.I)
    start = 0
    for match in boundary.finditer(sentence):
        if antecedent and match.start() < antecedent.end():
            continue
        yield start, match.start(), sentence[start:match.start()]
        start = match.end()
    if start < len(sentence):
        yield start, len(sentence), sentence[start:]


def _assertion_scope(prefix, suffix):
    """Bind modifiers to the doubt assertion, not to adjacent explanations."""
    # Postposed concessive conditions assert that the main fact survives the
    # condition; the financing's success is not a condition on doubt existing.
    following = re.search(r',?\s*\b(?:even\s+if|even\s+though|although|because|for\s+example)\b', suffix, re.I)
    tail = suffix[:following.start()] if following else suffix
    # A causal/concessive adjunct describes why the main assertion holds;
    # its date and negation belong to that adjunct, not the main predicate.
    adjunct = re.match(r'\s*(?:even\s+if|even\s+though|although|because)\b[^,]+,\s*', prefix, re.I)
    local_prefix = prefix[adjunct.end():] if adjunct else prefix
    conditional = bool(re.search(r'\b(?:if|unless|provided\s+that)\b', local_prefix + ' ' + tail, re.I))
    return local_prefix, tail, conditional


def _assessment_time_prefix(prefix):
    """An explicit present predicate may describe a historical cause.

    Keep the full prefix for polarity/embedding checks. Only the temporal
    attachment is narrowed: both a relative predicate (losses that now raise)
    and a main predicate (losses that arose earlier now raise) can assess the
    present. An earlier reporting verb leaves its temporal frame unresolved.
    """
    present = re.search(r'\b(?:now|currently|at\s+present)\s+'
        r'(?:raise[sd]?|creates?|is|have|has)\s+(?:a\s+|substantial\s+)*$', prefix, re.I)
    if present:
        before = prefix[:present.start()]
        if re.search(r'\b(?:concluded|reported|stated|said)\b', prefix[:present.start()], re.I):
            return None
        if re.search(r'\b(?:that|which|incurred|arising|sustained|experienced|suffered|generated)\b', before, re.I):
            return prefix[present.start():]
        # A remaining date/present-frame combination is not proven historical.
        # Do not let an unsupported attachment authorize a negative result.
        if re.search(r'\b(?:19|20)\d{2}\b', before):
            return None
    return prefix


def source_statement_relations(*, text, names, period, quoted=False):
    """Read supported assertion relations without consulting model labels.

    Sentence-local polarity, the possessor of the ability to continue, and
    an explicit assessment date are separate facts. Unrecognized relevant
    language stays unresolved; a missing relation never proves nondisclosure.
    Original text and source indices remain owned by the caller.
    """
    from .regulatory_investigation_candidates import _sentences, _PATTERNS
    from .going_concern_source import _LANGUAGE
    relations = []
    target_year = str(period.get('fiscal_year') or period.get('period_end', '')[:4])
    owners = ['our', *(re.escape(n) + r"[’']s" for n in names)]
    other_owners = r'(?:our\s+|the\s+)?(?:supplier|subsidiary|predecessor|acquired business|customer|partner)[’\']s'
    ability = re.compile(r'\b(?P<owner>' + '|'.join([*owners, 'its', 'their', other_owners]) + r')\s+'
        r'ability\s+to\s+continu(?:e|ing)\s+(?:as\s+a\s+going[ -]concern|(?:our\s+|its\s+)?operations?|in\s+business)\b', re.I)
    clauses = [(start + a, start + b, clause, original, original[:a])
        for start, end, original in _sentences(text)
        for a, b, clause in _assertion_clauses(original)]
    for start, end, sentence, original_sentence, preceding in clauses:
        if not _LANGUAGE.search(sentence):
            continue
        relation = {'statement_text': sentence, 'start_character': start, 'end_character': end,
                    'kind': None, 'subject': None, 'timing': None, 'reason': None}
        # A valuation premise and the basis of preparation are not assessments
        # of doubt. This excludes a relation, not every paragraph with the word.
        if re.search(r'going[ -]concern\s+element\s+of', sentence, re.I) and not re.search(r'\bdoubt\b', sentence, re.I):
            relation.update(kind='VALUATION_OR_OTHER_MEANING')
        elif (re.search(r'financial statements.{0,80}(?:prepared|preparation).{0,40}going[ -]concern\s+basis', sentence, re.I)
              and not re.search(r'\bdoubt\b', sentence, re.I)):
            relation.update(kind='CONDITIONAL_OR_BOILERPLATE', timing='CONDITIONAL')
        elif _specific_continuation_activity(sentence):
            relation.update(kind='VALUATION_OR_OTHER_MEANING')
        else:
            match = ability.search(sentence)
            doubt = re.search(r'\b(?:substantial\s+)?doubt\b', sentence, re.I)
            direct = (match is not None and doubt is not None and match.start() > doubt.end()
                and re.fullmatch(r'\s+(?:about|regarding|over|as to)\s+',
                                 sentence[doubt.end():match.start()], re.I) is not None)
            if direct:
                owner = match.group('owner')
                prefix, tail, conditional = _assertion_scope(
                    sentence[:doubt.start()], sentence[match.end():])
                inherited_condition = re.match(r'\s*(?:if|unless|provided\s+that)\b[^,]+,', preceding, re.I)
                if inherited_condition and ';' not in preceding and re.search(r'\band\s*$', preceding, re.I):
                    conditional = True
                # The syntactic owner is required: a supplier mentioned next to
                # "our" somewhere else is not the reporting entity.
                if any(re.fullmatch(o, owner, re.I) for o in owners):
                    relation['subject'] = 'TARGET_REGISTRANT'
                elif owner.casefold() not in {'its', 'their'}:
                    relation['subject'] = 'OTHER_ENTITY'
                else:
                    named = [n for n in names if re.search(r'\b' + re.escape(n)
                        + r'\s+(?:has|had|expressed|reported|identified)\s+(?:no\s+)?$', prefix, re.I)]
                    if len(named) == 1:
                        relation['subject'] = 'TARGET_REGISTRANT'
                # Affirmative doubt, its denial, and alleviation have different
                # predicates. A bare mention of doubt is insufficient.
                if re.search(r'\b(?:no|not\s+any)\s+(?:substantial\s+)?$', prefix, re.I):
                    relation['kind'] = 'NO_DOUBT_DECLARATION'
                elif re.search(r'\b(?:do|does|did)\s+not\s+(?:raise|create)\s+(?:substantial\s+)?$', prefix, re.I):
                    relation['kind'] = 'NO_DOUBT_DECLARATION'
                elif re.search(r'\b(?:raise[sd]?|creates?|created|is|was|exists?|existed|have|has|expressed|reported|identified)\s+(?:a\s+|substantial\s+)*$', prefix, re.I):
                    relation['kind'] = 'DOUBT_DISCLOSED'
                elif re.search(r'\balleviate[sd]?\s+(?:substantial\s+)?$', prefix, re.I):
                    relation['kind'] = 'DOUBT_ALLEVIATED'
                if re.search(r'\b(?:has|have|had)\s+(?:been\s+)?alleviated\b|\b(?:is|was)\s+alleviated\b', tail, re.I):
                    relation['kind'] = 'DOUBT_ALLEVIATED'
                if re.search(r'\b(?:has|have|had|is|was)\s+(?:not\s+been|not)\s+alleviated\b', tail, re.I):
                    relation['kind'] = 'DOUBT_DISCLOSED'
                time_prefix = _assessment_time_prefix(prefix)
                date = re.search(r'\b(?:In|As of|For (?:the )?(?:year ended )?)\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?((?:19|20)\d{2})\b', time_prefix or '', re.I)
                if time_prefix is None:
                    relation['timing'] = None
                elif re.search(r'\b(?:previously|historically|prior year|last year|previous annual report)\b', time_prefix, re.I):
                    relation['timing'] = 'HISTORICAL'
                elif date:
                    year = date.group(1)
                    if target_year.isdigit():
                        relation['timing'] = 'HISTORICAL' if year < target_year else 'CURRENT_REPORT' if year == target_year else None
                else:
                    relation['timing'] = 'CURRENT_REPORT'
                if conditional:
                    relation.update(kind='CONDITIONAL_OR_BOILERPLATE', timing='CONDITIONAL')
                elif re.search(r'\b(?:may|might|could|would|whether)\b', prefix, re.I):
                    relation['kind'] = None
                # An example is not inherently hypothetical. Explicitly
                # hypothetical framing without a supported conditional syntax
                # remains unproved instead of authorizing an absence result.
                if re.search(r'\b(?:hypothetical|illustrative)\b', prefix, re.I) and not conditional:
                    relation['kind'] = None
                # Negation outside the supported local predicate changes its
                # scope (e.g. "do not believe ... raise doubt"). Do not guess.
                local_denial = re.search(r'\b(?:no|not\s+any|(?:do|does|did)\s+not\s+(?:raise|create))\s*(?:substantial\s+)?$', prefix, re.I)
                before_denial = prefix[:local_denial.start()] if local_denial else prefix
                if re.search(r'\b(?:not|no|never|deny|denied)\b', before_denial, re.I):
                    relation['kind'] = None
                if len(re.findall(r'\b(?:substantial\s+)?doubt\b', sentence, re.I)) > 1:
                    relation['kind'] = None
                if not conditional and re.search(r'\bwill\b|\b(?:expects?|expected|intends?|intended|plans?|planned|proposes?|proposed)\s+to\b', prefix + ' ' + tail, re.I):
                    relation['kind'] = None
                # Unproved scope across contrast/semicolon or an embedding
                # attitude cannot become an automatically excluded assertion.
                if ((inherited_condition and not conditional)
                    or re.search(r'\b(?:believe|believes|hypothetical|illustrative)\b', preceding, re.I)):
                    relation['kind'] = None
            elif re.search(r'\b(?:required to|must)\s+(?:evaluate|assess|consider)\b.*\b(?:whether|ability)\b', sentence, re.I):
                relation.update(kind='CONDITIONAL_OR_BOILERPLATE', timing='CONDITIONAL')
        speech = any(_PATTERNS['reported_speech_intro'].search(original_sentence[:m.end()])
                     for m in re.finditer(r'[:“"]', original_sentence))
        if quoted or speech or _PATTERNS['discourse_qualification'].search(original_sentence):
            relation.update(kind=None, reason='D04_QUOTED_TEXT_REQUIRES_CONTEXT')
        if relation['kind'] is None or (relation['kind'] in CURRENT_KINDS and
                (relation['subject'] is None or relation['timing'] is None)):
            relation['reason'] = relation['reason'] or 'D04_SOURCE_RELATION_IMPLEMENTATION_UNSUPPORTED'
        relations.append(relation)
    return relations


def check_source_classifications(*, request, units, findings):
    """Check both selected and excluded facts over every supplied source item."""
    from .regulatory_investigation_candidates import _self_aliases
    from .going_concern_source import _CONCEPT
    blocks = [b for u in units if u['kind'] == 'VISIBLE_TEXT' for b in u['payload']['blocks']]
    binding = request['document_context']['registrant_name_binding']
    aliases = _self_aliases({'registrant_names': binding.get('accepted_source_names', []),
        'blocks': blocks, 'text_document_id': request['document_context']['document_id'],
        'raw_asset_id': None, 'source_reference_id': None})
    names = [a['text'] for a in aliases if a['text'].casefold() != 'we']
    unresolved = []
    for unit in units:
        evidence_kind, items = _source_items(unit)
        for index, item in items.items():
            text = item['raw_xml'] if evidence_kind == 'NATIVE_SUPPLEMENT' else item['text']
            # TextBlock markup is preserved in the source. It must not be
            # interpreted by stripping arbitrary tags into a claimed sentence.
            relations = source_statement_relations(text=text, names=names,
                period=request['target_period'], quoted=item.get('html_quotation_context', False))
            if not relations and evidence_kind == 'NATIVE_FACT' and _CONCEPT.search(item['qualified_name']):
                # A concept-name hint plus an undefined boolean cannot prove
                # either doubt or its absence. Preserve this specific gap.
                unresolved.append({'unit_id': unit['unit_id'], 'source_index': index,
                    'reason': 'D04_NATIVE_CONCEPT_MEANING_NOT_ESTABLISHED', 'statement_text': text})
            selected = [f for f in findings if f['unit_id'] == unit['unit_id'] and any(
                e['kind'] == evidence_kind and e['source_index'] == index for e in f['resolved_evidence'])]
            def matches(f, r):
                kind_matches = (f['kind'] == r['kind'] or
                    # V5 explicitly permits ordinary conditional business risks.
                    # This overlap applies only to a proved concrete activity,
                    # never to a valuation premise or a going-concern assertion.
                    (r['kind'] == 'VALUATION_OR_OTHER_MEANING'
                     and _specific_continuation_activity(r['statement_text'])
                     and f['kind'] == 'CONDITIONAL_OR_BOILERPLATE'
                     and f['timing'] == 'CONDITIONAL') or
                    f['kind'] == 'HISTORICAL_STATEMENT' and r['timing'] == 'HISTORICAL' or
                    f['kind'] == 'OTHER_ENTITY' and r['subject'] == 'OTHER_ENTITY')
                return (kind_matches and (r['subject'] is None or f['subject'] == r['subject'])
                        and (r['timing'] is None or f['timing'] == r['timing']))
            proven = [r for r in relations if r['reason'] is None]
            for relation in relations:
                if relation['reason'] is not None:
                    unresolved.append({'unit_id': unit['unit_id'], 'source_index': index,
                        'reason': relation['reason'], 'statement_text': relation['statement_text']})
                else:
                    need(any(matches(f, relation) for f in selected), 'D04_SOURCE_FACT_CLASSIFICATION_CONFLICT')
            for finding in selected:
                if finding['kind'] == 'UNRESOLVED':
                    continue
                if relations and not any(r['reason'] for r in relations):
                    need(any(matches(finding, r) for r in proven), 'D04_SOURCE_LABEL_CLASSIFICATION_CONFLICT')
                elif not relations and finding['kind'] in CURRENT_KINDS:
                    raise ValueError('D04_EXPLICIT_GOING_CONCERN_ASSERTION_NOT_ESTABLISHED')
    return unresolved


def native_source(source, *, historical_control=False, request_context_format=None, complete_response_contract=False):
    """A new input identity, retaining the exact complete original source set."""
    expected = 'D04_HISTORICAL_PRIMARY_CONTROL_SOURCE' if historical_control else 'D04_COMPLETE_SEMANTIC_SOURCE'
    need(source['record_type'] == expected
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}), 'D04_NATIVE_COMPLETE_SOURCE_REQUIRED')
    body = {k: v for k, v in source.items() if k != 'semantic_source_id'}
    if historical_control:
        need(source['normal_update_input'] is False and source['control_scope'] ==
             'EXACT_HISTORICAL_PRIMARY_AND_HEADER_ONLY_NOT_LATEST_ANNUAL_OR_WHOLE_FILING',
             'D04_NATIVE_CONTROL_SCOPE_CHANGED')
    body.update(record_type='D04_NATIVE_HISTORICAL_CONTROL_SOURCE' if historical_control else 'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE',
                original_complete_source_id=source['semantic_source_id'],
                source_check_scope=source['control_scope'] if historical_control else
                    'SAVED_ANNUAL_PRIMARY_AND_ALL_CURRENT_ANNUAL_AMENDMENTS_VISIBLE_AND_NATIVE')
    if request_context_format is not None:
        from .continuous_request_context import FORMAT_VERSION
        need(request_context_format == FORMAT_VERSION, 'D04_NATIVE_CONTEXT_FORMAT_UNSUPPORTED')
        body['request_context_format'] = FORMAT_VERSION
    need(type(complete_response_contract) is bool, 'D04_COMPLETE_RESPONSE_SELECTION_INVALID')
    if complete_response_contract:
        body['response_contract_version'] = COMPLETE_RESPONSE_VERSION
    return {**body, 'semantic_source_id': content_hash(value=body)}


def _response_contract(rules, units, required, complete):
    protocol = deepcopy(rules['response_protocol'])
    if not complete:
        return protocol, {}
    ids = [u['unit_id'] for u in units]
    unit_schema = protocol['json_schema']['properties']['units']
    unit_schema.update(minItems=len(ids), maxItems=len(ids))
    unit_schema['items']['properties']['unit_id']['enum'] = ids
    return protocol, {'required_response_unit_ids': ids, 'unit_response_requirements': [
        {'unit_id': uid, 'required_evidence_references': [
            {k:r[k] for k in ('kind','source_index')} for r in required if r['unit_id'] == uid]}
        for uid in ids]}


def requests_from_source(source):
    version = source.get('response_contract_version')
    need(version in {None, COMPLETE_RESPONSE_VERSION}, 'D04_RESPONSE_CONTRACT_VERSION_UNSUPPORTED')
    policy_path = COMPLETE_POLICY_PATH if version else POLICY_PATH
    rules = strict_json_file(path=ROOT / policy_path)
    need(source['record_type'] in {'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE', 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE'}
         and source['source_serialization_complete'] is True
         and source['semantic_source_id'] == content_hash(value={
             k: v for k, v in source.items() if k != 'semantic_source_id'}), 'D04_NATIVE_COMPLETE_SOURCE_REQUIRED')
    need(source['required_unit_ids'] == [u['unit_id'] for u in source['units']]
         and len(set(source['required_unit_ids'])) == len(source['units']), 'D04_NATIVE_UNIT_SET_CHANGED')
    documents = {d['document_id']: d for d in source['documents']}
    annual = source['prepared_annual_input']
    from .continuous_request_context import FORMAT_VERSION, measured_groups
    context_format = source.get('request_context_format')
    need(context_format in {None, FORMAT_VERSION}, 'D04_NATIVE_CONTEXT_FORMAT_UNSUPPORTED')

    def request_for_group(group):
        packed, shared = _shared_units(group)
        if context_format is None:
            need(len(_bytes([packed, shared])) <= rules['max_group_source_bytes'], 'D04_NATIVE_SOURCE_GROUP_EXCEEDS_BOUND')
        doc = documents[group[0]['document_id']]; required = []
        for unit in group:
            kind, items = _source_items(unit)
            indices = (doc['language_candidate_block_indices'] if kind == 'VISIBLE_BLOCK' else
                       doc['native_candidate_ordinals'] if kind == 'NATIVE_FACT' else [])
            required.extend({'unit_id': unit['unit_id'], 'kind': kind, 'source_index': i}
                            for i in indices if i in items)
        protocol, checklist = _response_contract(rules, packed, required, bool(version))
        body = {'record_type': 'D04_NATIVE_INTERPRETATION_REQUEST', 'metric_id': 'D04',
            'native_evidence_requested': True, 'source_id': source['semantic_source_id'],
            'company_id': source['company_id'], 'target_cik': annual['entity'],
            'target_period': annual['table_input']['target_period'],
            'fiscal_label_context': {k: annual['fiscal_year_label_resolution'][k] for k in
                ('selected_fiscal_year', 'basis', 'original_dei_fiscal_year',
                 'original_companyfacts_fiscal_year_values', 'metadata_conflict_retained')},
            'document_context': {k: doc[k] for k in ('document_id', 'filing', 'registrant_name_binding')},
            'system_prompt': rules['system_prompt'], 'units': packed, 'shared_source_dictionaries': shared,
            'category_definitions': rules['category_definitions'], 'required_candidate_assessments': required,
            'response_protocol': protocol, 'policy_sha256': sha256_file(path=ROOT / policy_path),
            'provider_request_sent': False, 'provider_tokens_measured': False, 'production_authorized': False}
        if version:
            body.update(response_contract_version=version, **checklist)
        if context_format is not None:
            body['request_context_format'] = context_format
        if source['record_type'] == 'D04_NATIVE_HISTORICAL_CONTROL_SOURCE':
            body.update(historical_control=source['control'], control_source_scope=source['control_scope'])
            body['system_prompt'] += (' This request is a historical primary/header-only control. CURRENT_REPORT refers '
                'to the supplied historical report. It cannot establish current-company status or whole-filing absence.')
        return {**body, 'request_id': content_hash(value=body)}

    groups = (shared_source_groups(source['units'], rules['max_group_source_bytes']) if context_format is None else
              measured_groups(source['units'], request_for_group))
    requests = [request_for_group(group) for group in groups]
    need([u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
         'D04_NATIVE_REQUEST_CENSUS_CHANGED')
    return requests


def validate_response(*, request, raw_response):
    if 'indexed_unit_contract' in request:
        from .native_unit_index import restore_response
        need(type(raw_response) is bytes and len(raw_response) <= strict_json_file(path=ROOT / POLICY_PATH)['max_response_bytes'],
             'D04_NATIVE_RESPONSE_SIZE')
        base, normalized, original = restore_response(request=request, raw_response=raw_response)
        checked = validate_response(request=base, raw_response=normalized)
        checked.update(request_id=request['request_id'], response=original)
        return checked
    version = request.get('response_contract_version')
    need(version in {None, COMPLETE_RESPONSE_VERSION}, 'D04_RESPONSE_CONTRACT_VERSION_UNSUPPORTED')
    policy_path = COMPLETE_POLICY_PATH if version else POLICY_PATH
    rules = strict_json_file(path=ROOT / policy_path)
    protocol, checklist = _response_contract(rules, request['units'], request['required_candidate_assessments'], bool(version))
    need(request['request_id'] == content_hash(value={k: v for k, v in request.items() if k != 'request_id'})
         and request['policy_sha256'] == sha256_file(path=ROOT / policy_path)
         and request['response_protocol'] == protocol
         and all(request.get(k) == v for k, v in checklist.items())
         and (bool(version) or not {'required_response_unit_ids','unit_response_requirements'}.intersection(request)),
         'D04_NATIVE_REQUEST_POLICY_CHANGED')
    need(type(raw_response) is bytes and len(raw_response) <= rules['max_response_bytes'], 'D04_NATIVE_RESPONSE_SIZE')
    original = strict_json_loads(text=raw_response.decode('utf-8'))
    need(type(original) is dict and original.get('request_id') == request['request_id'], 'D04_NATIVE_RESPONSE_REQUEST_CHANGED')
    if version:
        need(type(original.get('units')) is list
             and all(type(u) is dict for u in original['units'])
             and [u.get('unit_id') for u in original['units']] == request['required_response_unit_ids'],
             'D04_RESPONSE_UNIT_CENSUS_ORDER_CHANGED')
    resolved = deepcopy(original)
    units = _restore_units(request['units'], request['shared_source_dictionaries'])
    by_id = {u['unit_id']: u for u in units}
    need(type(resolved.get('units')) is list, 'D04_NATIVE_RESPONSE_UNITS_REQUIRED')
    for row in resolved['units']:
        need(type(row) is dict and row.get('unit_id') in by_id and type(row.get('findings')) is list,
             'D04_NATIVE_REFERENCE_UNIT_CHANGED')
        kind, items = _source_items(by_id[row['unit_id']])
        for finding in row['findings']:
            need(type(finding) is dict and type(finding.get('evidence')) is list, 'D04_NATIVE_REFERENCE_FIELDS')
            for evidence in finding['evidence']:
                need(type(evidence) is dict and set(evidence) == {'kind', 'source_index'}
                     and evidence['kind'] == kind and type(evidence['source_index']) is int
                     and evidence['source_index'] in items, 'D04_NATIVE_REFERENCE_OUTSIDE_SOURCE')
                item = items[evidence['source_index']]
                evidence['text'] = item['raw_xml'] if kind == 'NATIVE_SUPPLEMENT' else item['text']
    body = {k: v for k, v in request.items() if k != 'request_id'}
    body.update(units=units, document_context={**body['document_context'],
                'language_candidate_block_indices': [], 'native_candidate_ordinals': []})
    restored = {**body, 'request_id': content_hash(value=body)}
    checked = _validate_source_response(request=restored,
        raw_response=_bytes({**resolved, 'request_id': restored['request_id']}),
        policy={**rules, 'current_target_kinds': [], 'max_response_bytes': rules['host_reference_max_bytes'],
                'max_quote_characters': rules['host_reference_max_quote_characters']})
    required = {(r['unit_id'], r['kind'], r['source_index']) for r in request['required_candidate_assessments']}
    accounted = {(f['unit_id'], e['kind'], e['source_index']) for f in checked['findings'] for e in f['resolved_evidence']}
    need(required <= accounted, 'D04_NATIVE_KNOWN_CANDIDATE_NOT_ASSESSED')
    for finding in checked['findings']:
        if (finding['kind'] not in CURRENT_KINDS or finding['subject'] != 'TARGET_REGISTRANT'
                or finding['timing'] != 'CURRENT_REPORT'):
            continue
        _, items = _source_items(by_id[finding['unit_id']])
        need(not any(e['kind'] == 'VISIBLE_BLOCK' and items[e['source_index']]['html_quotation_context']
                     for e in finding['resolved_evidence']), 'D04_QUOTED_TEXT_CANNOT_ALONE_ESTABLISH_CURRENT_ASSERTION')
        # This is a necessary content check, never positive semantic proof.
        # A clean opinion, valuation uncertainty or absence of a cyber risk is
        # not itself an explicit going-concern assessment.
        text = ' '.join(e['text'] for e in finding['resolved_evidence'])
        need(re.search(r'\bgoing[\s-]+concern\b|\bcontinu(?:e|ing|ation)\b.{0,80}\b(?:operat\w*|business)\b',
                       text, re.I | re.S) is not None, 'D04_EXPLICIT_GOING_CONCERN_ASSERTION_NOT_ESTABLISHED')
    checked['unresolved'].extend(check_source_classifications(request=request, units=units, findings=checked['findings']))
    checked.update(request_id=request['request_id'], response=original,
        current_target_findings=[f for f in checked['findings'] if f['kind'] in CURRENT_KINDS
                                 and f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT'])
    return checked


def build_acceptance(*, prepared, plan, response_body):
    from pathlib import Path
    from .capacity_native_assessment import _build_acceptance
    request = strict_json_loads(text=prepared.request_bytes.decode())
    need(request['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST'
         and request['metric_id'] == 'D04' and request['native_evidence_requested'] is True,
         'D04_FRESH_NATIVE_REQUEST_REQUIRED')
    return _build_acceptance(prepared=prepared, plan=plan, response_body=response_body,
        checked=validate_response(request=request, raw_response=response_body), metric_id='D04',
        group='d04_going_concern_source_assessment_v1', spec_path=SPEC_PATH, validator_path=Path(__file__))
