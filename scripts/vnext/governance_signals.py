"""Source-bound C03 signals using the native XBRL and result primitives.

The adapter reads exact source bytes; no legacy metric/inventory value enters
selection. Current filing discovery and Run/Requirement binding are owned by
the caller. Multiple people/values are retained as evidence and never summed
or reduced by an arbitrary first-person choice.
"""

from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import Mapping, Sequence

from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, sha256_bytes, strict_json_loads
from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source, adapt_8k_item_index
from .observations import scope_key, structured_observation
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS
from .sources import validate_public_sec_filing_identity


C03_RESOLVER = "ecd_peo_total_compensation_v1"
C03_SPEC_PATH = "catalog/r5/C03_peo_total_compensation.md"
C04_RESOLVER = "auditor_change_dual_source_v1"
C04_SPEC_PATH = "catalog/r5/C04_auditor_changes.md"
C04_V2_RESOLVER = "auditor_change_complete_filings_v2"
C04_V2_SPEC_PATH = "catalog/r5/C04_auditor_changes_v2.md"
_XBRLI = "http://www.xbrl.org/2003/instance"
_ISO4217 = "http://www.xbrl.org/2003/iso4217"
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class GovernanceSignalError(ValueError):
    """Reject changed sources and unsupported source interpretations."""


def _need(condition, reason):
    if not condition:
        raise GovernanceSignalError(reason)


def _qname(value, namespaces):
    prefix, _, local = value.partition(":")
    return (namespaces.get(prefix, ""), local) if local else (namespaces.get("", ""), prefix)


