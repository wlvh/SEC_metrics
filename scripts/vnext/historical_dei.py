"""DEI facts on #47's historical paths, whichever DEI taxonomy release a filing declares.

Purpose: The frozen readers take a fact as a DEI fact only when its namespace is
``http://xbrl.sec.gov/dei/`` followed by four digits - the form the SEC's DEI
taxonomy releases have had since 2022. Earlier releases were named with a full
date after the year, or with a quarter (``2021q4``). Every filing the
repository held before Issue #47's acquisition was filed in 2023 or later, so
the four-digit form never met another. The five-year frame reaches annual
reports filed in 2021 and 2022, and the first live acquisition met them at once:
Enphase's FY2020 annual report declares a release named by its date and its
FY2021 report ``dei/2021q4``, each with exactly one DocumentType fact, and the
frozen reader reported that fact missing (DEI_MISSING_OR_AMBIGUOUS:DocumentType). That
stopped every company's planner once its older annual reports arrived, and
every position of an older year.

What the check is for is kept: a filer's own extension concept named like a DEI
element is not a DEI fact. Only the release suffix is widened, to the three
forms the releases have used - none, a quarter, or a date.

How: the frozen readers ask this one question with ``re.fullmatch`` and one of
two literal patterns, in eleven modules, inside functions that #47 reaches
through other frozen functions - the annual reader, the fiscal-year label scan,
the text document builder, the business-text source binder, the governance and
amendment readers, the financial issuer check and the going-concern source.
``release_aware(obj)`` is what #47 calls in place of such an object. For a
function whose calls can reach the question it is a view: each call runs the
function's own code object in its module's namespace as it is at that moment,
with two kinds of difference and no other. Where the code asks the question,
``re`` is the release-aware view below. Every name the code reads, and every
name it imports inside its body, whose object can itself reach the question -
a function, a class, a module, a registry - is that object's view. An object
whose calls cannot reach the question is returned unchanged. So on every
filing whose DEI namespace is ``dei/`` and four digits a view answers exactly
as the frozen function does; the widened pattern accepts nothing else those
filings contain.

The namespace is read from the module on every call, so a test that patches a
frozen module sees its patch on these paths as well. A reference a view cannot
redirect - a default argument, a closure cell, a wrapper - that can reach the
question is refused by name, as is any other way of asking it than
``re.fullmatch``: a view that silently kept the frozen answer somewhere would
read as a fix. The frozen modules are not changed; Issue #28's generations
record their bytes.

The executive-compensation (ECD) taxonomy namespace is the same question with
the same three release suffixes (``ecd/2022q4`` is the 2023 proxies' release)
and is answered by the same view. So is the FASB's US GAAP namespace, whose
releases through 2021 carry the release date after the year
(``us-gaap/<year>-<month>-<day>``).

Call relationships: #47's route modules call the frozen readers through
``release_aware``. ``unviewed_references`` is the check that they do: it lists
what a #47 function reaches that can ask the question without a view.
``release_aware_with`` is the same view with some of the names the frozen
code reads bound to a successor (C02's proxy identity, D02's note navigation);
``overrides_of`` tells which.
"""
import builtins
import dis
import functools
import importlib
import re
import sys
import types

from . import fiscal_year_labels as _frozen_labels
from . import normal_annual_input as _frozen_annual

PACKAGE = __name__.rpartition(".")[0]
# The frozen readers' DEI namespace patterns, as they spell them.
FROZEN_DEI_NAMESPACE_PATTERNS = (r"https?://xbrl\.sec\.gov/dei/\d{4}",
                                 r"https?://xbrl\.sec\.gov/dei/[0-9]{4}")
# The releases' own suffixes: none (2022 onward), a quarter (2021q4) or a month
# and day after the year. Anything else is not the SEC's DEI taxonomy.
DEI_NAMESPACE_PATTERN = r"https?://xbrl\.sec\.gov/dei/\d{4}(?:q[1-4]|-\d{2}-\d{2})?"
# The same question about the SEC's executive-compensation (ECD) taxonomy, which
# the frozen C03 resolver and the Part III amendment check ask. Its first
# release is named with a quarter (``ecd/2022q4``, the 2023 proxies); the
# frozen readers accept only four digits, so a 2023 proxy's pay-versus-
# performance facts read as not ECD (C03_ECD_TAXONOMY_REQUIRED). The same three
# suffixes are accepted and nothing else.
FROZEN_ECD_NAMESPACE_PATTERNS = (r"https?://xbrl\.sec\.gov/ecd/\d{4}",
                                 r"https?://xbrl\.sec\.gov/ecd/[0-9]{4}")
