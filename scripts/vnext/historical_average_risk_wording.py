"""Reuse only the three already-validated LCR/VaR historical wording forms.

The shared inspectors still own source/entity/period/amount/scope checks. Local
function namespaces substitute the existing note reader and counterfactual
header grammar without mutating shared module globals. This finite adapter
keeps the original answer unless the original is unresolved and these known
forms resolve it. It is not a general version installer or extraction core.
"""
import inspect
import types
from . import financial_candidates as candidates
from . import financial_balance_scope as balances
from . import financial_duration as duration

RULE = 'HISTORICAL_FINANCIAL_OLDER_WORDING_V1'
RESOLVED = 'SINGLE_SOURCE_SEMANTIC_FACT'

def _with_globals(function, **overrides):
    namespace = dict(function.__globals__)
    namespace.update(overrides)
    made = types.FunctionType(function.__code__, namespace, function.__name__,
                              function.__defaults__, function.__closure__)
    made.__kwdefaults__ = function.__kwdefaults__
    return made

def _known_form(function, substitutions, **overrides):
    # Compile just this existing function with the same three literal repairs
    # as the retained implementation; no recursive module or DEI rewriting.
    source = inspect.getsource(function)
    for old, new in substitutions:
        if source.count(old) != 1:
            raise ValueError('HISTORICAL_WORDING_FORM_NO_LONGER_MATCHES:' + function.__name__)
        source = source.replace(old, new)
    namespace = {**function.__globals__, **overrides}
    exec(compile(source, function.__code__.co_filename, 'exec', dont_inherit=True), namespace)
    return namespace[function.__name__]

GENERAL_NOTE = (
    ("""    notes = {}
""", """    notes, general = {}, []
"""),
    ("""        if match is None:
            break
""", """        if match is None:
            if notes or general or not _text(block["visible_text"]).endswith("."):
                break
            general.append(block)
            continue
"""),
)

MEASURE_ABBREVIATION = (
    (r'''        r"\bpercentage\s+represents\s+(?:average\s+)?ratios?\s+for\b",''',
     r'''        r"\bpercentage\s+represents\s+(?:average\s+)?(?:ratios?" + "".join(
            "|" + re.escape(name) for name in
            (re.findall(r"\(\s*[“\"]([A-Za-z]{2,10})[”\"]\s*\)", label["text"]) if label else []))
        + r")\s+for\b",'''),)

COUNTERFACTUAL_HEADER = (
    ("""and _clean(c["text"]) == "amounts by which reported average var would have been lower for the years ended:\"""",
     """and _clean(c["text"]) in ("amounts by which reported average var would have been lower for the years ended:",
                                    "amount by which reported average var would have been higher")"""),
    ("""item.update(disposition="COUNTERFACTUAL_REDUCTION_AMOUNT_NOT_REPORTED_TOTAL",""",
     """item.update(disposition="COUNTERFACTUAL_" + ("INCREASE" if _clean(counterfactual[0]["text"]).endswith("higher")
                                                              else "REDUCTION") + "_AMOUNT_NOT_REPORTED_TOTAL","""),
)

def _older_lcr(**arguments):
    notes = _known_form(duration._linked_notes, GENERAL_NOTE)
    interval = _known_form(duration.inspect_financial_duration, MEASURE_ABBREVIATION,
                           _linked_notes=notes)
    discovery = _with_globals(candidates.inspect_financial_candidates,
                              inspect_financial_duration=interval)
    inspector = _with_globals(candidates.inspect_lcr_disclosed_fact,
                             inspect_financial_candidates=discovery)
    return inspector(**arguments)


def _older_var(**arguments):
    return _known_form(balances.inspect_total_var, COUNTERFACTUAL_HEADER)(**arguments)


def _resolved(metric_id, component):
    field = 'status' if metric_id == 'A03' else 'semantic_status'
    return component[field] == RESOLVED


def inspect_historical_average_risk(*, metric_id, **arguments):
    if metric_id not in {'A03', 'A12'}:
        raise ValueError('HISTORICAL_AVERAGE_RISK_WORDING_FAMILY_NOT_RECEIVED')
    original = (candidates.inspect_lcr_disclosed_fact if metric_id == 'A03'
                else balances.inspect_total_var)(**arguments)
    if _resolved(metric_id, original):
        return original
    older = (_older_lcr if metric_id == 'A03' else _older_var)(**arguments)
    if not _resolved(metric_id, older):
        return original
    return {**older, 'historical_older_wording': {
        'rule': RULE,
        'forms': ['GENERAL_NOTE', 'MEASURE_ABBREVIATION'] if metric_id == 'A03'
                 else ['COUNTERFACTUAL_HEADER'],
        'frozen_inspector_status': {key: original[key] for key in
            ('status', 'semantic_status', 'outcome', 'whole_issuer_scope_status') if key in original},
        'taken_because': 'FROZEN_INSPECTOR_UNRESOLVED_AND_OLDER_WORDING_RESOLVED'}}