class _FactAttributes(HTMLParser):
    """Supplement native values/contexts with original units and transforms."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.facts = {}
        self.units = {}
        self.ordinal = 0
        self.unit = None
        self.measure = None
        self.measure_namespace = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        namespaces = dict(self.stack[-1][1]) if self.stack else {}
        namespaces.update({k[6:]: v for k, v in attrs.items() if k.startswith("xmlns:")})
        if "xmlns" in attrs: namespaces[""] = attrs["xmlns"]
        _need(len(self.stack) < 512, "GOVERNANCE_XML_NESTING_LIMIT")
        if tag not in _VOID: self.stack.append((tag, namespaces))
        uri, local = _qname(tag, namespaces)
        if "contextref" in attrs:
            self.ordinal += 1
            _need(self.ordinal <= 250000, "GOVERNANCE_FACT_LIMIT")
            self.facts[self.ordinal] = {"attrs": attrs, "namespaces": namespaces,
                "concept": _qname(attrs.get("name", tag), namespaces), "tag": tag}
        if uri == _XBRLI and local == "unit":
            _need(self.unit is None and attrs.get("id") and attrs["id"] not in self.units,
                  "GOVERNANCE_DUPLICATE_OR_NESTED_UNIT")
            self.unit = attrs["id"]
            self.units[self.unit] = {"measures": [], "divided": False}
        elif uri == _XBRLI and local == "divide" and self.unit is not None:
            self.units[self.unit]["divided"] = True
        elif uri == _XBRLI and local == "measure" and self.unit is not None:
            _need(self.measure is None, "GOVERNANCE_NESTED_MEASURE")
            self.measure, self.measure_namespace = [], namespaces

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID: self.handle_endtag(tag)

    def handle_data(self, data):
        if self.measure is not None:
            _need(sum(len(x) for x in self.measure) + len(data) < 1024, "GOVERNANCE_UNIT_TEXT_LIMIT")
            self.measure.append(data)

    def handle_endtag(self, tag):
        namespaces = self.stack[-1][1] if self.stack else {}
        uri, local = _qname(tag, namespaces)
        if uri == _XBRLI and local == "measure" and self.measure is not None:
            self.units[self.unit]["measures"].append(_qname("".join(self.measure).strip(), self.measure_namespace))
            self.measure = self.measure_namespace = None
        elif uri == _XBRLI and local == "unit":
            _need(self.measure is None, "GOVERNANCE_UNCLOSED_MEASURE")
            self.unit = None
        matches = [i for i, row in enumerate(self.stack) if row[0] == tag]
        if matches: del self.stack[matches[-1]:]


def _source_value(fact, metadata):
    attrs, namespaces = metadata["attrs"], metadata["namespaces"]
    nil = [v for k, v in attrs.items() if _qname(k, namespaces) == ("http://www.w3.org/2001/XMLSchema-instance", "nil")]
    _need(not nil or nil == ["false"] or nil == ["0"], "C03_NIL_TARGET_COMPENSATION")
    _need(attrs.get("sign", "") in {"", "-"}, "C03_UNSUPPORTED_SIGN")
    transform = attrs.get("format", "")
    if transform:
        uri, local = _qname(transform, namespaces)
        _need(re.fullmatch(r"https?://www\.xbrl\.org/inlineXBRL/transformation/\d{4}-\d{2}-\d{2}", uri) is not None,
              "C03_UNSUPPORTED_TRANSFORM_NAMESPACE")
        _need(local in {"num-dot-decimal", "numdotdecimal", "fixed-zero", "numdash"},
              "C03_UNSUPPORTED_NUMERIC_TRANSFORM")
        if local in {"fixed-zero", "numdash"}:
            _need(str(fact["text"]).strip() in {"-", "—", "–", "0"}, "C03_ZERO_TRANSFORM_TEXT_CONFLICT")
            return "0"
    return _numeric_xbrl_value(text=fact["text"], scale=fact["scale"], sign=fact["sign"])


def resolve_c03(*, raw_bytes: bytes, raw_blob: Mapping, source_reference: Mapping,
                target: Mapping, expected_cik: str, compiled_spec: Mapping) -> dict:
    """Select a scalar only when raw ECD facts determine one person/amount.

    ``target`` is the already-discovered annual company/period/scope grain.
    This function does not label an old proxy as current or issue source/live
    credit; callers must bind their selected filing to the input inventory.
    """
    _need(type(raw_bytes) is bytes and 0 < len(raw_bytes) <= RESOURCE_LIMITS.max_html_bytes,
          "GOVERNANCE_SOURCE_SIZE_LIMIT")
    blob, ref = validate_record(record=dict(raw_blob)), validate_record(record=dict(source_reference))
    _need(blob["record_type"] == "RAW_BLOB" and ref["record_type"] == "SOURCE_REFERENCE",
          "GOVERNANCE_SOURCE_RECORD_TYPE")
    _need(blob["raw_asset_id"] == ref["raw_asset_id"] == "sha256:" + sha256_bytes(content=raw_bytes)
          and blob["byte_length"] == len(raw_bytes), "GOVERNANCE_SOURCE_BYTES_CHANGED")
    _need(set(target) == {"company_id", "period_start", "period_end", "scope", "scope_key"}
          and target["scope"] == {"entity_scope": "registrant"}
          and target["scope_key"] == scope_key(scope=target["scope"]), "C03_TARGET_SCOPE_INVALID")
    _need(ref["company_id"] == target["company_id"], "GOVERNANCE_COMPANY_MISMATCH")
    _need(date.fromisoformat(target["period_end"]) > date.fromisoformat(target["period_start"]),
          "C03_ANNUAL_DURATION_REQUIRED")
    validate_public_sec_filing_identity(raw_blob=blob, source_url=ref["source_url"],
        accession=ref["accession"], document_name=ref["document_name"],
        source_role="target_primary", allowed_ciks=[expected_cik])
    semantic = compiled_spec["compiled"]
    _need(semantic["metric_id"] == "C03" and semantic["kind"] == "direct_numeric"
          and semantic["canonical_unit"] == "USD"
          and semantic["quality_rule"].get("resolver") == C03_RESOLVER,
          "C03_SPEC_REQUIRED")
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    metadata = _FactAttributes()
    metadata.feed(raw_bytes.decode("utf-8"))
    metadata.close()
    _need(metadata.unit is None and metadata.measure is None and metadata.ordinal == len(parsed.facts),
          "GOVERNANCE_ATTRIBUTE_STREAM_INCOMPLETE")
    forms = {f["text"].upper().replace(" ", "") for f in parsed.facts
             if metadata.facts[f["ordinal"]]["concept"][1].casefold() == "documenttype"
             and re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", metadata.facts[f["ordinal"]]["concept"][0])}
    _need(forms == {"DEF14A"}, "C03_DEF14A_SOURCE_REQUIRED")
    candidates, excluded, failures = [], [], []
    people_facts = []
    current_people = {}
    historical_people = {}
    for fact in parsed.facts:
        meta = metadata.facts[fact["ordinal"]]
        uri, local = meta["concept"]
        if local.casefold() != "peoname" or re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", uri) is None:
            continue
        context = parsed.contexts[fact["context_ref"]]
        dimensions = dict(context["dimensions"])
        members = [_qname(v, meta["namespaces"]) for v in dimensions.values()]
        valid_axes = all(_qname(k, meta["namespaces"])[1] == "IndividualAxis"
                         and re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", _qname(k, meta["namespaces"])[0])
                         for k in dimensions)
        same_period = context["period_start"] == target["period_start"] and context["period_end"] == target["period_end"]
        identity_valid = (str(context["entity_identifier"]).isdigit()
                          and str(int(context["entity_identifier"])) == str(int(expected_cik))
                          and not context["typed_dimension_count"] and valid_axes
                          and all(all(member) for member in members))
        person = {"name": " ".join(fact["text"].split()), "person_members": [list(m) for m in members],
                  "period_start": context["period_start"], "period_end": context["period_end"],
                  "locator": {"ordinal": fact["ordinal"], "qualified_name": fact["qualified_name"], "context_ref": fact["context_ref"]},
                  "identity_valid": identity_valid}
        people_facts.append(person)
        if same_period and (not identity_valid or not person["name"]):
            failures.append({"reason": "C03_PEO_NAME_SCOPE_CONFLICT", "person_fact": person})
        if identity_valid and person["name"] and len(members) == 1:
            (current_people if same_period else historical_people).setdefault(tuple(members[0]), []).append(person)
    all_peo = 0
    for fact in parsed.facts:
        meta = metadata.facts[fact["ordinal"]]
        uri, local = meta["concept"]
        if local.casefold() != "peototalcompamt":
            continue
        all_peo += 1
        _need(re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", uri) is not None,
              "C03_ECD_TAXONOMY_REQUIRED")
        _need(meta["attrs"]["contextref"] == fact["context_ref"], "GOVERNANCE_NATIVE_ORDINAL_MISMATCH")
        context = parsed.contexts[fact["context_ref"]]
        locator = {"ordinal": fact["ordinal"], "qualified_name": fact["qualified_name"],
                   "context_ref": fact["context_ref"]}
        if context["period_start"] != target["period_start"] or context["period_end"] != target["period_end"]:
            excluded.append({"locator": locator, "reason": "OTHER_PERIOD",
                             "period_start": context["period_start"], "period_end": context["period_end"]})
            continue
        reason = None
        if not str(context["entity_identifier"]).isdigit() or str(int(context["entity_identifier"])) != str(int(expected_cik)):
            reason = "C03_TARGET_ENTITY_CONFLICT"
        elif context["typed_dimension_count"]:
            reason = "C03_TYPED_PERSON_SCOPE_UNSUPPORTED"
        dimensions = dict(context["dimensions"])
        if any(_qname(k, meta["namespaces"])[1] != "IndividualAxis"
               or re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", _qname(k, meta["namespaces"])[0]) is None
               for k in dimensions):
            reason = "C03_NON_PERSON_DIMENSION"
        if any(not all(_qname(v, meta["namespaces"])) for v in dimensions.values()):
            reason = "C03_UNBOUND_PERSON_MEMBER"
        if metadata.units.get(fact["unit_ref"]) != {"measures": [(_ISO4217, "USD")], "divided": False}:
            reason = "C03_USD_UNIT_REQUIRED"
        row = {"locator": locator, "dimensions": dimensions, "source_text": fact["text"],
               "period_start": context["period_start"], "period_end": context["period_end"],
               "entity_identifier": context["entity_identifier"], "unit_ref": fact["unit_ref"],
               "source_transform": meta["attrs"].get("format", "")}
        if reason is None:
            try:
                row["value"] = _source_value(fact, meta)
            except ValueError as error:
                reason = str(error)
        if reason:
            row["reason"] = reason
            failures.append(row)
        else:
            row["person_members"] = [list(_qname(v, meta["namespaces"])) for v in dimensions.values()]
            members = [tuple(p) for p in row["person_members"]]
            # A fixed-zero dash is excluded only when the source's typed name
            # contexts bind this person to other periods, and explicitly name
            # the current period's different PEO. A bare zero has no such rule.
            if current_people and len(members) == 1 and members[0] not in current_people:
                historical = historical_people.get(members[0], [])
                if (historical and row["value"] == "0" and str(fact["text"]).strip() in {"-", "—", "–"}
                        and _qname(row["source_transform"], meta["namespaces"])[1] in {"fixed-zero", "numdash"}):
                    excluded.append({**row, "reason": "OTHER_PERIOD_PEO_ZERO_PLACEHOLDER",
                                     "other_period_person_facts": historical,
                                     "current_person_facts": [p for ps in current_people.values() for p in ps]})
                    continue
                failures.append({**row, "reason": "C03_CURRENT_PEO_IDENTITY_MISMATCH"})
                continue
            candidates.append(row)
    values = sorted({row["value"] for row in candidates})
    people = sorted(({tuple(p) for row in candidates for p in row["person_members"]
                     if not (p[1] == "PeoMember" and re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", p[0]))})
                    | {p for p in current_people if not (p[1] == "PeoMember" and re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/\d{4}", p[0]))})
    if any(len({p["name"] for p in names}) > 1 for names in current_people.values()):
        failures.append({"reason": "C03_CONFLICTING_PEO_NAMES"})
    if failures:
        reason = "C03_TARGET_FACT_INVALID"
    elif not candidates:
        reason = "C03_TARGET_PERIOD_NOT_FOUND" if all_peo else "C03_PEO_FACT_NOT_FOUND"
    elif len(values) > 1:
        reason = "C03_MULTIPLE_REPORTED_AMOUNTS"
    elif len(people) > 1:
        reason = "C03_MULTIPLE_REPORTED_PEOPLE"
    else:
        reason = "PASS"
    selection = {"resolver": C03_RESOLVER, "source_reference_id": ref["source_reference_id"],
                 "raw_asset_id": blob["raw_asset_id"], "target": dict(target),
                 "candidates": candidates, "excluded": excluded, "invalid_target_facts": failures,
                 "reported_person_facts": people_facts,
                 "distinct_values": values, "specific_person_members": [list(p) for p in people],
                 "reason_code": reason}
    selection["selection_id"] = content_hash(value=selection)
    observation = None
    if reason == "PASS":
        observation = structured_observation(metric_id="C03", semantic_role="peo_total_compensation",
            company_id=target["company_id"], period_start=target["period_start"], period_end=target["period_end"],
            scope=target["scope"], value=values[0], unit="USD", quality="EXACT",
            source_binding={"raw_asset_id": blob["raw_asset_id"], "source_reference_id": ref["source_reference_id"],
                            "accession": ref["accession"], "document_name": ref["document_name"],
                            "source_role": ref["source_role"], "selection_id": selection["selection_id"],
                            "fact_locators": [r["locator"] for r in candidates]})
        result, trace = calculate_observation_metric(compiled_spec=compiled_spec, target=target,
            company_traits=[], observation=observation)
    else:
        result, trace = withheld_metric_result(compiled_spec=compiled_spec, target=target, reason_code=reason)
    return {"record_type": "C03_SOURCE_RESOLUTION", "selection": selection,
            "observation": observation, "result": result, "trace": trace,
            "business_calls": [0, 0, 0], "formal_publication_authorized": False}


def replay_c03(*, resolution: Mapping, **source_args) -> dict:
    """Recompute the complete native chain from original source bytes."""
    rebuilt = resolve_c03(**source_args)
    _need(rebuilt == resolution, "C03_SOURCE_REPLAY_MISMATCH")
    return rebuilt


def _auditor_filing(*, sources: Sequence[Mapping], company_id: str, cik: str,
                    period_end: str) -> dict:
    """Read all caller-discovered sources for one filing without fetching."""
    _need(bool(sources), "C04_FILING_SOURCE_REQUIRED")
    accessions, forms, references, facts, problems = set(), set(), [], [], []
    for source in sources:
        _need(set(source) == {"raw_bytes", "raw_blob", "source_reference"}, "C04_SOURCE_FIELDS_INVALID")
        raw, blob, ref = source["raw_bytes"], validate_record(record=dict(source["raw_blob"])), validate_record(record=dict(source["source_reference"]))
        _need(type(raw) is bytes and 0 < len(raw) <= RESOURCE_LIMITS.max_html_bytes, "C04_SOURCE_SIZE_LIMIT")
        _need(blob["record_type"] == "RAW_BLOB" and ref["record_type"] == "SOURCE_REFERENCE"
              and blob["raw_asset_id"] == ref["raw_asset_id"] == "sha256:" + sha256_bytes(content=raw)
              and blob["byte_length"] == len(raw), "C04_SOURCE_BYTES_CHANGED")
        _need(ref["company_id"] == company_id, "C04_COMPANY_MISMATCH")
        expected_url = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(str(int(cik)), ref["accession"].replace("-", ""), ref["document_name"])
        _need(ref["source_url"] == expected_url, "C04_SAME_CIK_FILING_REQUIRED")
        accessions.add(ref["accession"])
        references.append(ref)
        parsed = parse_accession_xbrl_source(raw_bytes=raw)
        metadata = _FactAttributes()
        metadata.feed(raw.decode("utf-8"))
        metadata.close()
        _need(metadata.ordinal == len(parsed.facts), "C04_ATTRIBUTE_STREAM_INCOMPLETE")
        for fact in parsed.facts:
            uri, local = metadata.facts[fact["ordinal"]]["concept"]
            if re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", uri) is None:
                continue
            if local.casefold() == "documenttype": forms.add(fact["text"].upper())
            if local.casefold() != "auditorname": continue
            context = parsed.contexts[fact["context_ref"]]
            lexical = " ".join(fact["text"].split())
            canonical = "".join(c for c in lexical.casefold() if c.isalnum())
            row = {"source_reference_id": ref["source_reference_id"], "raw_asset_id": blob["raw_asset_id"],
                   "accession": ref["accession"], "name": lexical, "canonical_name": canonical,
                   "period_start": context["period_start"], "period_end": context["period_end"],
                   "entity_identifier": context["entity_identifier"],
                   "locator": {"qualified_name": fact["qualified_name"], "context_ref": fact["context_ref"], "ordinal": fact["ordinal"]}}
            if (context["period_end"] != period_end or context["dimensions"] or context["typed_dimension_count"]
                    or not str(context["entity_identifier"]).isdigit()
                    or str(int(context["entity_identifier"])) != str(int(cik))):
                problems.append({**row, "reason": "C04_AUDITOR_FACT_SCOPE_CONFLICT"})
            elif canonical:
                facts.append(row)
    _need(len(accessions) == 1 and len(forms) == 1 and forms <= {"10-K", "10-K/A"}, "C04_FILING_IDENTITY_OR_FORM_CONFLICT")
    _need(len({r["source_reference_id"] for r in references}) == len(references), "C04_DUPLICATE_FILING_SOURCE")
    names = sorted({f["canonical_name"] for f in facts})
    return {"accession": next(iter(accessions)), "form": next(iter(forms)), "source_references": references,
            "facts": facts, "problems": problems, "canonical_names": names,
            "status": "CONFLICT" if problems or len(names) > 1 else "FOUND" if names else "MISSING"}


def resolve_c04(*, current_filings: Sequence[Sequence[Mapping]], prior_sources: Sequence[Mapping],
                target_accession: str, prior_period_end: str, target: Mapping,
                expected_cik: str, compiled_spec: Mapping, event_input: Mapping = None,
                prior_filings: Sequence[Sequence[Mapping]] = None) -> dict:
    """Compare same-CIK auditor facts and independently read complete 8-K items.

    ``current_filings`` is ordered target, then optional original-report
    fallback. The existing trusted source-discovery layer must prove this
    filing/material set, including amendments. Missing event input never turns
    equal year-end names into a confirmed no-change flag.
    """
    semantic = compiled_spec["compiled"]
    resolver = semantic["quality_rule"].get("resolver")
    successor = resolver == C04_V2_RESOLVER
    _need(semantic["metric_id"] == "C04" and semantic["kind"] == "direct_numeric"
          and semantic["canonical_unit"] == "flag" and resolver in {C04_RESOLVER, C04_V2_RESOLVER},
          "C04_SPEC_REQUIRED")
    _need(set(target) == {"company_id", "period_start", "period_end", "scope", "scope_key"}
          and target["scope"] == {"entity_scope": "registrant"}
          and target["scope_key"] == scope_key(scope=target["scope"]), "C04_TARGET_SCOPE_INVALID")
    _need(1 <= len(current_filings) <= (64 if successor else 2), "C04_ORDERED_CURRENT_FILINGS_REQUIRED")
    current = [_auditor_filing(sources=sources, company_id=target["company_id"], cik=expected_cik, period_end=target["period_end"])
               for sources in current_filings]
    _need(current[0]["accession"] == target_accession, "C04_FILED_TARGET_MUST_BE_FIRST")
    if len(current) > 1:
        _need(all(f["form"] == "10-K/A" for f in current[:-1]) and current[-1]["form"] == "10-K"
              and len({f["accession"] for f in current}) == len(current), "C04_ORIGINAL_FALLBACK_INVALID")
    selected = next((f for f in current if f["status"] != "MISSING"), current[-1])
    prior = None
    prior_checks = []
    _need(prior_filings is None or successor and not prior_sources, "C04_PRIOR_CHAIN_REQUIRES_V2")
    if prior_filings:
        _need(len(prior_filings) <= 64 and date.fromisoformat(prior_period_end) < date.fromisoformat(target["period_start"]), "C04_PRIOR_PERIOD_INVALID")
        prior_checks = [_auditor_filing(sources=sources, company_id=target["company_id"], cik=expected_cik, period_end=prior_period_end)
                        for sources in prior_filings]
        _need(prior_checks[-1]["form"] == "10-K" and all(f["form"] == "10-K/A" for f in prior_checks[:-1])
              and len({f["accession"] for f in prior_checks}) == len(prior_checks), "C04_PRIOR_CHAIN_INVALID")
        prior = next((f for f in prior_checks if f["status"] != "MISSING"), prior_checks[-1])
    elif prior_sources:
        _need(date.fromisoformat(prior_period_end) < date.fromisoformat(target["period_start"]), "C04_PRIOR_PERIOD_INVALID")
        prior = _auditor_filing(sources=prior_sources, company_id=target["company_id"], cik=expected_cik, period_end=prior_period_end)
        prior_checks = [prior]
    event_claims = None
    event_manifest = None
    event_sets, event_references = [], []
    if event_input is not None:
        history = event_input.get("history_inputs", [])
        _need(isinstance(history, list), "C04_HISTORY_INPUTS_INVALID")
        native_input = {k: v for k, v in event_input.items() if k != "history_inputs"}
        inventory = strict_json_loads(text=native_input["inventory_bytes"].decode("utf-8"))
        inventory_cik = inventory.get("cik")
        _need(type(inventory_cik) in (str, int) and str(inventory_cik).isdigit()
              and int(inventory_cik) == int(expected_cik),
              "C04_INVENTORY_ENTITY_CONFLICT")
        _need(isinstance(inventory.get("filings"), dict) and isinstance(inventory["filings"].get("recent"), dict)
              and isinstance(inventory["filings"].get("files"), list), "C04_COMPLETE_SUBMISSIONS_INDEX_REQUIRED")
        files = inventory["filings"]["files"]
        _need(all(isinstance(f, dict) and {"name", "filingFrom", "filingTo"}.issubset(f) for f in files),
              "C04_HISTORY_INDEX_INVALID")
        seen_names = set()
        for shard in files:
            name = shard["name"]
            _need(type(name) is str and re.fullmatch(
                "CIK" + str(int(expected_cik)).zfill(10)
                + r"-submissions-[0-9]+\.json", name) is not None
                and name not in seen_names, "C04_HISTORY_INDEX_INVALID")
            seen_names.add(name)
            try:
                start, end = shard["filingFrom"], shard["filingTo"]
                valid = (type(start) is str and type(end) is str
                         and date.fromisoformat(start).isoformat() == start
                         and date.fromisoformat(end).isoformat() == end
                         and start <= end)
            except ValueError:
                valid = False
            _need(valid, "C04_HISTORY_DATE_INVALID")
        needed = {f["name"] for f in files if f["filingFrom"] <= target["period_end"] and f["filingTo"] >= target["period_start"]}
        provided = [h["inventory_source_reference"]["document_name"] for h in history]
        _need(len(provided) == len(set(provided)) and set(provided) == needed, "C04_HISTORY_SHARD_SET_INCOMPLETE")
        event_manifest = event_input["source_set_manifest"]
        event_claims = []
        source_accessions = set()
        for index, source_input in enumerate([native_input] + history):
            _need(set(source_input) in ({"filing_documents", "source_set_manifest", "inventory_source_reference", "inventory_bytes"},
                                      {"filing_documents", "source_set_manifest", "inventory_source_reference", "inventory_bytes", "acquisition_discovery_receipt"}),
                  "C04_EVENT_INPUT_FIELDS_INVALID")
            manifest = source_input["source_set_manifest"]
            window = manifest["fiscal_or_date_window"]
            _need(manifest["company_id"] == target["company_id"] and manifest["form_types"] == (["8-K", "8-K/A"] if successor else ["8-K"])
                  and window.get("period_start") == target["period_start"] and window.get("period_end") == target["period_end"],
                  "C04_EVENT_SOURCE_WINDOW_MISMATCH")
            inventory_reference = source_input["inventory_source_reference"]
            event_references.append(inventory_reference)
            event_sets.append({"manifest": manifest, "inventory_source_reference": inventory_reference})
            inventory_name = inventory_reference["document_name"]
            _need(inventory_reference["source_url"] == "https://data.sec.gov/submissions/" + inventory_name,
                  "C04_INVENTORY_ORIGIN_MISMATCH")
            if index == 0:
                _need(inventory_name == "CIK" + str(int(expected_cik)).zfill(10) + ".json", "C04_INVENTORY_CIK_MISMATCH")
            for doc in source_input["filing_documents"]:
                accession = doc["primary_source_reference"]["accession"]
                _need(accession not in source_accessions, "C04_DUPLICATE_EVENT_ACCESSION")
                source_accessions.add(accession)
                for key in ("hdr_source_reference", "primary_source_reference"):
                    ref = doc[key]
                    _need(ref["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/" + str(int(expected_cik)) + "/"),
                          "C04_EVENT_CIK_MISMATCH")
                    event_references.append(ref)
            event_claims.extend(adapt_8k_item_index(**dict(source_input)))
    matching = [c for c in (event_claims or []) if c["attributes"]["item_code"] == "4.01"]
    comparison = None
    if selected["status"] == "FOUND" and prior is not None and prior["status"] == "FOUND":
        comparison = selected["canonical_names"] != prior["canonical_names"]
    if selected["status"] == "CONFLICT" or prior is not None and prior["status"] == "CONFLICT":
        reason, value = "C04_AUDITOR_SOURCE_CONFLICT", None
    elif matching:
        reason, value = "PASS", "1"
    elif comparison is True:
        reason, value = "PASS", "1"
    elif comparison is False and event_claims is not None:
        reason, value = "PASS", "0"
    else:
        reason, value = ("C04_EVENT_COVERAGE_REQUIRED" if comparison is False else "C04_COMPARABLE_AUDITOR_FACTS_MISSING"), None
    selection = {"resolver": resolver, "target": dict(target), "current_filing_checks": current,
                 "selected_current_accession": selected["accession"], "prior_filing_check": prior,
                 "names_differ": comparison, "event_source_set_manifest": event_manifest,
                 "event_source_sets": event_sets,
                 "event_item_claims": event_claims, "matched_item_4_01_claim_ids": [c["verified_claim_id"] for c in matching],
                 "reason_code": reason}
    if successor:
        selection["prior_filing_checks"] = prior_checks
    selection["selection_id"] = content_hash(value=selection)
    observation = None
    if value is None:
        result, trace = withheld_metric_result(compiled_spec=compiled_spec, target=target, reason_code=reason)
    else:
        references = [r for f in current + (prior_checks if successor else [prior] if prior is not None else []) for r in f["source_references"]] + event_references
        anchor = (next(r for r in event_references if r["source_reference_id"] == matching[0]["source_reference_id"])
                  if matching else selected["source_references"][0])
        observation = structured_observation(metric_id="C04", semantic_role="auditor_change_flag",
            company_id=target["company_id"], period_start=target["period_start"], period_end=target["period_end"],
            scope=target["scope"], value=value, unit="flag", quality="EXACT",
            source_binding={"raw_asset_id": anchor["raw_asset_id"], "source_reference_id": anchor["source_reference_id"],
                            "accession": anchor["accession"], "document_name": anchor["document_name"], "source_role": anchor["source_role"],
                            "selection_id": selection["selection_id"], "source_reference_ids": [r["source_reference_id"] for r in references],
                            "current_accession": selected["accession"], "prior_accession": prior["accession"] if prior else None,
                            "matched_item_4_01_claim_ids": selection["matched_item_4_01_claim_ids"],
                            "event_source_set_manifest_ids": [s["manifest"]["source_set_manifest_id"] for s in event_sets]})
        result, trace = calculate_observation_metric(compiled_spec=compiled_spec, target=target, company_traits=[], observation=observation)
    return {"record_type": "C04_SOURCE_RESOLUTION", "selection": selection, "observation": observation,
            "result": result, "trace": trace, "business_calls": [0, 0, 0], "formal_publication_authorized": False}


def replay_c04(*, resolution: Mapping, **source_args) -> dict:
    """Rebuild the comparison, source-set check and native result chain."""
    rebuilt = resolve_c04(**source_args)
    _need(rebuilt == resolution, "C04_SOURCE_REPLAY_MISMATCH")
    return rebuilt