ECD_NAMESPACE_PATTERN = r"https?://xbrl\.sec\.gov/ecd/\d{4}(?:q[1-4]|-\d{2}-\d{2})?"
# The same question about the FASB's US GAAP taxonomy, which the frozen B06
# routes, B03's contract-amortization check and the successor income input ask
# of a fact's concept. Releases through 2021 are named with the release date
# after the year (the form every FY2021 annual report here declares); from 2022
# the year alone. The frozen readers accept only the year, so once
# the older annual reports' XBRL instances were acquired, every B06 position of
# FY2021 stopped at B06_GUARD_EQUITY_NAMESPACE_CONFLICT instead of reading the
# equity it was asking about. The date form is accepted and nothing else.
FROZEN_US_GAAP_NAMESPACE_PATTERNS = (r"https?://fasb\.org/us-gaap/[0-9]{4}",
                                     r"https?://fasb\.org/us-gaap/\d{4}")
US_GAAP_NAMESPACE_PATTERN = r"https?://fasb\.org/us-gaap/[0-9]{4}(?:-\d{2}-\d{2})?"
# The FASB's SRT taxonomy is released with US GAAP and named the same way
# (``srt/<year>-<month>-<day>`` through 2021). No frozen code holds the pattern
# as a constant; the accession policy file spells it
# (config/normal_accession_metrics_v1.json), and the bank capital ratios'
# required scope names an SRT axis, so a bank's ratios in a report of that era
# stopped at NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED. Read through
# ``release_aware_pattern``.
FROZEN_SRT_NAMESPACE_PATTERNS = (r"https?://fasb\.org/srt/[0-9]{4}",)
SRT_NAMESPACE_PATTERN = r"https?://fasb\.org/srt/[0-9]{4}(?:-\d{2}-\d{2})?"
_WIDENED = {**{p: DEI_NAMESPACE_PATTERN for p in FROZEN_DEI_NAMESPACE_PATTERNS},
            **{p: ECD_NAMESPACE_PATTERN for p in FROZEN_ECD_NAMESPACE_PATTERNS},
            **{p: US_GAAP_NAMESPACE_PATTERN for p in FROZEN_US_GAAP_NAMESPACE_PATTERNS},
            **{p: SRT_NAMESPACE_PATTERN for p in FROZEN_SRT_NAMESPACE_PATTERNS}}
_CONTAINERS = (dict, list, tuple, set, frozenset)
_ATTRIBUTE_LOADS = ("LOAD_ATTR", "LOAD_METHOD")
_NAME_LOADS = ("LOAD_GLOBAL", "LOAD_NAME", "LOAD_FAST", "LOAD_DEREF")


class HistoricalDeiError(ValueError):
    """A reference on a historical path would keep the frozen DEI answer."""


def is_dei_namespace(uri):
    """Whether ``uri`` is a release of the SEC's DEI taxonomy."""
    return re.fullmatch(DEI_NAMESPACE_PATTERN, str(uri)) is not None


def is_ecd_namespace(uri):
    """Whether ``uri`` is a release of the SEC's executive-compensation (ECD) taxonomy."""
    return re.fullmatch(ECD_NAMESPACE_PATTERN, str(uri)) is not None


def is_us_gaap_namespace(uri):
    """Whether ``uri`` is a release of the FASB's US GAAP taxonomy."""
    return re.fullmatch(US_GAAP_NAMESPACE_PATTERN, str(uri)) is not None


def _frozen_pattern(pattern):
    return isinstance(pattern, str) and pattern in _WIDENED


def release_aware_pattern(pattern):
    """The release-aware form of a frozen namespace pattern a policy file spells.

    The view answers a frozen pattern held in code; a pattern read from a
    policy file is data the view cannot see, so a successor that passes the
    policy to the frozen reader asks for each pattern's release-aware form
    here. Anything that is not one of the frozen patterns is refused by name:
    widening an arbitrary pattern would read as a release fix.
    """
    if not _frozen_pattern(pattern):
        raise HistoricalDeiError("HISTORICAL_DEI_NOT_A_FROZEN_NAMESPACE_PATTERN:" + repr(pattern)[:120])
    return _WIDENED[pattern]


