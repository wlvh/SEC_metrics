"""Pinned receiver of #47's pending D01 running-header substitutions.

Source: af29ab2f41f40a442c13a3453c97d2c476f3536b,
docs/evidence/issue47_history/pending-rule-changes/d01-running-header.patch.
The small source compiler is copied from historical_financial_wording.successor
at that commit; only its D01 targets/error names and receiver import differ.
No financial/history engine or mutable provider path is a dependency.
"""
import inspect
from pathlib import Path
import types

from . import risk_signals as frozen_signals
from . import text_results as frozen_text

PEER_SHA = 'af29ab2f41f40a442c13a3453c97d2c476f3536b'
SEVERAL_PARTS = ((r'part\s+[ivx]+$)', r'part\s+[ivx]+$|parts\s+[ivx]+\s+and\s+[ivx]+$)'),)
SELECTOR_IMPORT = (('from .risk_signals import risk_factor_headings',
                    'from .d01_running_header_28_v1 import risk_factor_headings'),)


def _need(condition, reason):
    if not condition:
        raise ValueError('D01_SUCCESSOR_' + reason)


def _function_codes(code, name, first_line):
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            if constant.co_name == name and constant.co_firstlineno == first_line:
                yield constant
            yield from _function_codes(constant, name, first_line)


def _compiled(function, source):
    module = compile(source, function.__code__.co_filename, 'exec', dont_inherit=True)
    found = list(_function_codes(module, function.__name__, function.__code__.co_firstlineno))
    _need(len(found) == 1, 'FUNCTION_NOT_FOUND:' + function.__qualname__)
    return found[0]


def _successor(function, substitutions):
    _need(function in (frozen_signals.risk_factor_headings, frozen_text._derive_deterministic_candidate)
          and isinstance(function, types.FunctionType) and function.__closure__ is None
          and function.__qualname__ == function.__name__, 'TARGET_INVALID')
    source = Path(function.__code__.co_filename).read_text(encoding='utf-8')
    _need(_compiled(function, source) == function.__code__, 'SOURCE_IS_NOT_LOADED_CODE')
    lines, first = inspect.getsourcelines(function)
    module_lines = source.splitlines(keepends=True)
    before = ''.join(module_lines[:first - 1])
    body = ''.join(module_lines[first - 1:first - 1 + len(lines)])
    after = ''.join(module_lines[first - 1 + len(lines):])
    _need(body == ''.join(lines) and bool(substitutions), 'SOURCE_SPAN_OR_SUBSTITUTIONS_INVALID')
    for old, new in substitutions:
        _need(body.count(old) == 1, 'SUBSTITUTION_NOT_FOUND_ONCE')
        body = body.replace(old, new)
    made = types.FunctionType(_compiled(function, before + body + after), function.__globals__,
                              function.__name__, function.__defaults__, function.__closure__)
    made.__kwdefaults__ = function.__kwdefaults__
    made.__qualname__ = function.__qualname__
    made.historical_substitutions = tuple(substitutions)
    return made


risk_factor_headings = _successor(frozen_signals.risk_factor_headings, SEVERAL_PARTS)
derive_candidate = _successor(frozen_text._derive_deterministic_candidate, SELECTOR_IMPORT)
