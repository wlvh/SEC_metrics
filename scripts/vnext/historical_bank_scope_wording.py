"""Finite reuse of existing NIM, nonaccrual and AUM historical forms.

Shared inspectors own numerical, entity, period and scope checks. Local
namespaces add only previously verified wording forms and never mutate the
shared modules. Native A09 still runs first; only its explicit ambiguity may
reach the existing HTML fallback. No new extraction or classification core.
"""
import inspect
import types
from . import financial_relationships as relationships
from . import financial_balance_scope as balances
from . import financial_structured as structured

RULE = 'HISTORICAL_FINANCIAL_OLDER_WORDING_V1'

def _with_globals(function, **overrides):
    namespace = {**function.__globals__, **overrides}
    made = types.FunctionType(function.__code__, namespace, function.__name__,
                              function.__defaults__, function.__closure__)
    made.__kwdefaults__ = function.__kwdefaults__
    return made

def _known_form(function, substitutions, **overrides):
    source = inspect.getsource(function)
    for old, new in substitutions:
        if source.count(old) != 1:
            raise ValueError('HISTORICAL_BANK_SCOPE_FORM_NO_LONGER_MATCHES:' + function.__name__)
        source = source.replace(old, new)
    namespace = {**function.__globals__, **overrides}
    exec(compile(source, function.__code__.co_filename, 'exec', dont_inherit=True), namespace)
    return namespace[function.__name__]

GLOSSARY_COLON = (
    ("""match = re.fullmatch(r'AUM [“"]Assets under management[”"]: Represent""",
     """match = re.fullmatch(r'AUM:? [“"]Assets under management[”"]: Represent"""),)

SEGMENT_LIST = (
    ("""r"(.+?)\\s*[–—-]\\s*with the remaining activities in", block["visible_text"], re.I)""",
     """r"(.+?)\\s*[–—-]\\s*with the remaining activities in", block["visible_text"], re.I) or re.search(
            r"There are (?:[0-9]+|two|three|four|five|six) major reportable business segments\\s*[–—-]\\s*"
            r"(.+?)\\.\\s*In addition, there is a Corporate segment\\b", block["visible_text"], re.I)"""),)

MARKETS_NAME = (
    ("""elif _clean(label["text"]) == "net yield on average interest-earning assets excluding markets":""",
     """elif re.fullmatch(r"net yield on average interest-earning assets excluding (?:cib )?markets",
                                      _clean(label["text"])):"""),
    ("""and "excluding Markets, as shown below" in text""",
     """and re.search(r"excluding (?:CIB )?Markets, as shown below", text)"""),
)

TABLE_OF_CONTENTS = (
    ("""                    elif re.search(r"\\bcriticized\\b.*\\bretained\\b|\\bsecured by real estate\\b", label["text"], re.I):""",
     """                    elif (column is None and (contents := _nearest_table_introduction(structure, table))
                          and re.search(r"\\bTable of Contents$", contents["visible_text"], re.I)):
                        item.update(disposition="SOURCE_NAMED_TABLE_OF_CONTENTS", navigation_heading=contents)
                    elif re.search(r"\\bcriticized\\b.*\\bretained\\b|\\bsecured by real estate\\b", label["text"], re.I):"""),
)

FALLBACK_BY_NAME = (
    ("""    from .financial_relationships import inspect_nonaccrual_loan_ratio
""", ""),)

def _older_nim(**arguments):
    return _known_form(relationships.inspect_nim_relationships, MARKETS_NAME)(**arguments)


def _older_aum(**arguments):
    segments = _known_form(relationships._reported_segment_sections, SEGMENT_LIST)
    definitions = _known_form(balances._aum_definitions, GLOSSARY_COLON)
    scope = _with_globals(balances._aum_reported_scope,
                         _aum_definitions=definitions, _reported_segment_sections=segments)
    return _with_globals(balances.inspect_aum_balance,
                         _aum_definitions=definitions, _aum_reported_scope=scope)(**arguments)


def _older_nonaccrual(**arguments):
    segments = _known_form(relationships._reported_segment_sections, SEGMENT_LIST)
    return _known_form(relationships.inspect_nonaccrual_loan_ratio, TABLE_OF_CONTENTS,
                       _reported_segment_sections=segments)(**arguments)


def _older_a09(**arguments):
    # The original import must read the local fallback without changing its
    # native-first control flow or the shared structured inspector.
    return _known_form(structured.inspect_ordinary_a09_source_fact, FALLBACK_BY_NAME,
                       inspect_nonaccrual_loan_ratio=_older_nonaccrual)(**arguments)


def _resolved(metric_id, component):
    return (component['outcome'] in {'STRUCTURED_PRIMARY_RESOLVED', 'HTML_FALLBACK_SOURCE_SEMANTIC_FACT'}
            if metric_id == 'A09' else component['semantic_status'] == 'SINGLE_SOURCE_SEMANTIC_FACT')


def inspect_historical_bank_scope(*, metric_id, **arguments):
    functions = {'A04': relationships.inspect_nim_relationships,
                 'A09': structured.inspect_ordinary_a09_source_fact,
                 'A11': balances.inspect_aum_balance}
    if metric_id not in functions:
        raise ValueError('HISTORICAL_BANK_SCOPE_WORDING_FAMILY_NOT_RECEIVED')
    original = functions[metric_id](**arguments)
    if _resolved(metric_id, original):
        return original
    older = {'A04': _older_nim, 'A09': _older_a09, 'A11': _older_aum}[metric_id](**arguments)
    if not _resolved(metric_id, older):
        return original
    forms = {'A04': ['MARKETS_NAME'], 'A09': ['SEGMENT_LIST','TABLE_OF_CONTENTS','FALLBACK_BY_NAME'],
             'A11': ['GLOSSARY_COLON','SEGMENT_LIST']}
    return {**older, 'historical_older_wording': {'rule': RULE, 'forms': forms[metric_id],
        'frozen_inspector_status': {key: original[key] for key in
            ('status','semantic_status','outcome','whole_issuer_scope_status') if key in original},
        'taken_because': 'FROZEN_INSPECTOR_UNRESOLVED_AND_OLDER_WORDING_RESOLVED'}}