class _ReleaseAwareRe:
    """``re`` for frozen code, with the DEI namespace question answered for every release.

    ``fullmatch`` with one of the frozen DEI namespace patterns is answered with
    the widened pattern. Any other function of ``re`` given one of those
    patterns is refused: the frozen code asks the question only through
    ``fullmatch``, and an answer by another function would be the frozen one.
    Every other call and attribute is the standard library's.
    """

    def fullmatch(self, pattern, string, flags=0):
        if _frozen_pattern(pattern) and flags == 0:
            pattern = _WIDENED[pattern]
        return re.fullmatch(pattern, string, flags)

    def __getattr__(self, name):
        value = getattr(re, name)
        if not callable(value) or isinstance(value, type):
            return value

        def guarded(*args, **kwargs):
            if (args and _frozen_pattern(args[0])) or _frozen_pattern(kwargs.get("pattern")):
                raise HistoricalDeiError("HISTORICAL_DEI_QUESTION_ASKED_THROUGH:re." + name)
            return value(*args, **kwargs)
        return functools.wraps(value)(guarded)


RELEASE_AWARE_RE = _ReleaseAwareRe()
_REAL_IMPORT = builtins.__import__


def _codes(code):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from _codes(constant)


def asks_the_dei_question(function):
    """Whether the function's own code holds one of the frozen DEI or ECD namespace patterns."""
    return isinstance(function, types.FunctionType) and any(
        pattern in code.co_consts for code in _codes(function.__code__)
        for pattern in _WIDENED)


def _in_package(obj):
    module = getattr(obj, "__module__", None)
    return isinstance(module, str) and (module == PACKAGE or module.startswith(PACKAGE + "."))


def _package_module(obj):
    return isinstance(obj, types.ModuleType) and (
        obj.__name__ == PACKAGE or obj.__name__.startswith(PACKAGE + "."))


# Views, and every original viewed, are kept here for the life of the process:
# ids identify objects only while they live.
_VIEWS = {}
_VIEW_IDS = set()
_REACH = {}


def _is_view(obj):
    return id(obj) in _VIEW_IDS


def _attribute(module, name):
    value = getattr(module, name, None)
    if value is None and _package_module(module):
        value = importlib.import_module(module.__name__ + "." + name)
    return value


def _imported(function, name, level, fromlist):
    """The module an import statement inside ``function`` returns, when it names this
    package: the named module with a from-list, otherwise the top-level package."""
    if level:
        package = function.__globals__.get("__package__") or ""
        return importlib.import_module("." * level + name, package=package)
    if name == PACKAGE or name.startswith(PACKAGE + "."):
        module = importlib.import_module(name)
        return module if fromlist else sys.modules[name.partition(".")[0]]
    return None


def _load_chains(code):
    """(opname, name, attributes) for each name load and the attribute loads that follow it."""
    instructions = list(dis.get_instructions(code))
    chains, index = [], 0
    while index < len(instructions):
        instruction = instructions[index]
        index += 1
        if instruction.opname not in _NAME_LOADS:
            continue
        attributes = []
        while index < len(instructions) and instructions[index].opname in _ATTRIBUTE_LOADS:
            attributes.append(instructions[index].argval)
            index += 1
        chains.append((instruction.opname, instruction.argval, attributes))
    return chains


def _function_references(function):
    """What ``function``'s code reaches by name.

    Globals it loads, the attributes it loads from this package's modules -
    named as globals or imported inside the body - the names it imports, its
    closure cells and defaults, and the function it wraps.
    """
    namespace, found = function.__globals__, []
    for code in _codes(function.__code__):
        instructions = list(dis.get_instructions(code))
        local = {}
        for index, instruction in enumerate(instructions):
            if instruction.opname != "IMPORT_NAME":
                continue
            module = _imported(function, instruction.argval, instructions[index - 2].argval,
                               instructions[index - 1].argval)
            if module is None:
                continue
            found.append(module)
            following = instructions[index + 1:]
            if following and following[0].opname == "STORE_FAST":
                local[following[0].argval] = module
            for position, later in enumerate(following):
                if later.opname != "IMPORT_FROM":
                    if later.opname in ("STORE_FAST", "STORE_NAME", "STORE_GLOBAL"):
                        continue
                    break
                value = _attribute(module, later.argval)
                found.append(value)
                if position + 1 < len(following) and following[position + 1].opname == "STORE_FAST":
                    local[following[position + 1].argval] = value
        for opname, name, attributes in _load_chains(code):
            if opname in ("LOAD_GLOBAL", "LOAD_NAME"):
                if name not in namespace:
                    continue
                value = namespace[name]
            elif name in local:
                value = local[name]
            else:
                continue
            found.append(value)
            for attribute in attributes:
                if not _package_module(value):
                    break
                value = vars(value).get(attribute)
                if value is None:
                    break
                found.append(value)
    found.extend(_held_cells(function))
    found.extend(function.__defaults__ or ())
    found.extend((function.__kwdefaults__ or {}).values())
    if hasattr(function, "__wrapped__"):
        found.append(function.__wrapped__)
    return found


