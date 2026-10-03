"""Designation name search passes list items: not names, not counted in the reach."""
import json, re, sys
from pathlib import Path
REPO = Path("/home/user/SEC_metrics")
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO))
from vnext import historical_board_composition_v3 as sel
S = Path("<scratch>")
orig = sel._card_name

def list_item(blocks, j):
    text = sel.clean(blocks[j]["text"])
    return bool(sel._BULLET.match(text)) and not sel._ONE_BULLET.match(text)

def card_name_items(blocks, before, after, registrant, *, passable=sel._card_field, spacers_free=False):
    if passable is sel._card_field or getattr(passable, "__name__", "") == "<lambda>":
        return orig(blocks, before, after, registrant, passable=passable, spacers_free=spacers_free)
    following = None
    seen, j = 0, after
    while 0 <= j < len(blocks) and seen < sel._CARD_REACH:
        text = sel.clean(blocks[j]["text"])
        if not text or sel._ONE_BULLET.match(text) or list_item(blocks, j):
            j += 1
            continue
        seen += 1
        following = sel._name_from(blocks, j, registrant)
        if following or not passable(blocks[j]):
            break
        j += 1
    preceding = None
    for k in sel._reach(blocks, before - 1, -1, spacers_free):
        if not sel.clean(blocks[k]["text"]):
            continue
        preceding = sel._full_name(blocks, k, registrant)
        if preceding or not sel._card_field(blocks[k]):
            break
    if following and preceding:
        return None
    return following or preceding

for p in sorted((S / "c02docs").glob("*.json")):
    d = json.loads(p.read_text())
    doc = d["document"]
    sel._card_name = orig
    c0 = {c["block_index"] for c in sel.board_composition_facts(document=doc, period_start=d["period_start"])["candidates"]}
    sel._card_name = card_name_items
    try:
        c1 = {c["block_index"] for c in sel.board_composition_facts(document=doc, period_start=d["period_start"])["candidates"]}
    finally:
        sel._card_name = orig
    rec = json.loads((REPO / d["reading"]).read_text())
    j = {r["i"]: r for r in [*rec["pool_facts"], *rec.get("outside_pool_facts", []), *rec["selected"], *rec.get("supplementary", [])]}
    pool = {r["i"] for r in rec.get("pool", [])}
    v = lambda i: j.get(i, {}).get("verdict") or ("POOL_NOT_FACT" if i in pool else "UNREAD")
    for i in sorted(c1 - c0):
        print("ADD ", d["position"], i, v(i), repr(doc["blocks"][i]["text"][:80]))
    for i in sorted(c0 - c1):
        print("DROP", d["position"], i, v(i), repr(doc["blocks"][i]["text"][:80]))
