"""Fiscal-year labels on #47's historical paths: two definition forms the frozen scan leaves unparsed.

Purpose: an annual input's fiscal-year label comes from the issuer's own
definition in the filing (``ordinary_fiscal_year_labels_v1``). The frozen scan
in ``fiscal_year_labels`` recognizes three sentence forms and, when a sentence
that looks like a definition mentions the period's end year but is not one of
them, stops the period as ``EXPLICIT_DEFINITION_UNRESOLVED`` - the right answer
for a definition it cannot read. The five-year frame reached two forms older
annual reports use for the same statement:

- the ordered form with the week count appended to the same sentence: "Fiscal
  years <labels> ended on <dates>, respectively, and included 52 weeks." The
  frozen pattern requires the sentence to end at "respectively.";
- the reference form whose alias is the registrant's name without its legal
  form: "references to "Example Stores" or the "Company" are references to
  Example Stores and its subsidiaries" in a filing whose DEI registrant name is
  "Example Stores, Inc.". The frozen alias proof requires the full name.

The filings where they were met are named in
docs/evidence/issue47_history/fiscal-label-forms/.

Neither form says anything the frozen forms do not: the first maps the same
labels to the same end dates and adds how many weeks they had; the second
names the same registrant. Both stopped a period whose label every source
agrees on (DEI, Company Facts and every definition that did parse), which is a
reader that cannot read the filing, not a filing that does not say.

What changes: only a period the frozen inspection leaves
``EXPLICIT_DEFINITION_UNRESOLVED`` is read again, by the frozen definition scan
itself - its own code object - with those two recognizers widened to accept the
forms above as well as everything they accepted. The frozen definitions must
come back unchanged and the frozen unparsed leads must shrink, or the period is
refused by name. The label is then decided by the frozen rule over what was
read. Every other period keeps the frozen inspection, byte for byte, so its
input identity does not move. A sentence neither form covers still stops the
period, as does a widened reading that yields a second label.

Call relationships: ``historical_annual_input.prepare_historical_annual_input``
calls ``inspect_prepared_fiscal_year_labels`` here in place of the DEI view's.
The frozen module is not changed; Issue #28's generations record its bytes.
"""
import json
import re
import types

from . import fiscal_year_labels as _frozen_labels
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .historical_dei import inspect_prepared_fiscal_year_labels as _frozen_inspection
from .sources import resolve_repository_file

FORMS_RULE = "HISTORICAL_FISCAL_DEFINITION_FORMS_V1"
UNRESOLVED = "EXPLICIT_DEFINITION_UNRESOLVED"
_FROZEN_END = r"respectively\."
# The week count the same sentence states, and nothing else, may follow.
_WEEKS_END = r"respectively(?:,\s+and\s+included\s+5[23]\s+weeks)?\."
_LEGAL_FORMS = frozenset({"inc", "incorporated", "corp", "corporation", "co", "company",
                          "ltd", "limited", "llc", "plc", "lp"})


class HistoricalFiscalLabelError(ValueError):
    """A widened reading would change what the frozen scan already read."""


def _need(condition, reason):
    if not condition:
        raise HistoricalFiscalLabelError(reason)


def _ordered_pattern():
    frozen = _frozen_labels._MULTI
    _need(frozen.pattern.count(_FROZEN_END) == 1 and frozen.pattern.endswith(_FROZEN_END),
          "HISTORICAL_FISCAL_FROZEN_ORDERED_FORM_CHANGED")
    return re.compile(frozen.pattern[:-len(_FROZEN_END)] + _WEEKS_END, frozen.flags)


def _words(value):
    # The frozen alias proof's own normalization, repeated so the name forms compare alike.
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", value.casefold().replace("'", "").replace("’", "")).split())


def _name_forms(names):
    """Each registrant name, and the same name without trailing legal-form words."""
    forms = set()
    for name in names:
        tokens = _words(name).split()
        forms.add(" ".join(tokens))
        while len(tokens) > 1 and tokens[-1] in _LEGAL_FORMS:
            tokens.pop()
            forms.add(" ".join(tokens))
    return sorted(form for form in forms if form)


def _alias_prefix(prefix, names):
    """The frozen proof, or the same sentence naming the registrant without its legal form."""
    if _frozen_labels._issuer_alias_prefix(prefix, names):
        return True
    text = _words(prefix)
    return any(text.startswith("unless the context requires otherwise references to " + form
                               + " or the company are references to ")
               for form in _name_forms(names))


