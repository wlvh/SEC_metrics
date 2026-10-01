"""Group complete nearby C02 source blocks for the explicit ordinary successor.

The original governance document and its full-source selector run first. This
view partitions *all* original blocks in order. A selected group contains every
selected block and at most two intervening context blocks; no source text is
trimmed to meet the existing 64-item native text protocol. The view and its
mapping are rebuilt from authenticated original bytes on every Run replay.
"""

from .canonical import content_hash, sha256_bytes
from .text_business_candidates import _check_document


POLICY = "COMPLETE_NEARBY_BLOCK_GROUPS_V1"
MAX_INTERVENING_BLOCKS = 2


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _clusters(selected):
    groups = []
    for index in selected:
        if not groups or index - groups[-1][-1] > MAX_INTERVENING_BLOCKS + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def grouped_governance_source(*, document, proposal, coverage, raw_bytes):
    """Return a reversible complete-document view and its bounded proposal.

    The number of groups is not clipped. The existing Spec and native Result
    checks refuse a source whose complete grouped set still exceeds its bound.
    """
    _check_document(document)
    _need(type(raw_bytes) is bytes and document["raw_asset_id"] == "sha256:" + sha256_bytes(content=raw_bytes),
          "C02_GROUPED_ORIGINAL_BYTES_CHANGED")
    _need(proposal["document_id"] == coverage["document_id"] == document["text_document_id"]
          and proposal["source_reference_id"] == coverage["source_reference_id"] == document["source_reference_id"],
          "C02_GROUPED_SOURCE_RELATION_CHANGED")
    blocks = document["blocks"]
    candidates = proposal["candidates"]
    selected = [candidate["block_index"] for candidate in candidates]
    _need(selected and selected == sorted(set(selected))
          and all(type(index) is int and 0 <= index < len(blocks) for index in selected),
          "C02_GROUPED_COMPLETE_SELECTION_REQUIRED")
    _need(all(candidate["document_id"] == document["text_document_id"]
              and candidate["source_reference_id"] == document["source_reference_id"]
              and candidate["section_id"] == "GOVERNANCE_DISCLOSURES"
              for candidate in candidates), "C02_GROUPED_CANDIDATE_SOURCE_CHANGED")
    groups = _clusters(selected)
    by_start = {group[0]: group for group in groups}
    chosen = {index: candidate for index, candidate in zip(selected, candidates)}
    partition, new_blocks, selected_new_indexes = [], [], []
    index = 0
    while index < len(blocks):
        group = by_start.get(index)
        end = group[-1] + 1 if group else index + 1
        original = blocks[index:end]
        _need(all(block["block_index"] == i and
                  sha256_bytes(content=raw_bytes[block["raw_start_byte"]:block["raw_end_byte"]])
                  == block["raw_span_sha256"]
                  for i, block in enumerate(original, start=index)),
              "C02_GROUPED_ORIGINAL_SPAN_CHANGED")
        _need(all(original[i]["raw_start_byte"] <= original[i]["raw_end_byte"]
                  <= original[i + 1]["raw_start_byte"]
                  for i in range(len(original) - 1)),
              "C02_GROUPED_ORIGINAL_ORDER_CHANGED")
        block = dict(original[0])
        block["block_index"] = len(new_blocks)
        block["source_block_range"] = [index, end]
        if group:
            block["text"] = "\n".join(item["text"] for item in original)
            block["raw_end_byte"] = original[-1]["raw_end_byte"]
            block["raw_span_sha256"] = sha256_bytes(
                content=raw_bytes[block["raw_start_byte"]:block["raw_end_byte"]])
            block["linked"] = any(item["linked"] for item in original)
            block["emphasized"] = any(item["emphasized"] for item in original)
            block["selected_source_blocks"] = list(group)
            block["context_source_blocks"] = [i for i in range(index, end) if i not in chosen]
            selected_new_indexes.append(block["block_index"])
        partition.append(block["source_block_range"])
        new_blocks.append(block)
        index = end
    _need([i for start, end in partition for i in range(start, end)] == list(range(len(blocks)))
          and len(selected_new_indexes) == len(groups)
          and [i for group in groups for i in group] == selected,
          "C02_GROUPED_SOURCE_PARTITION_INCOMPLETE")
    view_body = {key: value for key, value in document.items() if key != "text_document_id"}
    view_body.update(blocks=new_blocks, original_text_document_id=document["text_document_id"],
                     grouping_policy=POLICY, original_block_count=len(blocks))
    view = {**view_body, "text_document_id": content_hash(value=view_body)}
    mapping = [{"view_block_index": i, "source_block_range": block["source_block_range"],
                "selected_source_blocks": block.get("selected_source_blocks", []),
                "context_source_blocks": block.get("context_source_blocks", [])}
               for i, block in enumerate(new_blocks)]
    mapping_hash = content_hash(value=mapping)
    old_coverage_hash = coverage["coverage_hash"]
    scope = {key: value for key, value in coverage.items() if key != "coverage_hash"}
    scope.update(document_id=view["text_document_id"],
                 original_document_id=document["text_document_id"],
                 original_coverage_hash=old_coverage_hash,
                 complete_source_partition_hash=mapping_hash,
                 ranges=[{"section_id": "GOVERNANCE_DISCLOSURES", "start_block": 0,
                          "end_block_exclusive": len(new_blocks)}])
    new_coverage = {**scope, "coverage_hash": content_hash(value=scope)}
    original_proposal_id = proposal["proposal_id"]
    proposal_body = {key: value for key, value in proposal.items() if key != "proposal_id"}
    grouped_candidates = []
    for group, new_index in zip(groups, selected_new_indexes):
        original_candidate = chosen[group[0]]
        view_block = new_blocks[new_index]
        grouped_candidates.append({**original_candidate,
            "document_id": view["text_document_id"], "block_index": new_index,
            "text": view_block["text"],
            "raw_start_byte": view_block["raw_start_byte"],
            "raw_end_byte": view_block["raw_end_byte"],
            "raw_span_sha256": view_block["raw_span_sha256"],
            "labels": sorted({label for original_index in group
                              for label in chosen[original_index]["labels"]}),
            "selected_source_blocks": list(group),
            "context_source_blocks": list(view_block["context_source_blocks"])})
    proposal_body.update(document_id=view["text_document_id"], candidates=grouped_candidates,
                         selection_policy=POLICY, original_proposal_id=original_proposal_id,
                         complete_source_partition_hash=mapping_hash)
    new_proposal = {**proposal_body, "proposal_id": content_hash(value=proposal_body)}
    return view, new_proposal, new_coverage
