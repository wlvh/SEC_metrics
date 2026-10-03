"""Usage: python3 answer_crosscheck.py <scratch dir holding c02pk/ and c02ans/> [answer file names]

Do an answer's 'why' texts describe its own packet's blocks or another packet's?

For each judged or listed block, the distinctive words of the reader's 'why'
(capitalized words of 4+ letters, numbers) are looked up in the block's text
(with two neighbours on each side) in the answer's own packet and, at the same
index, in every other packet. An entry that matches another packet better than
its own is reported. Analysis only.
"""
import json, re, sys, glob, os
S = sys.argv[1]
GENERIC = {"Board","Committee","Committees","Chair","Chairman","Director","Directors","Audit","Compensation",
           "Governance","Nominating","Independent","Lead","FACT","MIXED","NOT","Company","CEO","The","This",
           "Item","Annual","Meeting","Proxy","Statement","Corporate","Executive","Officer","Member","Members",
           "Financial","Expert","Rule","Science","Technology","Regulatory","Compliance","Report","Signature",
           "Value","Pool","Same","Also","Only","With","From","States","Names","Card","Table","Block","Note",
           "Lists","None","Each","Their","They","Also","Name","Title","Section","Policy","Principles","Fiscal"}
def words(text):
    out = set()
    for w in re.findall(r"[A-Z][a-zA-Z'\-]{3,}|\b\d{2,}\b", text):
        if w not in GENERIC:
            out.add(w)
    return out
def block_text(packet, i):
    blocks = packet["by_index"]
    return " ".join(blocks.get(j, "") for j in range(i - 2, i + 3))
packets = {}
for path in glob.glob(S + "/c02pk/*.json"):
    p = json.load(open(path))
    p["by_index"] = {b["i"]: b.get("text", "") for b in p["blocks"]}
    packets[os.path.basename(path)] = p
names = sys.argv[2:] or [os.path.basename(x) for x in glob.glob(S + "/c02ans/*.json")]
for name in sorted(names):
    ans = json.load(open(S + "/c02ans/" + name))
    own = packets[name]
    suspicious, checked, own_hits = [], 0, 0
    for entry in ans["selected"] + ans["facts"]:
        ws = words(entry.get("why", ""))
        if not ws:
            continue
        checked += 1
        own_text = block_text(own, entry["i"])
        own_score = sum(1 for w in ws if w in own_text) / len(ws)
        own_hits += own_score >= 0.5
        best_other = max(((sum(1 for w in ws if w in block_text(p, entry["i"])) / len(ws), other)
                          for other, p in packets.items() if other != name), default=(0, None))
        if best_other[0] > own_score:
            suspicious.append((entry["i"], round(own_score, 2), best_other, sorted(ws)[:6]))
    print(name, "checked", checked, "own>=0.5:", own_hits, "better elsewhere:", len(suspicious))
    for s in suspicious[:8]:
        print("   ", s)
