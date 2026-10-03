"""The nine proxies without inline XBRL under the base commit's readers and this tree's.

Usage: python3 measure.py <base commit> <out.json>

For each proxy: the cover each reader gives (and the identity record), every
Summary Compensation Table person row of the pinned fiscal year (chief
executive or not, the amounts read, whether they sum), and the C03 answer.
The base readers are the base commit's own source executed as modules of the
same package, so everything they import is this tree's; the eight earlier
proxies' covers come out the same either way, which the comparison checks
rather than assumes. Reads saved bytes only (the checkout or the committed
acquisition export). Zero calls.
"""
import json
import re
import subprocess
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO / "scripts"), str(REPO)]

from tests.vnext.test_historical_proxy_compensation import PERIODS, _target  # noqa: E402
from tests.vnext.test_historical_proxy_identity import (IMAGE_NAME, PROXIES, _filing,  # noqa: E402
                                                       _inventory, _records)
from tools.acceptance_readings import saved_bytes  # noqa: E402
from vnext import historical_proxy_compensation as table_now  # noqa: E402
from vnext import historical_proxy_identity as cover_now  # noqa: E402
from vnext.specs import compile_spec_file  # noqa: E402
from vnext.table_grid import build_table_grid  # noqa: E402

LABELS = {document: period[2] for document, period in PERIODS.items()}
LABELS[IMAGE_NAME[2]] = 2021
SPANS = {document: period[:2] for document, period in PERIODS.items()}
SPANS[IMAGE_NAME[2]] = ("2021-01-01", "2021-12-31")


def _base(name, commit):
    source = subprocess.run(["git", "show", commit + ":scripts/vnext/" + name + ".py"], cwd=REPO,
                            check=True, capture_output=True, text=True).stdout
    module = types.ModuleType("vnext._base_" + name)
    module.__package__, module.__file__ = "vnext", "<" + commit + ">/" + name
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _cover(reader, raw, row):
    try:
        cover = reader.proxy_cover(raw_bytes=raw, filing=_filing(row))
        identity = reader.cover_name_in_effect(cover=cover, inventory=_inventory(row[0]), filing=_filing(row))
        return {"cover": cover, "identity": identity}
    except reader.HistoricalProxyIdentityError as error:
        return {"refused": str(error)}


def _rows(reader, raw, label, now):
    asset = build_table_grid(html_bytes=raw, parent_raw_asset_ids=["sha256:" + "0" * 64], storage_uri="x.json")
    rows = []
    for table in asset["tables"]:
        header, people = reader._executives(table, label)
        if header is None or not all(re.search(r"\b" + word + r"\b", header, re.I)
                                     for word in ("total", "year", "salary")):
            continue
        for person in people:
            tokens = [text for _, text in person["amount_cells"]]
            amounts, marks = (reader.row_amounts_by_arithmetic(tokens) if now
                              else (reader.row_amounts(tokens), []))
            rows.append({"table": table["table_id"], "person": person["text"],
                         "chief_executive": reader.names_the_chief_executive(person["text"]),
                         "amounts": [text for _, text in amounts] if amounts else None, "marks": marks,
                         "sums": bool(amounts) and len(amounts) >= 3
                         and sum(value for value, _ in amounts[:-1]) == amounts[-1][0]})
    return rows


def _answer(reader, raw, row, spec):
    blob, reference = _records(row, raw)
    resolved = reader.resolve_proxy_compensation_table(
        raw_bytes=raw, raw_blob=blob, source_reference=reference, filing=_filing(row),
        inventory=_inventory(row[0]), company_id="company", cik=row[0], target=_target(*SPANS[row[2]]),
        fiscal_year=LABELS[row[2]], compiled_spec=spec)
    selection = resolved["selection"]
    return {"reason_code": selection["reason_code"], "value": resolved["result"]["value"],
            "candidates": [{"person": c["person_and_position"], "reason": c["reason"],
                            "value": c.get("value"), "marks": c.get("cells_read_as_footnote_marks", [])}
                           for c in selection["candidates"]]}


def main(commit, out):
    cover_base, table_base = _base("historical_proxy_identity", commit), _base("historical_proxy_compensation", commit)
    spec = compile_spec_file(path=REPO / table_now.SPEC_PATH, dependency_specs={})
    proxies = {}
    for row in list(PROXIES) + [IMAGE_NAME]:
        raw = saved_bytes(repo_root=REPO, relative=row[4])
        label = LABELS[row[2]]
        before = {"cover": _cover(cover_base, raw, row), "rows": _rows(table_base, raw, label, False),
                  "c03": _answer(table_base, raw, row, spec)}
        after = {"cover": _cover(cover_now, raw, row), "rows": _rows(table_now, raw, label, True),
                 "c03": _answer(table_now, raw, row, spec)}
        proxies[row[2]] = {"cik": row[0], "accession": row[1], "same": before == after,
                           "before": before, "after": after}
        print(row[2], "same" if before == after else "MOVED", after["c03"]["reason_code"], after["c03"]["value"],
              flush=True)
    moved = sorted(document for document, entry in proxies.items() if not entry["same"])
    Path(out).write_text(json.dumps({"record_type": "ISSUE_47_PROXY_IMAGE_NAME_MEASUREMENT", "base_commit": commit,
                                     "proxies": proxies, "moved": moved,
                                     "calls": {"provider": 0, "paid": 0, "sec": 0}},
                                    indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print("moved:", moved)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
