"""One native XBRL parse per exact document bytes while a block is open.

Purpose: ``deterministic_router.parse_accession_xbrl_source`` runs two HTML
parsers over a whole inline-XBRL document and returns an immutable object - a
frozen dataclass whose contexts and facts are read-only mappings and tuples,
named by the bytes' SHA-256 and length. It reads nothing but the bytes it is
handed. The frozen chains ask it again for the same filing at nearly every
step - the annual period, the fiscal-year labels, the equity rebuild, the
amendment scope, the text document, each B06 grammar - so one module of B06's
cascade cases made 356 parses of 17 distinct documents, and the period cases
153 of 8; the parses were about two fifths of the B06 module's profiled time.

Inside this block every module binding of the parser answers once per
(SHA-256, length) of the bytes: the first call runs the frozen parser, later
calls with the same bytes get the same object. Sharing it is safe because
nothing can change it, and a fresh parse of the same bytes gives an object with
the same SHA-256, length and parsed-source id and equal contexts and facts,
which the cases check. A call whose argument is not ``bytes`` goes to the
frozen parser, which refuses it as before; a call that raises is not
remembered. The block holds a bounded number of documents, oldest dropped
first - a dropped document is parsed again when it comes back, never answered
differently.

What changes: nothing outside the block. Inside it, every binding of the
parser in this package - ``deterministic_router``'s own included, so a module
first imported inside the block takes the remembered parser - is swapped, and
put back on the way out whatever happens, including the bindings of modules
first imported inside the block. A block inside another keeps the outer memo.
A block is for one thread.

Call relationships: batch drivers open it with the replay and derivation
blocks; saved-source test modules whose cases parse the same filings many
times open it for the module. No rule module opens it.
"""
import contextlib
import hashlib
import sys
import threading

from . import deterministic_router
from .normal_history_catalog import _need

PACKAGE = __name__.rpartition(".")[0]
# Documents held per block. One historical resolution reads its target filing,
# the prior one and any amendments; a test module of the cascade reads about
# twenty; a batch worker, one period's. The largest saved 10-K (JPMorgan's,
# 12.6 MB) parses into about 26 MB, so this bounds a block near a gigabyte.
# Past it the oldest document is parsed again.
MAX_DOCUMENTS = 32


def _memo(frozen, parses):
    held = {}

    def parse_accession_xbrl_source(*, raw_bytes):
        if type(raw_bytes) is not bytes:
            return frozen(raw_bytes=raw_bytes)
        key = (hashlib.sha256(raw_bytes).hexdigest(), len(raw_bytes))
        parsed = held.get(key)
        if parsed is None:
            parsed = frozen(raw_bytes=raw_bytes)
            parses.append(key)
            held[key] = parsed
            while len(held) > MAX_DOCUMENTS:
                held.pop(next(iter(held)))
        return parsed

    parse_accession_xbrl_source.parsed_once = True
    parse_accession_xbrl_source.thread = threading.get_ident()
    return parse_accession_xbrl_source


def _bindings(function):
    """(namespace, name) for every name a module of this package binds to ``function``."""
    found = []
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", None)
        if not isinstance(name, str) or not (name == PACKAGE or name.startswith(PACKAGE + ".")):
            continue
        namespace = vars(module)
        for attribute, value in list(namespace.items()):
            if value is function:
                found.append((namespace, attribute))
    return found


@contextlib.contextmanager
def xbrl_parsed_once(*, parses=None):
    """Answer the native XBRL parser once per document while the block is open.

    ``parses``, when given, is a list that receives the (SHA-256, length) of
    each document the frozen parser actually parsed, so a caller can report
    how many there were.
    """
    current = deterministic_router.parse_accession_xbrl_source
    if getattr(current, "parsed_once", False) is True:
        _need(current.thread == threading.get_ident(),
              "HISTORICAL_XBRL_PARSE_BLOCK_OPEN_IN_ANOTHER_THREAD")
        yield
        return
    _need(getattr(current, "__module__", None) == deterministic_router.__name__,
          "HISTORICAL_XBRL_PARSER_ALREADY_REPLACED")
    memo = _memo(current, parses if parses is not None else [])
    swapped = []
    try:
        for namespace, attribute in _bindings(current):
            namespace[attribute] = memo
            swapped.append((namespace, attribute))
        yield
    finally:
        for namespace, attribute in swapped:
            namespace[attribute] = current
        # A module first imported inside the block bound the remembered parser.
        for namespace, attribute in _bindings(memo):
            namespace[attribute] = current