def _widened_definitions():
    """The frozen scan's own code, with the two recognizers widened and nothing else."""
    scan = _frozen_labels._definitions
    _need(not scan.__closure__ and not scan.__defaults__ and not scan.__kwdefaults__,
          "HISTORICAL_FISCAL_FROZEN_SCAN_NOT_A_PLAIN_FUNCTION")
    namespace = dict(scan.__globals__)
    namespace.update(_MULTI=_ordered_pattern(), _issuer_alias_prefix=_alias_prefix)
    return types.FunctionType(scan.__code__, namespace, scan.__name__)


def _status(inspected, definitions, unparsed):
    """The frozen rule over what was read (fiscal_year_labels.inspect_fiscal_year_labels)."""
    end_year = inspected["actual_period"]["period_end"][:4]
    labels = sorted({year for item in definitions for year in item["current_period_labels"]})
    machine = {inspected["dei_fiscal_year"], *inspected["companyfacts_fiscal_year_values"]}
    invalid = inspected["invalid_companyfacts_fy_rows"]
    current = [lead for lead in unparsed
               if re.search(r"(?:" + _frozen_labels._MONTH + r")\s+[0-9]{1,2},\s*" + end_year,
                            lead["text"], re.I)]
    if len(labels) > 1 or current:
        return labels, UNRESOLVED, None
    if len(labels) == 1:
        conflict = machine != {labels[0]} or invalid
        return labels, "SOURCE_LABEL_CONFLICT" if conflict else "SOURCE_LABELS_CONSISTENT", labels[0]
    conflict = len(machine) > 1 or invalid
    return labels, "SOURCE_LABEL_CONFLICT" if conflict else "METADATA_LABEL_ONLY", None


def widen_inspection(*, inspected, primary_bytes):
    """Read an unresolved period's definitions again with the two widened recognizers.

    Returns ``inspected`` itself unless its status is unresolved. Otherwise the
    frozen definitions must all be read again unchanged, what was read must add
    at least one definition, and every lead left unparsed must be one the
    frozen scan also left; then the frozen rule decides over the result.
    """
    if inspected["status"] != UNRESOLVED:
        return inspected
    _need(sha256_bytes(content=primary_bytes) == inspected["primary_sha256"],
          "HISTORICAL_FISCAL_PRIMARY_BYTES_ARE_NOT_THE_INSPECTED_ONES")
    _, frozen_status, frozen_label = _status(inspected, inspected["source_definitions"],
                                             inspected["unsupported_definition_leads"])
    _need((frozen_status, frozen_label) == (inspected["status"],
                                            inspected["source_defined_fiscal_year"]),
          "HISTORICAL_FISCAL_FROZEN_RULE_NOT_REPRODUCED")
    definitions, unparsed = _widened_definitions()(
        primary_bytes, inspected["actual_period"]["period_end"], inspected["registrant_names"])
    definitions = strict_json_loads(text=json.dumps(definitions, ensure_ascii=False))
    unparsed = strict_json_loads(text=json.dumps(unparsed, ensure_ascii=False))
    frozen_definitions = inspected["source_definitions"]
    _need(all(item in definitions for item in frozen_definitions),
          "HISTORICAL_FISCAL_WIDENED_SCAN_CHANGED_A_FROZEN_DEFINITION")
    _need(all(lead in inspected["unsupported_definition_leads"] for lead in unparsed),
          "HISTORICAL_FISCAL_WIDENED_SCAN_LEFT_A_NEW_LEAD")
    added = [item for item in definitions if item not in frozen_definitions]
    if not added:
        return inspected
    labels, status, proposed = _status(inspected, definitions, unparsed)
    body = {key: value for key, value in inspected.items() if key != "inspection_id"}
    body.update(source_definitions=definitions, unsupported_definition_leads=unparsed,
                current_definition_labels=labels, status=status,
                source_defined_fiscal_year=proposed, new_rule_label_proposal=proposed,
                definition_forms_rule=FORMS_RULE,
                definitions_read_by_the_widened_forms=added,
                frozen_inspection={"inspection_id": inspected["inspection_id"],
                                   "status": inspected["status"],
                                   "unsupported_definition_leads":
                                       inspected["unsupported_definition_leads"]})
    canonical_json_bytes(value=body)
    return {**body, "inspection_id": content_hash(value=body)}


def inspect_prepared_fiscal_year_labels(*, repo_root, prepared):
    """The DEI view's inspection of a pinned input, widened where the frozen scan stopped."""
    report = _frozen_inspection(repo_root=repo_root, prepared=prepared)
    inspected = report["inspection"]
    if inspected["status"] != UNRESOLVED:
        return report
    primary = resolve_repository_file(
        repo_root=repo_root,
        repo_relative_path=prepared["table_input"]["source_repo_relative_path"]).read_bytes()
    return {**report, "inspection": widen_inspection(inspected=inspected, primary_bytes=primary)}
