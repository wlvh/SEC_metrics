"""Write #28's C02 development input for historical positions, task unchanged.

#28's C02 model method (docs/evidence/issue28_continuous/c02-model-input-pilot-20261003/)
gives a development model every visible block of one governance filing, labelled
[B<n>] in document order, with its prompt.txt, and keeps the model's facts and
unresolved items as proposals that a program only checks mechanically. #47's
body (section 3.1) asks whether the same method is cheaper than more selector
rules on other years and layouts. This writes that input for a historical
position. The document is the historical route's own
(tools/read_c02_composition.route_selection), so its block numbers are the ones
#47's two-direction readings judged. Only the prompt's opening paragraph is
adapted to the filing (issuer, form, filing date, accession, fiscal year), as
#28 adapted it for Paramount; from "Extract the registrant" on the task is #28's
prompt byte for byte. The request body and its measurement use #28's settings
(deepseek-flash, temperature 0, 4096 output tokens), but nothing is sent: these
inputs are read by development contexts only, and C02 has no call allowance.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-model-method/prepare_inputs.py \
        --source-root <root holding the saved proxies> --out <dir> \
        --position <company_id>:<report_end> [--position ...]

Each position gets <dir>/<company_id>-<report_end>/ with source.txt, prompt.txt,
input.txt (the one file a development context reads), locators.json,
request-body.json, context-measurement.json and metadata.json. Zero calls.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))
PILOT = REPO / "docs/evidence/issue28_continuous/c02-model-input-pilot-20261003"
TASK_START = "Extract the registrant"


def header(*, issuer, form, filing_date, accession, fiscal_year, period_end):
    """#28's opening paragraph with this filing's identity, as #28 wrote it for Paramount."""
    return (f"You receive the complete visible source blocks of one {issuer}\n"
            f"{form} filed on {filing_date}, accession {accession}.\n"
            f"It is associated with the {fiscal_year} annual reporting container, not a\n"
            f"measurement of the board at {period_end}. Source blocks have stable\n"
            "[B<number>] labels in document order.\n\n")


def render(prompt, source_text):
    return ("SYSTEM PROMPT\n=============\n" + prompt + "\n\nUSER MESSAGE\n============\n"
            + source_text)


def prepare(*, source_root, company_id, report_end, out):
    from read_c02_composition import route_selection
    from vnext.continuous_request_context import measure_request
    document, chosen, candidate, period_start = route_selection(
        repo_root=REPO, company_id=company_id, report_end=report_end,
        source_root=source_root, with_period=True)
    if document["source_state"] != "COMPLETE_LOCAL_DOCUMENT":
        raise SystemExit("C02_DEV_INPUT_DOCUMENT_INCOMPLETE:" + company_id + ":" + report_end)
    lines, locators = [], []
    for index, block in enumerate(document["blocks"]):
        if block["block_index"] != index:
            raise SystemExit("C02_DEV_INPUT_BLOCK_ORDER")
        lines.append("[B{}]\n{}\n".format(index, block["text"]))
        locators.append({key: block[key] for key in ("block_index", "raw_start_byte",
                                                    "raw_end_byte", "raw_span_sha256")})
    source_text = "\n".join(lines)
    template = (PILOT / "prompt.txt").read_text(encoding="utf-8")
    filing = document["source_filing"]
    # #28's header names the fiscal year. For a calendar year that is the year
    # the period ends; another year end needs the issuer's own label, which
    # this sample does not include, so it is refused rather than guessed.
    if not (period_start.endswith("-01-01") and report_end.endswith("-12-31")
            and period_start[:4] == report_end[:4]):
        raise SystemExit("C02_DEV_INPUT_FISCAL_LABEL_NOT_CALENDAR:" + company_id + ":" + report_end)
    fiscal_year = "FY" + report_end[:4]
    prompt = header(issuer=document["registrant_names"][0], form=filing["form"],
                    filing_date=filing["filingDate"], accession=filing["accessionNumber"],
                    fiscal_year=fiscal_year, period_end=report_end) + template[template.index(TASK_START):]
    request = {"model": "deepseek-flash", "messages": [
        {"role": "system", "content": prompt}, {"role": "user", "content": source_text}],
        "response_format": {"type": "json_object"}, "temperature": 0,
        "max_tokens": 4096, "stream": False, "thinking": {"type": "disabled"}}
    wire = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    measurement = measure_request(wire, require_reference=True)
    target = Path(out) / (company_id + "-" + report_end)
    target.mkdir(parents=True, exist_ok=False)
    (target / "source.txt").write_text(source_text, encoding="utf-8")
    (target / "prompt.txt").write_text(prompt, encoding="utf-8")
    (target / "input.txt").write_text(render(prompt, source_text), encoding="utf-8")
    (target / "locators.json").write_text(json.dumps(locators, indent=1) + "\n")
    (target / "request-body.json").write_bytes(wire)
    (target / "context-measurement.json").write_text(json.dumps(measurement, indent=1) + "\n")
    metadata = {"record_type": "ISSUE_47_C02_DEV_INPUT", "company_id": company_id,
                "report_end": report_end, "period_start": period_start, "fiscal_year": fiscal_year,
                "document_id": document["text_document_id"],
                "source_reference_id": document["source_reference_id"],
                "raw_asset_id": document["raw_asset_id"], "filing": filing,
                "issuer_named": document["registrant_names"][0],
                "blocks": len(locators), "visible_characters": sum(len(b["text"]) for b in document["blocks"]),
                "input_sha256": hashlib.sha256(render(prompt, source_text).encode("utf-8")).hexdigest(),
                "task_sha256": hashlib.sha256(template[template.index(TASK_START):].encode("utf-8")).hexdigest(),
                "pilot_prompt_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
                "route_selection": chosen, "route_candidate_hash": candidate["candidate_hash"],
                "fits": measurement["fits"], "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (target / "metadata.json").write_text(json.dumps(metadata, indent=1) + "\n")
    print(company_id, report_end, len(locators), "blocks", measurement.get("input_tokens"),
          "input tokens", "fits" if measurement["fits"] else "DOES_NOT_FIT", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--position", action="append", required=True)
    arguments = parser.parse_args()
    for position in arguments.position:
        company_id, report_end = position.rsplit(":", 1)
        prepare(source_root=arguments.source_root, company_id=company_id,
                report_end=report_end, out=arguments.out)


if __name__ == "__main__":
    main()
