"""Check every development fact's names and numbers against the blocks it cites.

A coarse, mechanical screen for misattribution and invention, run before the
hand review: each capitalised word of three or more letters that is not a
common governance word, and each number, in a fact's statement must occur
(case-insensitively; numbers also without thousands separators) in the text
of the blocks the fact cites. A flag is a place to read, not a finding: a
statement may name a year or a count the filing gives elsewhere. Every flag is
read by hand in the README.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-model-method/fact_support.py \
        --inputs <dir> --answers <dir> --out <json>
Zero calls.
"""
import argparse
import json
import re
from pathlib import Path

NUMBER = re.compile(r"\b\d[\d,.]*%?")
WORD = re.compile(r"\b[A-Z][a-z]{2,}\b")
COMMON = {"The", "Board", "Committee", "Committees", "Director", "Directors", "Chair", "Chairman", "Lead",
          "Independent", "Executive", "Chief", "Officer", "President", "Annual", "Meeting", "Company", "All",
          "Each", "Inc", "Corporate", "Governance", "Nominating", "Audit", "Compensation", "Finance", "Risk",
          "Security", "Human", "Capital", "Management", "Talent", "Culture", "Policy", "Innovation", "Science",
          "Technology", "Regulatory", "Compliance", "Sustainability", "Standards", "Principles", "Guidelines",
          "Proxy", "Statement", "Vice"}
BLOCK = re.compile(r"\[B(\d+)\]\n(.*?)(?=\n\n\[B\d+\]\n|\Z)", re.S)


def flags(*, source_text, answer):
    blocks = {int(m.group(1)): m.group(2) for m in BLOCK.finditer(source_text)}
    found = []
    for number, fact in enumerate(answer["facts"]):
        cited = " ".join(blocks.get(i, "") for i in fact["source_blocks"])
        numbers = [n.rstrip(".,") for n in NUMBER.findall(fact["statement"])]
        absent_numbers = [n for n in numbers if n and n not in cited
                          and n.replace(",", "") not in cited.replace(",", "")]
        absent_words = sorted({w for w in WORD.findall(fact["statement"]) if w not in COMMON
                               and w.lower() not in cited.lower()})
        if absent_numbers or absent_words:
            found.append({"fact": number, "kind": fact["kind"], "statement": fact["statement"],
                          "source_blocks": fact["source_blocks"],
                          "numbers_not_in_cited_blocks": absent_numbers,
                          "words_not_in_cited_blocks": absent_words})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    rows = []
    for path in sorted(arguments.answers.glob("*.json")):
        answer = json.loads(path.read_text(encoding="utf-8"))
        source = (arguments.inputs / path.stem / "source.txt").read_text(encoding="utf-8")
        found = flags(source_text=source, answer=answer)
        rows.append({"position": path.stem, "facts": len(answer["facts"]), "flagged": found})
        print(path.stem, len(answer["facts"]), "facts", len(found), "flagged", flush=True)
    arguments.out.write_text(json.dumps({"record_type": "ISSUE_47_C02_DEV_FACT_SUPPORT_SCREEN",
                                         "rows": rows, "calls": {"provider": 0, "paid": 0, "sec": 0}},
                                        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
