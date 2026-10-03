"""D03 reported-action facts and bounded semantic-review source candidates.

A current filing may report an old action. These proposals preserve that
separation and never infer no investigation from a keyword miss. No native
Result, provider attempt, acquisition credit or review decision is created.
"""
from __future__ import annotations

from pathlib import Path
from html.parser import HTMLParser
import re

from .canonical import content_hash, strict_json_file
from .text_business_candidates import _bound_source, _excerpt, _substantive, legal_risk_candidates
from .text_coverage import build_text_document

_POLICY = strict_json_file(path=Path(__file__).resolve().parents[2] / "catalog/r6/regulatory_investigation_candidates_v1.json")
_POLICY_HASH = content_hash(value=_POLICY)
_PATTERNS = {k:re.compile(v,re.I) for k,v in _POLICY["patterns"].items() if "{{SELF}}" not in v}


class RegulatoryCandidateError(ValueError):
    """The source or recomputed candidate binding is not proven."""


def _need(condition, reason):
    if not condition:
        raise RegulatoryCandidateError(reason)


def _sentences(text):
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\"“])",text):
        prefix = text[:match.start()]
        if any(prefix.endswith(a) for a in _POLICY["abbreviations"]):
            continue
        yield start,match.start(),text[start:match.start()]
        start = match.end()
    if start < len(text):
        yield start,len(text),text[start:]


def _self_aliases(document):
    aliases = [{"text":"we","basis":"SOURCE_AUTHOR_FIRST_PERSON","support":None}]
    names = document["registrant_names"]
    for name in names:
        aliases.append({"text":name,"basis":"NAMESPACE_CHECKED_DEI_REGISTRANT_NAME","support":None})
        pattern = re.compile(re.escape(name) + r"\.?" + _POLICY["patterns"]["alias_parenthetical"],re.I)
        for block in document["blocks"]:
            for match in pattern.finditer(block["text"]):
                quoted=list(_PATTERNS["quoted_alias"].finditer(match.group(1)))
                if not quoted or not _PATTERNS["alias_intro"].search(match.group(1)):
                    continue
                name_compact=re.sub(r"\W","",name).casefold()
                first=quoted[0].group(1).casefold()
                first_compact=re.sub(r"\W","",first)
                if not (first.removeprefix("the ") in _POLICY["generic_entity_aliases"]
                        or first in _POLICY["source_author_pronouns"]
                        or len(first_compact)>=3 and name_compact.startswith(first_compact)):
                    continue
                for alias in quoted:
                    value=alias.group(1)
                    compact=re.sub(r"\W","",value).casefold()
                    generic=value.casefold().removeprefix("the ") in _POLICY["generic_entity_aliases"]
                    # A quoted transaction or class of stock after the name is
                    # not an issuer alias. Accept only explicit generic aliases
                    # or a shorter rendering of the same registrant name.
                    if not (generic or len(compact)>=3 and name_compact.startswith(compact)):
                        continue
                    support=_excerpt(document,block,"FULL_DOCUMENT_ALIAS_DEFINITION",["SOURCE_ENTITY_ALIAS"])
                    aliases.append({"text":value,"basis":"EXPLICIT_SAME_NAME_PARENTHETICAL","support":support})
                    if generic and not value.casefold().startswith("the "):
                        aliases.append({"text":"the "+value,"basis":"EXPLICIT_SAME_NAME_PARENTHETICAL","support":support})
    by_text = {}
    for alias in aliases:
        by_text.setdefault(alias["text"].casefold(),alias)
    return list(by_text.values())


def _signals(text):
    return [name.upper() for name in ("prospective","resolution","partial_resolution","negated_action",
            "private_internal","third_party","generic_regulation") if _PATTERNS[name].search(text)]


