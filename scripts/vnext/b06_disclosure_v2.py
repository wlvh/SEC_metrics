"""Additive B06 content checks; historical v1 records keep their old verifier.

The two supported table grammars still use v1's relationship and calculation
checks. This successor also compares consumed XML/inline numbers, explains the
two observed alternate debt measurements, and checks a bounded class of current
borrowing assertions in the complete debt/lease notes. It is not a general
natural-language reader and grants no source, execution or publication credit.
"""
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
import re

from . import b06_disclosure as prior
from .canonical import content_hash, decimal_text
from .r5_b06_scope import precision_choice
from .r5_b06_structured import need

RESOLVER = "debt_equity_new_source_v2"
SPEC_PATH = "catalog/r5/B06_new_source_v2.md"
propose = prior.propose


class _NumericAttributes(HTMLParser):
    """Read source attributes alongside, not instead of, the native parser."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.facts = {}
        self.units = {}
        self.ordinal = 0
        self.unit = None
        self.measure = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        local = tag.split(":")[-1]
        if "contextref" in attrs:
            self.ordinal += 1
            self.facts[self.ordinal] = attrs
        if local == "unit":
            need(self.unit is None, "B06_V2_NESTED_UNIT")
            self.unit = attrs["id"]
            need(self.unit not in self.units, "B06_V2_DUPLICATE_UNIT")
            self.units[self.unit] = []
        elif local == "measure" and self.unit is not None:
            self.measure = []

    def handle_data(self, data):
        if self.measure is not None:
            self.measure.append(data)

    def handle_endtag(self, tag):
        local = tag.split(":")[-1]
        if local == "measure" and self.measure is not None:
            self.units[self.unit].append("".join(self.measure).strip())
            self.measure = None
        elif local == "unit":
            self.unit = None


def _numeric_source(raw):
    parsed = prior.parse_accession_xbrl_source(raw_bytes=raw)
    attrs = _NumericAttributes()
    attrs.feed(raw.decode("utf-8"))
    attrs.close()
    need(attrs.unit is None and attrs.measure is None, "B06_V2_UNIT_TRUNCATED")
    return parsed, attrs


def _reports(parsed, attrs, concept, target):
    result = []
    for fact in parsed.facts:
        context = parsed.contexts[fact["context_ref"]]
        if (fact["qualified_name"].casefold() != concept.casefold()
                or context["period_start"] != context["period_end"]
                or context["period_end"] != target["period_end"]
                or context["dimensions"] or context["typed_dimension_count"]):
            continue
        need(str(int(context["entity_identifier"])) == target["entity"],
             "B06_V2_MONETARY_SUBJECT_CONFLICT:" + concept)
        need(attrs.units.get(fact["unit_ref"]) == ["iso4217:USD"],
             "B06_V2_MONETARY_UNIT_CONFLICT:" + concept)
        metadata = attrs.facts[fact["ordinal"]]
        need(metadata["contextref"] == fact["context_ref"],
             "B06_V2_NATIVE_ATTRIBUTE_ORDINAL_CONFLICT")
        result.append({
            "value": prior._numeric_xbrl_value(text=fact["text"],
                scale=fact["scale"], sign=fact["sign"]),
            "decimals": metadata.get("decimals"),
            "ordinal": fact["ordinal"], "context_ref": fact["context_ref"],
        })
    return result


def _numeric_agreement(raw, primary, target, proof):
    xml, xattrs = _numeric_source(raw)
    inline, iattrs = _numeric_source(primary)
    required = {entry["concept"] for entry in proof["precision"]} | {
        "us-gaap:FinanceLeaseLiabilityCurrent",
        "us-gaap:FinanceLeaseLiabilityNoncurrent",
        "us-gaap:FinanceLeaseLiabilityPaymentsDue",
        "us-gaap:FinanceLeaseLiabilityUndiscountedExcessAmount",
    }
    alternate = {"us-gaap:LongTermDebt", "us-gaap:DebtInstrumentCarryingAmount"}
    agreement = []
    for concept in sorted(required | alternate):
        left = _reports(xml, xattrs, concept, target)
        right = _reports(inline, iattrs, concept, target)
        if not left and not right and concept not in required:
            continue
        need(left and right, "B06_V2_PRIMARY_XML_FACT_MISSING:" + concept)
        # Reuse the existing precision rule: compatible coarse reports remain
        # legal, while equal-precision disagreements, scale and sign drift fail.
        try:
            chosen = precision_choice(left + right)
        except ValueError as error:
            raise ValueError("B06_V2_PRIMARY_XML_AMOUNT_CONFLICT:" + concept
                             + ":" + str(error)) from error
        agreement.append({"concept": concept, "value": chosen["value"],
            "xml_reports": left, "primary_reports": right})
    return agreement


def _date_text(end):
    day = date.fromisoformat(end)
    return day.strftime("%B") + " " + str(day.day) + ", " + str(day.year)


def _principal_column(scope, target):
    table = scope["debt_table"]
    title = "outstanding principal as of " + _date_text(target["period_end"])
    headings = [c for row in table["rows"] for c in prior.origins(row)
                if c["text"].casefold() == title.casefold()]
    need(len(headings) == 1, "B06_V2_PRINCIPAL_COLUMN_UNSUPPORTED")
    heading = headings[0]
    parts = []
    for row in table["rows"][heading["row_index"] + 1:]:
        cells = [c for c in prior.origins(row) if heading["column_index"]
                 <= c["column_index"] < heading["column_index"] + heading["colspan"]]
        if not cells:
            continue
        value = prior.amount(row, heading["column_index"], heading["colspan"])
        label = prior.label(row)
        if label.casefold().startswith("total"):
            need(parts and sum(Decimal(p["value"]) for p in parts) == value,
                 "B06_V2_PRINCIPAL_MEMBERSHIP_SUM_CONFLICT")
            return {"basis": "OUTSTANDING_PRINCIPAL_COLUMN", "header": heading,
                    "members": parts, "total": decimal_text(value=value)}
        need(re.search(r"\b(?:notes|debentures|loan|credit agreement)\b", label, re.I),
             "B06_V2_PRINCIPAL_MEMBERSHIP_UNSUPPORTED")
        parts.append({"row": row["row_index"], "label": label,
                      "value": decimal_text(value=value)})
    raise ValueError("B06_V2_PRINCIPAL_TOTAL_MISSING")


def _maturity_principal(scope, target):
    note = prior._note(scope["parsed"],
        "us-gaap:ScheduleOfMaturitiesOfLongTermDebtTableTextBlock", target)
    tables = prior.tables(note["text"])
    need(len(tables) == 1 and "in millions" in prior.text(note["text"]).casefold(),
         "B06_V2_MATURITY_MEASUREMENT_UNSUPPORTED")
    text = prior.text(scope["debt"]["text"])
    need(re.search(r"As of " + re.escape(_date_text(target["period_end"]))
        + r", aggregate annual principal maturities of debt and finance leases", text, re.I),
        "B06_V2_MATURITY_PRINCIPAL_BASIS_UNPROVEN")
    parts = []
    for row in tables[0]["rows"]:
        cells = prior.origins(row)
        if len(cells) < 2:
            continue
        label = cells[0]["text"]
        start = cells[0]["column_index"] + cells[0]["colspan"]
        end = max(c["column_index"] + c["colspan"] for c in cells)
        value = prior.amount(row, start, end - start)
        if label.casefold() == "total":
            year = date.fromisoformat(target["period_end"]).year
            need([p["label"] for p in parts] == [str(year + n) for n in range(1, 6)]
                 + ["Thereafter"], "B06_V2_MATURITY_PERIODS_UNSUPPORTED")
            need(sum(Decimal(p["value"]) for p in parts) == value,
                 "B06_V2_MATURITY_TOTAL_CONFLICT")
            return {"basis": "FUTURE_PRINCIPAL_MATURITIES", "concept": note["qualified_name"],
                    "members": parts, "total": decimal_text(value=value)}
        parts.append({"row": row["row_index"], "label": label,
                      "value": decimal_text(value=value)})
    raise ValueError("B06_V2_MATURITY_TOTAL_MISSING")


def _alternate_measurements(scope, target, proof, agreement):
    consumed = {entry["concept"].casefold() for entry in proof["precision"]}
    explanations = []
    for entry in agreement:
        name = entry["concept"].casefold()
        if name in consumed:
            continue
        if name == "us-gaap:longtermdebt" and proof["model_id"] == "INCLUSIVE_RECONCILED_COSTS":
            explanation = _maturity_principal(scope, target)
        elif (name == "us-gaap:debtinstrumentcarryingamount"
              and proof["model_id"] == "BORROWING_PLUS_SEPARATE_FINANCE_LEASE"):
            explanation = _principal_column(scope, target)
        elif name in {"us-gaap:longtermdebt", "us-gaap:debtinstrumentcarryingamount"}:
            raise ValueError("B06_V2_ALTERNATE_MEASUREMENT_UNSUPPORTED:" + entry["concept"])
        else:
            # Additional explicit lease facts are already reconciled by v1.
            continue
        need(entry["value"] == explanation["total"],
             "B06_V2_ALTERNATE_MEASUREMENT_CONFLICT:" + entry["concept"])
        explanations.append({"concept": entry["concept"], "value": entry["value"],
            "disposition": "EXPLAINED_DIFFERENT_REPORTED_MEASUREMENT", **explanation})
    return explanations


class _Narrative(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "table":
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


_MONEY = re.compile(r"(?:\$\s*([\d,]+(?:\.\d+)?)(?:\s*(thousand|million|billion))?"
                    r"|([\d,]+(?:\.\d+)?)\s*(thousand|million|billion))\b", re.I)
_BORROWING = re.compile(r"\b(?:borrowings?|debt|loans?|notes|debentures|finance leases?"
                        r"|financing|credit facilit(?:y|ies)|credit agreements?|commercial paper|promissory)\b", re.I)
_BALANCE = re.compile(r"\b(?:outstanding|carrying (?:amount|value)|balance|recognized|recognised)\b"
                      r"|\b(?:borrowings?|debt|loans?)\s+(?:was|were|is|are|totaled|totalled|amounted to)\b", re.I)
_MONETARY_CUE = re.compile(r"\$|\b(?:USD|dollars?|thousand|million|billion)\b", re.I)


def _money_values(sentence):
    scales = {"": 1, "thousand": 1000, "million": 1000000, "billion": 1000000000}
    return [Decimal((dollars or unprefixed).replace(",", ""))
            * scales[(dollar_unit or plain_unit).casefold()]
            for dollars, dollar_unit, unprefixed, plain_unit in _MONEY.findall(sentence)]


def _narrative_inventory(scope, target, proof, measurements):
    """Check current monetary balance assertions, not every borrowing keyword.

    Supported explanations are explicit zero, a named reconciled table member,
    a named carrying total, estimated market fair value, and the documented
    off-balance-sheet letter-of-credit amount. Unknown positive assertions fail.
    Historical issuance, rate definitions, undrawn facilities and future
    commitments are not present recognized balances and are recorded separately.
    """
    inventory = []
    members = {label.casefold(): Decimal(value)
               for label, value in proof["relations"][1]["members"]}
    for measurement in measurements:
        members.update({p["label"].casefold(): Decimal(p["value"])
                        for p in measurement["members"]
                        if measurement["basis"] == "OUTSTANDING_PRINCIPAL_COLUMN"})
    totals = {item["label"].casefold(): Decimal(item["value"])
              for item in proof["disclosure_inventory"]
              if item["origin"] == "debt_composition"
              and item["disposition"] == "RECONCILED_TOTAL" and item["label"]}
    for note in [scope["debt"], scope["leases"]]:
        parser = _Narrative()
        parser.feed(note["text"])
        parser.close()
        text = " ".join(" ".join(parser.parts).split())
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            if not _BORROWING.search(sentence):
                continue
            row = {"concept": note["qualified_name"], "sentence": sentence}
            if not _MONEY.search(sentence) and re.search(r"\bno (?:amounts |outstanding )?(?:borrowings|amounts)\b", sentence, re.I):
                need(re.search(r"\bunder\b", sentence, re.I),
                     "B06_V2_NARRATIVE_ZERO_SCOPE_UNSUPPORTED:" + sentence)
                need(not any(label in sentence.casefold() and value != 0 for label, value in members.items()),
                     "B06_V2_NARRATIVE_ZERO_BALANCE_CONFLICT:" + sentence)
                row["disposition"] = "EXPLICIT_NO_BORROWING_BALANCE"
            elif _BALANCE.search(sentence) and _MONETARY_CUE.search(sentence) and not _MONEY.search(sentence):
                raise ValueError("B06_V2_NARRATIVE_AMOUNT_UNSUPPORTED:" + sentence)
            elif not _MONEY.search(sentence) or not _BALANCE.search(sentence):
                row["disposition"] = "NO_MONETARY_BALANCE_ASSERTION"
            elif _date_text(target["period_end"]).casefold() not in sentence.casefold():
                # A monetary balance cannot silently inherit the current date.
                # Only an explicit other-year reference is a historical claim.
                years = set(re.findall(r"\b20\d{2}\b", sentence))
                if years and str(date.fromisoformat(target["period_end"]).year) not in years:
                    row["disposition"] = "EXPLICIT_OTHER_PERIOD"
                else:
                    raise ValueError("B06_V2_NARRATIVE_PERIOD_AMBIGUOUS:" + sentence)
            elif re.search(r"\b(?:excluded from|not included in|not part of|outside|separate from)\b", sentence, re.I):
                raise ValueError("B06_V2_UNRESOLVED_ADDITIONAL_BORROWING:" + sentence)
            elif (re.search(r"\btotal estimated fair value\b", sentence, re.I)
                  and not re.search(r"\b(?:recognized|recognised|recorded|carrying amount|carrying value)\b", sentence, re.I)):
                row["disposition"] = "DISCLOSED_ESTIMATED_FAIR_VALUE_NOT_CARRYING"
            else:
                amounts = _money_values(sentence)
                matches = [(label, value) for label, value in {**members, **totals}.items()
                           if label in sentence.casefold() and value in amounts]
                group = re.search(r"associated with the ([A-Za-z][A-Za-z0-9 &'’-]{0,100}?) Credit Agreements\b",
                                  sentence, re.I)
                grouped = []
                if group:
                    prefix = group[1].casefold() + " "
                    grouped = [(label, value) for label, value in members.items()
                               if label.startswith(prefix) and re.search(r"\bcredit agreement(?: \(\d+\))?$", label)]
                if matches and len(amounts) == 1:
                    row["disposition"] = "RECONCILED_NAMED_TABLE_AMOUNT"
                    row["matched_labels"] = [label for label, _ in matches]
                elif len(grouped) >= 2 and len(amounts) == 1 and sum(value for _, value in grouped) == amounts[0]:
                    row["disposition"] = "RECONCILED_NAMED_AGREEMENT_GROUP"
                    row["group_name"] = group[1]
                    row["members"] = [{"label": label, "value": decimal_text(value=value)}
                                      for label, value in grouped]
                else:
                    reason = ("B06_V2_UNRESOLVED_ADDITIONAL_BORROWING:" if re.search(r"\badditional\b", sentence, re.I)
                              else "B06_V2_NARRATIVE_BALANCE_UNSUPPORTED:")
                    raise ValueError(reason + sentence)
            inventory.append(row)
    return inventory


def verify(*, raw, primary, source, spec, target, filed, data_root, proposal):
    need(spec["compiled"]["quality_rule"].get("resolver") == RESOLVER,
         "B06_V2_SPEC_REQUIRED")
    proof = prior.verify(raw=raw, primary=primary, source=source, spec=spec,
                         target=target, filed=filed, data_root=data_root, proposal=proposal)
    agreement = _numeric_agreement(raw, primary, target, proof)
    scope = prior.discover_scope(raw=raw, primary=primary, target=target)
    measurements = _alternate_measurements(scope, target, proof, agreement)
    narrative = _narrative_inventory(scope, target, proof, measurements)
    checks = {"version": RESOLVER, "primary_xml_numeric_agreement": agreement,
              "alternate_measurements": measurements, "narrative_inventory": narrative,
              "narrative_scope": "CURRENT_MONETARY_BALANCE_ASSERTIONS_IN_REQUIRED_DEBT_AND_LEASE_NOTES"}
    checks["checks_id"] = content_hash(value=checks)
    return {**proof, "successor_content_checks": checks}