def _held_cells(function):
    """What the function's closure cells hold, except zero-argument ``super``'s class.

    That cell names the class whose method this is, and ``super()`` uses it
    only to find the next class in the instance's own order; it is not a call.
    """
    held = []
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or ()):
        if name == "__class__":
            continue
        try:
            held.append(cell.cell_contents)
        except ValueError:
            continue
    return held


def _members(klass):
    for name, member in vars(klass).items():
        if isinstance(member, (staticmethod, classmethod)):
            yield name, member.__func__
        elif isinstance(member, property):
            for accessor in (member.fget, member.fset, member.fdel):
                if accessor is not None:
                    yield name, accessor
        elif isinstance(member, (types.FunctionType, type)):
            yield name, member


def _successors(obj):
    if _is_view(obj):
        return []
    if isinstance(obj, types.FunctionType):
        references = _function_references(obj)
    elif isinstance(obj, type):
        references = [member for owner in obj.__mro__ if _in_package(owner)
                      for _, member in _members(owner)]
    elif isinstance(obj, dict):
        references = list(obj.values())
    elif isinstance(obj, _CONTAINERS):
        references = list(obj)
    elif isinstance(obj, types.MethodType):
        references = [obj.__func__]
    elif isinstance(obj, functools.partial):
        references = [obj.func, *obj.args, *obj.keywords.values()]
    else:
        references = [obj.__wrapped__] if hasattr(obj, "__wrapped__") else []
    return [r for r in references if _followed(r)]


def _followed(obj):
    if _is_view(obj):
        return True
    if getattr(obj, "__module__", None) == __name__:
        return False  # the views' own machinery, not a path to the question
    if isinstance(obj, types.FunctionType):
        return _in_package(obj) or hasattr(obj, "__wrapped__")
    if isinstance(obj, type):
        return _in_package(obj)
    return isinstance(obj, _CONTAINERS + (types.MethodType, functools.partial)) or (
        not isinstance(obj, types.ModuleType) and hasattr(obj, "__wrapped__"))


def reaches_the_dei_question(obj):
    """Whether calling ``obj``, or anything it can call, can ask the frozen DEI question.

    Strongly connected references are decided together (Tarjan), so a
    recursive helper and its caller get one answer.
    """
    if not _followed(obj):
        return False
    known = _REACH.get(id(obj))
    if known is not None:
        return known[1]
    index, low, stack, on_stack, successors, counter = {}, {}, [], set(), {}, [0]

    def enter(node):
        key = id(node)
        index[key] = low[key] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(key)
        successors[key] = _successors(node)
        return iter(successors[key])

    work = [(obj, enter(obj))]
    while work:
        node, pending = work[-1]
        descended = False
        for child in pending:
            key = id(child)
            if key in _REACH:
                continue
            if key not in index:
                work.append((child, enter(child)))
                descended = True
                break
            if key in on_stack:
                low[id(node)] = min(low[id(node)], index[key])
        if descended:
            continue
        work.pop()
        if work:
            parent = id(work[-1][0])
            low[parent] = min(low[parent], low[id(node)])
        if low[id(node)] != index[id(node)]:
            continue
        component = []
        while True:
            member = stack.pop()
            on_stack.discard(id(member))
            component.append(member)
            if member is node:
                break
        inside = {id(member) for member in component}
        value = any(asks_the_dei_question(member) and not _is_view(member)
                    for member in component) or any(
            _REACH[id(child)][1] for member in component for child in successors[id(member)]
            if id(child) not in inside)
        for member in component:
            _REACH[id(member)] = (member, value)
    return _REACH[id(obj)][1]