def _quotation_ranges(raw_bytes):
    """Locate real HTML quotation containers without interpreting their text."""
    source = raw_bytes.decode("utf-8-sig")
    lines = [0]
    for match in re.finditer("\n", source):
        lines.append(match.end())

    class Quotes(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.opened, self.ranges = [], []

        def position(self):
            line, column = self.getpos()
            return lines[line - 1] + column

        def handle_starttag(self, tag, attrs):
            if tag in _POLICY["quotation_tags"]:
                self.opened.append((tag, self.position()))

        def handle_endtag(self, tag):
            matches = [i for i, item in enumerate(self.opened) if item[0] == tag]
            if matches:
                i = matches[-1]
                end = source.find(">", self.position()) + 1
                self.ranges.extend((start, end) for _, start in self.opened[i:])
                del self.opened[i:]

    parser = Quotes()
    parser.feed(source)
    parser.close()
    parser.ranges.extend((start, len(source)) for _, start in parser.opened)
    # Convert only the tag boundaries, once in source order, to raw byte offsets.
    positions = sorted({p for bounds in parser.ranges for p in bounds})
    offsets, previous, size = {}, 0, 3 if raw_bytes.startswith(b"\xef\xbb\xbf") else 0
    for position in positions:
        size += len(source[previous:position].encode("utf-8"))
        offsets[position] = size
        previous = position
    return [(offsets[start], offsets[end]) for start, end in parser.ranges]


def _facts(*, text, aliases, complete, quoted=False, context=()):
    alternatives = "(?:" + "|".join(re.escape(a["text"]) for a in sorted(aliases,key=lambda x:-len(x["text"]))) + ")"
    sentences = list(_sentences(text));facts=[]
    for rule in _POLICY["rules"]:
        pattern = re.compile(_POLICY["patterns"]["sentence_prefix"] +
            _POLICY["patterns"][rule["pattern"]].replace("{{SELF}}", "(?P<subject>"+alternatives+")")
            .replace("{{AUTHORITY}}",_POLICY["patterns"]["authority_actor"]),re.I)
        for index,(start,end,sentence) in enumerate(sentences):
            # Only the explicit "These include" rule joins adjacent sentences.
            if rule["rule_id"] == "CURRENT_LEGAL_INVENTORY" and index + 1 < len(sentences):
                end=sentences[index+1][1];sentence=text[start:end]
            match=pattern.search(sentence)
            if not match or not _PATTERNS["authority"].search(sentence) or not _PATTERNS["action"].search(sentence):
                continue
            if rule["rule_id"] == "ISSUED_PROCESS_TO_NAMED_ENTITY" and match.group("subject").casefold() == "we":
                continue
            flags=_signals(sentence)
            reasons=[]
            relation=_POLICY["authority_relations"].get(rule["rule_id"])
            authority_related=relation is None or re.search(relation.replace("{{AUTHORITY}}",_POLICY["patterns"]["authority_actor"]),sentence,re.I) is not None
            if not authority_related:reasons.append("AUTHORITY_ACTOR_RELATION_NOT_PROVEN")
            if not complete:reasons.append("SOURCE_OR_REQUIRED_NAVIGATION_INCOMPLETE")
            if quoted or _PATTERNS["discourse_qualification"].search(text) or any(
                    _PATTERNS["discourse_qualification"].search(p)
                    or _PATTERNS["reported_speech_intro"].search(p) for p in context):
                reasons.append("QUOTED_OR_QUALIFIED_DISCOURSE_REQUIRES_INTERPRETATION")
            if "NEGATED_ACTION" in flags:reasons.append("NEGATED_ACTION_CONTEXT_REQUIRES_INTERPRETATION")
            if "THIRD_PARTY" in flags:reasons.append("OTHER_ENTITY_RELATION_REQUIRES_INTERPRETATION")
            if "PRIVATE_INTERNAL" in flags:reasons.append("PRIVATE_OR_INTERNAL_ACTION_RELATION_REQUIRES_INTERPRETATION")
            if rule["current_status_asserted"] and "RESOLUTION" in _signals(text):
                reasons.append("MIXED_RESOLUTION_AND_CURRENT_CONTEXT_REQUIRES_INTERPRETATION")
            if rule["current_status_asserted"] and any(
                    _PATTERNS["linked_resolution"].search(p)
                    and _PATTERNS["resolution"].search(p)
                    and not _PATTERNS["explicit_unrelated"].search(p) for p in context):
                reasons.append("ADJACENT_LINKED_RESOLUTION_REQUIRES_INTERPRETATION")
            if "PROSPECTIVE" in flags:reasons.append("MIXED_OR_HYPOTHETICAL_ACTION_REQUIRES_INTERPRETATION")
            alias=next(a for a in aliases if a["text"].casefold()==match.group("subject").casefold())
            fact={"rule_id":rule["rule_id"],"fact_kind":rule["fact_kind"],"statement_text":sentence,
                  "visible_block_character_span":{"start":start,"end":end},"subject_binding":alias,
                  "source_date_literals":_PATTERNS["date_literal"].findall(sentence),
                  "status":"SOURCE_REPORTED_FACT" if not reasons else "SEMANTIC_REVIEW_REQUIRED",
                  "authority_relation_syntax_matched":authority_related,
                  "authority_to_action_relation_proven":authority_related and not reasons,
                  "reason_codes":reasons,"current_status_asserted":rule["current_status_asserted"] and not reasons,
                  "action_start_or_end_date_inferred":False,"same_as_annual_measurement_period_asserted":False,
                  "investigated_subject_identity_inferred_from_participation":False,
                  "investigation_case_identity_or_count_inferred":False}
            fact["fact_id"]=content_hash(value=fact);facts.append(fact)
    return facts


def prepare_regulatory_investigation_candidates(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Derive candidates from the actual annual source, not caller-chosen quotes."""
    _need(filing["form"] == "10-K","D03_ORDINARY_ANNUAL_SOURCE_REQUIRED")
    _bound_source(raw_bytes=raw_bytes,raw_blob=raw_blob,source_reference=source_reference,
                  company_id=company_id,cik=cik,filing=filing)
    document=build_text_document(raw_bytes=raw_bytes,raw_blob=raw_blob,source_reference=source_reference,
        expected_company_id=company_id,expected_cik=cik,expected_period_end=filing["reportDate"])
    navigation=legal_risk_candidates(document=document);aliases=_self_aliases(document)
    complete=navigation["coverage_status"] == "LOCAL_REQUESTED_RANGES_SCANNED"
    ranges=navigation["checked_ranges"];by_block={}
    for scope in ranges:
        for block in document["blocks"][scope["start_block"]:scope["end_block_exclusive"]]:
            if not _substantive(document,block):continue
            if not (_PATTERNS["action"].search(block["text"]) or _PATTERNS["authority"].search(block["text"])):continue
            by_block.setdefault(block["block_index"],(block,scope))
    candidates=[]
    quotations = _quotation_ranges(raw_bytes)
    for index,(block,scope) in sorted(by_block.items()):
        excerpt=_excerpt(document,block,scope["section_id"],["REGULATORY_LANGUAGE_CANDIDATE"])
        neighbors=[]
        for i in range(max(scope["start_block"],index-1),min(scope["end_block_exclusive"],index+1+_POLICY["context_neighbor_limit"])):
            if i!=index and _substantive(document,document["blocks"][i]):
                neighbors.append(_excerpt(document,document["blocks"][i],scope["section_id"],["ADJACENT_CONTEXT_ONLY"]))
        quoted = any(start < block["raw_end_byte"] and block["raw_start_byte"] < end
                     for start, end in quotations)
        facts=_facts(text=block["text"],aliases=aliases,complete=complete,
                     quoted=quoted,context=[n["text"] for n in neighbors])
        body={"excerpt":excerpt,"context_excerpts":neighbors,"language_signals":_signals(block["text"]),
              # A proven clause does not resolve the rest of the paragraph or
              # identify the target/phase of every proceeding mentioned in it.
              "facts":facts,"requires_semantic_review":True,
              "unmatched_language_semantically_resolved":False}
        candidates.append({**body,"candidate_id":content_hash(value=body)})
    checked={i for scope in ranges for i in range(scope["start_block"],scope["end_block_exclusive"])}
    outside=[_excerpt(document,b,"OUTSIDE_REQUESTED_RANGES",["UNMAPPED_ACTION_LANGUAGE"])
        for b in document["blocks"] if b["block_index"] not in checked and _substantive(document,b)
        and _PATTERNS["action"].search(b["text"]) and _PATTERNS["authority"].search(b["text"])]
    body={"record_type":"REGULATORY_INVESTIGATION_CANDIDATE_BUNDLE","metric_id":"D03","company_id":company_id,
          "source_reference_id":source_reference["source_reference_id"],"raw_asset_id":raw_blob["raw_asset_id"],
          "source_filing":dict(filing),"document_id":document["text_document_id"],"navigation_proposal_id":navigation["proposal_id"],
          "checked_ranges":ranges,"note_references":navigation["note_references"],"source_aliases":aliases,
          "coverage_status":navigation["coverage_status"],"coverage_reasons":navigation["coverage_reasons"],
          "candidates":candidates,"outside_requested_range_action_candidates":outside,
          "supported_fact_count":sum(f["status"]=="SOURCE_REPORTED_FACT" for c in candidates for f in c["facts"]),
          "semantic_scope_completeness_asserted":False,"not_disclosed_confirmed":False,
          "native_result_created":False,"publication_credit":False,"policy_hash":_POLICY_HASH}
    return {**body,"candidate_bundle_id":content_hash(value=body)}


def replay_regulatory_investigation_candidates(*, bundle, **source_arguments):
    rebuilt=prepare_regulatory_investigation_candidates(**source_arguments)
    _need(rebuilt==bundle,"D03_SOURCE_CANDIDATE_REPLAY_CHANGED")
    return rebuilt
