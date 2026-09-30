"""The zero-AI event route's walk over history blocks, held to the catalog's check.

``normal_zero_ai_results._event_sources`` reads every history block whose
declared range overlaps the fiscal window and holds it to the frozen date
check (``history_body_alignment``). That check refuses a fresh block for the
filings SEC dates on the undeclared day between two blocks - measured on the
acquired blocks: JPMorgan's 008, 009 and 024, which hold its FY2023-FY2025
windows - and passes a block that is missing filings. The catalog now blocks
every period whose window a stale block could reach, and no other company's
five-year window reaches a block the frozen check refuses, so today no period
this route runs reads one; the refusal is reached as soon as JPMorgan's block
007 is fetched again and its periods pass the catalog.

Here the frozen walk runs as it is, from its own code object, with one name
bound differently: the block check it calls is ``history_block_coherence``,
the catalog's, given the block's whole body (the frozen call hands over only
the rows of the forms the catalog keeps, which cannot show a missing filing)
and the block's last day from the index. The body is the one the walk has
just read through its reader; nothing is read twice.
``_registered_event_sources`` runs the same way, with its ``_event_sources``
bound to this walk. A name is bound only where the function's own code refers
to it, so a frozen rename stops the route by name instead of leaving the
frozen check in place. The frozen module is not changed: issue_28 generations
bind its bytes and the current route uses it.
"""
import types

from sec_urls import submissions_file_url

from . import normal_zero_ai_results as frozen
from .canonical import strict_json_loads
from .normal_governance_input import _history_index
from .normal_history_catalog import _need, block_last_days, history_block_coherence


def _view(function, **names):
    """``function``'s own code with ``names`` bound in place of its module's."""
    _need(set(names) <= set(function.__code__.co_names),
          "HISTORICAL_EVENT_WALK_NAME_NOT_REFERENCED:" + ",".join(
              sorted(set(names) - set(function.__code__.co_names))))
    namespace = dict(function.__globals__)
    namespace.update(names)
    view = types.FunctionType(function.__code__, namespace, function.__name__,
                              function.__defaults__, function.__closure__)
    view.__kwdefaults__ = function.__kwdefaults__
    return view


class _Remembering:
    """The walk's reader, keeping the bytes of each history block it reads."""

    def __init__(self, reader):
        self.reader, self.blocks = reader, {}

    def read(self, url, **keywords):
        item = self.reader.read(url, **keywords)
        if keywords.get("role") == "sec_submissions_history":
            self.blocks[url] = item["raw_bytes"]
        return item


def event_sources(*, repo_root, reader, prepared, inventory):
    """``_event_sources``, with every block held to ``history_block_coherence``."""
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    last_days = block_last_days(payload=payload,
                                shards=_history_index(payload, prepared["entity"]))
    remembering = _Remembering(reader)

    def coherence(*, shard, rows):
        raw = remembering.blocks[submissions_file_url(file_name=shard["name"])]
        return history_block_coherence(shard=shard, body=strict_json_loads(text=raw.decode("utf-8")),
                                       rows=rows, last_day=last_days[shard["name"]])
    walk = _view(frozen._event_sources, history_body_alignment=coherence)
    return walk(repo_root=repo_root, reader=remembering, prepared=prepared, inventory=inventory)


def registered_event_sources(*, repo_root, reader, prepared, inventory, period):
    """``_registered_event_sources``, walking each registered CIK with ``event_sources``."""
    walk = _view(frozen._registered_event_sources, _event_sources=event_sources)
    return walk(repo_root=repo_root, reader=reader, prepared=prepared, inventory=inventory,
                period=period)