class _ModuleView:
    """A package module as a view sees it: each attribute is ``release_aware`` of itself."""

    __slots__ = ("_module",)

    def __init__(self, module):
        object.__setattr__(self, "_module", module)

    def __getattr__(self, name):
        return release_aware(getattr(self._module, name))

    def __setattr__(self, name, value):
        raise HistoricalDeiError("HISTORICAL_DEI_MODULE_VIEW_IS_READ_ONLY:" + name)

    def __repr__(self):
        return "<release-aware view of " + repr(self._module) + ">"


def _view_import(name, globals=None, locals=None, fromlist=(), level=0):
    """``__import__`` inside a view: this package's modules come back as module views."""
    module = _REAL_IMPORT(name, globals, locals, fromlist, level)
    return release_aware(module) if _package_module(module) else module


_VIEW_BUILTINS = {**vars(builtins), "__import__": _view_import}


def _refuse_unredirectable(function):
    """A reference a per-call namespace cannot redirect must not reach the question."""
    held = [*_held_cells(function), *(function.__defaults__ or ()),
            *(function.__kwdefaults__ or {}).values()]
    for value in held:
        if not _is_view(value) and reaches_the_dei_question(value):
            raise HistoricalDeiError("HISTORICAL_DEI_REFERENCE_NOT_REBINDABLE:"
                                     + function.__module__ + ":" + function.__qualname__)
    if asks_the_dei_question(function):
        names = set().union(*(code.co_names for code in _codes(function.__code__)))
        if "re" not in names or function.__globals__.get("re") is not re:
            raise HistoricalDeiError("HISTORICAL_DEI_QUESTION_NOT_ASKED_THROUGH_RE:"
                                     + function.__module__ + ":" + function.__qualname__)


def _function_view(function, overrides=None):
    module = sys.modules[function.__module__]
    if module.__dict__ is not function.__globals__:
        raise HistoricalDeiError("HISTORICAL_DEI_FUNCTION_OUTSIDE_ITS_MODULE:"
                                 + function.__module__ + ":" + function.__qualname__)
    _refuse_unredirectable(function)
    asks = asks_the_dei_question(function)
    names = sorted(set().union(*(code.co_names for code in _codes(function.__code__))))
    imports = any(instruction.opname == "IMPORT_NAME" for code in _codes(function.__code__)
                  for instruction in dis.get_instructions(code))
    overrides = dict(overrides or {})

    def view(*args, **kwargs):
        namespace = dict(vars(module))
        for name in names:
            if name in namespace:
                namespace[name] = release_aware(namespace[name])
        if asks:
            namespace["re"] = RELEASE_AWARE_RE
        if imports:
            namespace["__builtins__"] = _VIEW_BUILTINS
        namespace.update(overrides)
        runnable = types.FunctionType(function.__code__, namespace, function.__name__,
                                      function.__defaults__, function.__closure__)
        runnable.__kwdefaults__ = function.__kwdefaults__
        return runnable(*args, **kwargs)

    functools.update_wrapper(view, function)
    view.release_aware_view_of = function
    return view


# Views with overrides, kept for the life of the process like the others.
_OVERRIDE_VIEWS = {}


def release_aware_with(function, **overrides):
    """``release_aware(function)`` with some of the names its own code reads bound otherwise.

    For a successor that replaces one helper a frozen function calls and keeps
    everything else the frozen function does: each call is the frozen code in
    its module's namespace as the release-aware view sees it, then the named
    globals replaced. Only a name the function's own code reads can be
    replaced - naming another would change nothing and read as a change - and
    a replacement that can itself ask the frozen DEI question without a view
    is refused, so an override cannot carry the frozen answer back in.
    """
    if not (isinstance(function, types.FunctionType) and _in_package(function)
            and not hasattr(function, "__wrapped__")):
        raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_TARGET_NOT_A_PACKAGE_FUNCTION:"
                                 + repr(function)[:120])
    read = set().union(*(code.co_names for code in _codes(function.__code__)))
    unread = sorted(set(overrides) - read)
    if unread:
        raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_NAME_NOT_READ:"
                                 + function.__qualname__ + ":" + ",".join(unread))
    # A name the code only imports inside its body is bound by that import,
    # never read from the namespace the view replaces: an override of it would
    # change nothing and read as a change.
    loaded = {instruction.argval for code in _codes(function.__code__)
              for instruction in dis.get_instructions(code)
              if instruction.opname in ("LOAD_GLOBAL", "LOAD_NAME")}
    imported_only = sorted(set(overrides) - loaded)
    if imported_only:
        raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_NAME_ONLY_IMPORTED:"
                                 + function.__qualname__ + ":" + ",".join(imported_only))
    for name, value in overrides.items():
        if not _is_view(value) and reaches_the_dei_question(value):
            raise HistoricalDeiError("HISTORICAL_DEI_OVERRIDE_REACHES_THE_QUESTION:" + name)
    key = (id(function), tuple(sorted((name, id(value)) for name, value in overrides.items())))
    known = _OVERRIDE_VIEWS.get(key)
    if known is None:
        view = _function_view(function, overrides)
        # The originals are kept with the view so the ids in the key stay theirs.
        known = (function, dict(overrides), view)
        _OVERRIDE_VIEWS[key] = known
        _VIEW_IDS.add(id(view))
    return known[2]


