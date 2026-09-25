"""The submissions document that lists a pinned filing.

A pinned route proves its target filing against SEC's index before it reads a
fact from it: the frozen ``_exact_filing_source_set`` looks the accession up
among the rows of the document it is handed and builds the source set from
that document. Every pinned route handed it the registrant's main submissions
document. SEC lists a registrant's newest filings in that document's ``recent``
block and the rest in history blocks, and re-partitions them over time, so an
older period's 10-K row can sit in a history block, where the lookup stops with
"Filing accession is absent from submissions". Measured on this repository's
saved indexes, six of the frame's fifty target periods are like that
(JPMorgan FY2021-FY2024, Salesforce FY2022-FY2023). That is a consumer
limitation, not a missing source: fetching their originals does not remove it.

The frozen prior-year walk (``normal_companyfacts_results._prior_filing``)
already answers this question for the prior filing - it reads the history
blocks and returns the document that lists the row. This answers it for the
target filing, from the blocks the pinned selection loaded, which the pinned
input carries with their request proofs. Where ``recent`` lists the row the
main document is returned - the same object the route already read - so no
period whose row is in ``recent`` changes by a byte.

Each block is read through the route's own reader, so it is a request-proved
source of the Run like the main document, and it is held to the same checks
the prior-year walk applies: declared by the index, same registrant, and a
body inside its declared range. Exactly one loaded block may list the row.
"""
from sec_urls import submissions_file_url

from .canonical import strict_json_loads
from .normal_governance_input import _filings, _history_index, history_body_alignment

RULE = "THE_LOADED_BLOCK_THAT_LISTS_THE_FILING_ELSE_THE_MAIN_DOCUMENT"


class HistoricalFilingInventoryError(ValueError):
    """A metadata limitation, never a disclosure conclusion."""

    def __init__(self, reason, category="SOURCE_COVERAGE_CONFLICT"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_COVERAGE_CONFLICT"):
    if not condition:
        raise HistoricalFilingInventoryError(reason, category)


def _lists(rows, accession):
    return any(row["accessionNumber"] == accession for row in rows)


def filing_inventory(*, reader, inventory, period_selection, cik, accession):
    """The main document if its ``recent`` block lists ``accession``, else the loaded block that does.

    ``inventory`` is the main document as the route read it. The blocks asked
    are the ones the pinned selection loaded, in its order; a row the selection
    never loaded cannot be the one it selected.
    """
    payload = strict_json_loads(text=inventory["raw_bytes"].decode("utf-8"))
    name = inventory["source_reference"]["document_name"]
    if _lists(_filings(payload, inventory_name=name), accession):
        return inventory
    loaded = period_selection["loaded_inventories"]
    _need(bool(loaded) and loaded[0] == name, "HISTORICAL_FILING_INVENTORY_ORDER_CHANGED",
          "IMPLEMENTATION_GAP")
    declared = {row["name"]: row for row in _history_index(payload, cik)}
    holding = []
    for block_name in loaded[1:]:
        _need(block_name in declared, "HISTORICAL_FILING_BLOCK_NOT_DECLARED:" + block_name)
        item = reader.read(submissions_file_url(file_name=block_name),
                           role="sec_submissions_history", media_type="application/json")
        body = strict_json_loads(text=item["raw_bytes"].decode("utf-8"))
        _need("cik" not in body or (str(body["cik"]).isdigit() and int(body["cik"]) == int(cik)),
              "HISTORICAL_FILING_BLOCK_ENTITY_CONFLICT", "SOURCE_INTEGRITY_ERROR")
        rows = _filings(body, inventory_name=block_name)
        _need(history_body_alignment(shard=declared[block_name], rows=rows) is None,
              "HISTORICAL_FILING_BLOCK_SNAPSHOT_CONFLICT:" + block_name)
        if _lists(rows, accession):
            holding.append(item)
    _need(bool(holding), "HISTORICAL_FILING_ROW_IN_NO_LOADED_BLOCK:" + accession)
    _need(len(holding) == 1, "HISTORICAL_FILING_ROW_IN_MORE_THAN_ONE_BLOCK:" + accession)
    return holding[0]