def overrides_of(view):
    """The names ``release_aware_with`` bound for ``view``, or None if it has none."""
    for function, overrides, known in _OVERRIDE_VIEWS.values():
        if known is view:
            return dict(overrides)
    return None


def _class_view(klass):
    for owner in klass.__mro__[1:]:
        if _in_package(owner) and any(reaches_the_dei_question(member)
                                      for _, member in _members(owner)):
            raise HistoricalDeiError("HISTORICAL_DEI_INHERITED_MEMBER_REACHES:"
                                     + klass.__module__ + ":" + klass.__qualname__)
    body = {"__module__": klass.__module__, "__qualname__": klass.__qualname__,
            "__doc__": klass.__doc__, "release_aware_view_of": klass}
    for name, member in vars(klass).items():
        target = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
        if isinstance(member, property) and any(
                reaches_the_dei_question(accessor)
                for accessor in (member.fget, member.fset, member.fdel) if accessor is not None):
            raise HistoricalDeiError("HISTORICAL_DEI_PROPERTY_REACHES:" + klass.__qualname__
                                     + "." + name)
        if isinstance(target, (types.FunctionType, type)) and reaches_the_dei_question(target):
            viewed = release_aware(target)
            body[name] = type(member)(viewed) if isinstance(
                member, (staticmethod, classmethod)) else viewed
    return type(klass.__name__, (klass,), body)


def release_aware(obj):
    """What #47's historical paths use in place of ``obj``; see the module docstring.

    ``obj`` itself when nothing it can call asks the frozen DEI question.
    """
    if _package_module(obj):
        known = _VIEWS.get(id(obj))
        if known is None:
            known = (obj, _ModuleView(obj))
            _VIEWS[id(obj)] = known
            _VIEW_IDS.add(id(known[1]))
        return known[1]
    if _is_view(obj) or not reaches_the_dei_question(obj):
        return obj
    if isinstance(obj, dict):
        return {key: release_aware(value) for key, value in obj.items()}
    if isinstance(obj, _CONTAINERS):
        return type(obj)(release_aware(value) for value in obj)
    known = _VIEWS.get(id(obj))
    if known is not None:
        return known[1]
    if (isinstance(obj, types.FunctionType) and _in_package(obj)
            and not hasattr(obj, "__wrapped__")):
        view = _function_view(obj)
    elif isinstance(obj, type):
        view = _class_view(obj)
    else:
        raise HistoricalDeiError("HISTORICAL_DEI_REFERENCE_NOT_REBINDABLE:" + type(obj).__name__
                                 + ":" + repr(obj)[:120])
    _VIEWS[id(obj)] = (obj, view)
    _VIEW_IDS.add(id(view))
    return view


def unviewed_references(obj, *, own_modules):
    """What a #47 function or class reaches directly that can ask the frozen DEI question
    without a view. Functions of ``own_modules`` - #47's own - are not listed: each is
    checked itself."""
    if isinstance(obj, type):
        references = [member for _, member in _members(obj)]
    else:
        references = _function_references(obj)
    return [reference for reference in references
            if _followed(reference) and not _is_view(reference)
            and getattr(reference, "__module__", None) not in own_modules
            and reaches_the_dei_question(reference)]


# The annual reader, and the fiscal-year label inspection a pinned annual input
# runs, which re-reads the period and collects the DEI facts' spans.
annual_period = release_aware(_frozen_annual.annual_period)
inspect_prepared_fiscal_year_labels = release_aware(_frozen_labels._inspect_prepared_input)
