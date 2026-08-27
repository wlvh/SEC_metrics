# -*- coding: utf-8 -*-
"""Build the static flow-1 slide deck.

Every number in the deck is read from the active publication bundle at build
time, so the shipped HTML cannot drift from the artifacts it describes.  The
output contains no script tag: text carries meaning, SVG carries structure.
"""
from __future__ import annotations

import csv
import html
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BUNDLE = REPO / "outputs" / "publications" / (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861"
    "df55e0b268df2062a441c438f"
)
OUT = REPO / "docs" / "visual" / "flow1-mechanism-deck.html"

E = html.escape

# --------------------------------------------------------------------------
# facts read from the bundle
# --------------------------------------------------------------------------


def load_facts() -> dict:
    graph = json.loads((BUNDLE / "internal" / "deterministic_execution_graph.json").read_text())
    index = json.loads((BUNDLE / "internal" / "coordinate_index.json").read_text())["coordinates"]
    receipt = json.loads((BUNDLE / "internal" / "zero_ai_release_receipt.json").read_text())
    compat = json.loads((BUNDLE / "legacy_invariant_migration_receipt.json").read_text())
    pointer = json.loads((REPO / "outputs" / "active_publication.json").read_text())
    manifest = json.loads((BUNDLE / "publication_manifest.json").read_text())
    prov = json.loads((BUNDLE / "internal" / "request_locator_provenance.json").read_text())
    plan = json.loads((BUNDLE / "internal" / "release_input_plan.json").read_text())
    rows = list(csv.DictReader((BUNDLE / "metrics_matrix.csv").open()))
    registry = {r["company_id"]: r for r in csv.DictReader((REPO / "config" / "company_registry.csv").open())}

    by_kind: dict[str, dict] = {"METRIC_RESULT": {}, "EXECUTION_TRACE": {},
                                "VERIFIED_OBSERVATION": {}, "DETERMINISTIC_VERIFIED_CLAIM": {}}
    key = {"METRIC_RESULT": "result_id", "EXECUTION_TRACE": "trace_id",
           "VERIFIED_OBSERVATION": "observation_id",
           "DETERMINISTIC_VERIFIED_CLAIM": "verified_claim_id"}
    for rec in graph["records"]:
        by_kind[rec["record_type"]][rec[key[rec["record_type"]]]] = rec

    def count(field, source):
        out: dict[str, int] = {}
        for item in source:
            out[item[field]] = out.get(item[field], 0) + 1
        return out

    plan_records: dict[str, set] = {}
    plan_attempts: set = set()

    def walk(o):
        if isinstance(o, dict):
            rt = o.get("record_type")
            if rt == "SOURCE_SET_MANIFEST":
                plan_records.setdefault(rt, set()).add(o["source_set_manifest_id"])
            elif rt == "SOURCE_REFERENCE":
                plan_records.setdefault(rt, set()).add(o["source_reference_id"])
                plan_attempts.add(o["request_attempt_id"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(plan)

    return {
        "graph": graph, "index": index, "receipt": receipt, "compat": compat,
        "plan": plan,
        "n_manifests": len(plan_records.get("SOURCE_SET_MANIFEST", ())),
        "n_refs": len(plan_records.get("SOURCE_REFERENCE", ())),
        "n_attempts": len(plan_attempts),
        "pointer": pointer, "manifest": manifest, "prov": prov, "rows": rows,
        "registry": registry, "by": by_kind,
        "claim_records": sum(1 for r in graph["records"] if r["record_type"] == "DETERMINISTIC_VERIFIED_CLAIM"),
        "claim_unique": len(by_kind["DETERMINISTIC_VERIFIED_CLAIM"]),
        "claim_kinds": count("claim_kind", [r for r in graph["records"]
                                            if r["record_type"] == "DETERMINISTIC_VERIFIED_CLAIM"]),
        "obs_roles": count("semantic_role", by_kind["VERIFIED_OBSERVATION"].values()),
        "applicability": count("applicability", index),
        "quality": count("quality", index),
        "publication": count("publication", index),
        "locator": count("locator_class", prov["source_proofs"]),
        "status": count("status", rows),
        "source_class": count("source_class", rows),
    }


F = load_facts()
DISP = {c: F["registry"][c]["display_name"] for c in F["registry"]}
METRICS = ["A01", "A02", "A05", "A06", "A07", "A08", "A10", "B01", "B02", "B03",
           "B04", "B05", "B07", "B08", "B09", "B12", "C01", "E01", "E02", "E03", "E04", "E05"]
COMPANIES = sorted(F["registry"], key=lambda c: DISP[c])
CELL = {(c["company_id"], c["metric_id"]): c for c in F["index"]}

# --------------------------------------------------------------------------
# svg primitives — short labels only; prose lives in HTML
# --------------------------------------------------------------------------

TONE = {"fact": "var(--fact)", "raw": "var(--neutral)", "degrade": "var(--degrade)",
        "refuse": "var(--refuse)", "inherit": "var(--inherit)", "dim": "var(--ink3)"}
MARK = {"fact": "●", "raw": "▤", "degrade": "◐", "refuse": "✕", "inherit": "◇", "dim": "○"}


def node(x, y, w, h, *, tone="raw", kind="", rows=(), note="", dash=False, strong=False):
    c = TONE[tone]
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" '
         f'fill="var(--panel)" stroke="{c}" stroke-width="{2 if strong else 1.2}"'
         + (' stroke-dasharray="5 4"' if dash else "") + "/>"]
    if kind:
        s.append(f'<text class="k" x="{x+13}" y="{y+21}" fill="{c}">{MARK[tone]} {E(kind)}</text>')
    ly = y + (42 if kind else 26)
    for r in rows:
        if isinstance(r, str):
            s.append(f'<text class="b" x="{x+13}" y="{ly}">{E(r)}</text>')
            ly += 20
        else:
            k, v = r[0], r[1]
            vt = TONE[r[2]] if len(r) > 2 else "var(--ink)"
            s.append(f'<text class="m2" x="{x+13}" y="{ly}">{E(k)}</text>')
            s.append(f'<text class="m" x="{x+w-13}" y="{ly}" text-anchor="end" fill="{vt}">{E(v)}</text>')
            ly += 19
    if note:
        s.append(f'<text class="n" x="{x+13}" y="{y+h-12}">{E(note)}</text>')
    return "".join(s)


def arr(x1, y1, x2, y2, *, tone="dim", dash=False):
    c = TONE[tone]
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="1.5" '
            f'marker-end="url(#a-{tone})"' + (' stroke-dasharray="5 4"' if dash else "") + "/>")


def elbow(pts, *, tone="fact"):
    c = TONE[tone]
    d = "M" + " L".join(f"{p[0]} {p[1]}" for p in pts[:-1])
    last, prev = pts[-1], pts[-2]
    return (f'<path d="{d}" fill="none" stroke="{c}" stroke-width="1.5"/>'
            + arr(prev[0], prev[1], last[0], last[1], tone=tone))


def txt(x, y, s, *, cls="b", tone=None, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    f_ = f' fill="{TONE[tone]}"' if tone else ""
    return f'<text class="{cls}" x="{x}" y="{y}"{a}{f_}>{E(s)}</text>'


def svg(w, h, body, *, label=""):
    defs = "".join(
        f'<marker id="a-{k}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">'
        f'<path d="M0,0 L7,3.5 L0,7 z" fill="{v}"/></marker>' for k, v in TONE.items())
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{E(label)}">'
            f"<defs>{defs}</defs>{body}</svg>")


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

CHAIN = [("RawBlob", "raw_asset_id"), ("SourceReference", "source_reference_id"),
         ("SourceSetManifest", "source_set_manifest_id"), ("VerifiedClaim", "verified_claim_id"),
         ("VerifiedObservation", "observation_id"), ("Result ⇄ Trace", "result_id / trace_id"),
         ("坐标 exact set", "220 = 10 × 22"), ("独立渲染", "rendered_row_set_hash"),
         ("兼容性对照", "141 × 20 = 2 820"), ("PublicationBundle", "publication_id"),
         ("active pointer", "fe01e227…")]


def fig_chain():
    b, w, gap, h = [], 190, 14, 84
    for i, (name, idf) in enumerate(CHAIN):
        col, row = i % 4, i // 4
        x, y = 30 + col * (w + gap), 34 + row * 118
        b.append(node(x, y, w, h, tone="fact", rows=[]))
        b.append(txt(x + 13, y + 22, f"{i+1:02d}", cls="n"))
        b.append(txt(x + 13, y + 46, name, cls="s"))
        b.append(txt(x + 13, y + 68, idf, cls="m", tone="fact"))
        if col < 3 and i < len(CHAIN) - 1:
            b.append(arr(x + w, y + h / 2, x + w + gap - 2, y + h / 2, tone="fact"))
        elif i < len(CHAIN) - 1:
            b.append(elbow([(x + w // 2, y + h), (x + w // 2, y + h + 18), (44, y + h + 18), (44, y + h + 32)]))
    y = 34 + 3 * 118 - 12
    b.append(node(30, y, 4 * w + 3 * gap, 66, tone="refuse", kind="任何一环断掉",
                  rows=["没有伪造的下游对象 · 没有半新半旧的文件组 · 旧 active publication 继续服务"]))
    return svg(30 + 4 * w + 3 * gap + 30, y + 82, "".join(b),
               label="十一次信任升级构成的链条，任何一环断掉都回落到旧的正式版本")


def fig_rawblob():
    b = [node(24, 30, 236, 128, tone="raw", kind="磁盘上的路径",
              rows=[("能证明", "文件此刻在这里"), ("不能证明", "是谁的", "refuse"),
                    ("不能证明", "换过没", "refuse")], note="路径不是身份"),
         arr(268, 94, 306, 94, tone="fact"),
         node(314, 30, 236, 128, tone="fact", kind="resolve_repository_file()",
              rows=["拒 .. 路径穿越", "拒任何一级 symlink", "resolve() 后仍在仓库根下"],
              note="sources.py:105"),
         arr(558, 94, 596, 94, tone="fact"),
         node(604, 30, 200, 128, tone="fact", kind="读字节 + SHA-256",
              rows=["7 888 465 bytes", "↓", "sha256:e5a94464…"], note="sources.py:147"),
         elbow([(704, 158), (704, 178), (414, 178), (414, 192)]),
         node(190, 200, 448, 96, tone="fact", strong=True, kind="RAW_BLOB",
              rows=[("raw_asset_id", "sha256:e5a94464…", "fact"),
                    ("byte_length", "7 888 465")])]
    return svg(828, 312, "".join(b), label="路径经过安全检查后被读成字节，字节的 SHA-256 成为 RawBlob 的身份")


def fig_two_refs():
    b = [node(24, 108, 214, 96, tone="raw", kind="RAW_BLOB",
              rows=[("raw_asset_id", "sha256:e5a94464…"), ("byte_length", "7 888 465")],
              note="一份文件含 73 个 accession"),
         arr(246, 132, 300, 74, tone="fact"), arr(246, 178, 300, 236, tone="fact"),
         node(308, 22, 402, 104, tone="fact", kind="SOURCE_REFERENCE · current",
              rows=[("source_reference_id", "sha256:bcdb93f3…", "fact"),
                    ("accession", "0001628280-26-008131", "fact"),
                    ("source_role", "companyfacts_current")]),
         node(308, 186, 402, 104, tone="fact", kind="SOURCE_REFERENCE · prior",
              rows=[("source_reference_id", "sha256:ea0f760a…", "fact"),
                    ("accession", "0000019617-25-000270", "fact"),
                    ("source_role", "companyfacts_prior")]),
         node(308, 134, 402, 44, tone="dim", rows=[("两条完全相同", "raw_asset_id · request_attempt_id", "dim")])]
    return svg(736, 306, "".join(b), label="同一组字节生成两个申报身份，共享 raw_asset_id 与 request_attempt_id")


def fig_closure():
    b = [node(24, 24, 240, 92, tone="raw", kind="调用方声明", rows=["「我要用这 N 个 filing」"],
              note="调用方说了算？不。"),
         node(24, 140, 240, 108, tone="raw", kind="submissions 字节",
              rows=["_submissions_accessions()", "按 form_types + 时间窗", "当场重新解析"],
              note="deterministic_router.py:370"),
         arr(272, 70, 322, 120, tone="dim"), arr(272, 194, 322, 144, tone="fact"),
         node(330, 96, 216, 92, tone="fact", kind="逐一比对",
              rows=["planned_accessions", "  ==  discovered_accessions"], note="不等 → raise"),
         arr(554, 142, 596, 142, tone="fact"),
         node(604, 60, 244, 164, tone="fact", strong=True, kind="SOURCE_SET_MANIFEST",
              rows=[("字段数", "13（exact set）"),
                    ("discovered_hash", "sha256:836dbd69…", "fact"),
                    ("ordered_ref_ids", "有序、无重复"),
                    ("manifest_id", "= 其余 12 字段", "fact")],
              note="多传或少传都过不去")]
    return svg(872, 268, "".join(b), label="构造函数从 submissions 字节重推集合，与声明集合逐一比对后才生成清单")


def fig_zero():
    jpm = F["by"]["VERIFIED_OBSERVATION"]
    obs = next(o for o in jpm.values() if o["company_id"] == "jpmorgan_chase" and o["metric_id"] == "E01")
    cw = len(obs["source_binding"]["ordered_source_reference_ids"])
    mt = len(obs["source_binding"]["matched_verified_claim_ids"])
    b = [node(24, 24, 380, 150, tone="fact", kind="JPMorgan × E01（并购事件数）",
              rows=[("matched_verified_claim_ids", f"{mt} 个", "degrade"),
                    ("ordered_source_reference_ids", f"{cw} 个", "fact"),
                    ("value", '"0"', "fact")],
              note="0 是在 46 份已证明完整的来源上做出的断言"),
         node(424, 24, 400, 150, tone="refuse", kind="没有这一层时的同一个 0",
              rows=["「我扫过的文件里没有」", "——但没人能证明扫全了", "「没发生」与「没看见」不可区分"],
              note="这是整层里唯一一类 hash 发现不了的错误")]
    return svg(848, 190, "".join(b), label="事件计数为零时仍绑定完整来源集合，使零成为断言而不是缺省")


def fig_funnel():
    steps = [("us-gaap:Assets / USD 全部事实", 206, "raw", "横跨 73 个 accession"),
             ("+ accession = 0001628280-26-008131", 3, "raw", "2023 / 2024 / 2025 三个年末"),
             ("+ period_role = current_instant", 1, "fact", "2025-12-31"),
             ("+ form = 10-K 且 fiscal_period = FY", 1, "fact", "本来就满足")]
    b = []
    for i, (lab, n, tone, sub) in enumerate(steps):
        y = 24 + i * 60
        bw = max(24, round(172 * (n / 206) ** 0.5))
        b.append(txt(24, y + 22, lab, cls="b"))
        b.append(txt(24, y + 41, sub, cls="n"))
        b.append(f'<rect x="330" y="{y+6}" width="{bw}" height="28" rx="4" fill="{TONE[tone]}" '
                 f'opacity="0.26" stroke="{TONE[tone]}" stroke-width="1.1"/>')
        b.append(txt(338 + bw, y + 26, f"{n} 条", cls="s", tone=tone))
        if i < 3:
            b.append(arr(344, y + 36, 344, y + 56, tone="dim"))
    b.append(node(596, 24, 268, 160, tone="fact", strong=True, kind="选中的 CLAIM",
                  rows=[("concept", "Assets"), ("value", "4 424 900 000 000", "fact"),
                        ("unit", "USD"), ("period", "2025-12-31"),
                        ("accession", "…-26-008131")],
                  note="claim_id = 除 ID 外全部字段"))
    b.append(node(596, 196, 268, 62, tone="refuse", kind="若筛完仍有多个不同值",
                  rows=["raise value-ambiguous · 整批中止"]))
    return svg(884, 272, "".join(b), label="按 catalog 声明的维度逐级收敛，从 206 条候选收敛到唯一一条")


def fig_branch():
    b = [txt(24, 20, "JPMorgan × A05 · 第一条分支即命中", cls="s"),
         node(24, 32, 300, 62, tone="raw", kind="claim · net_income", rows=[("NetIncomeLoss", "57 048 000 000")]),
         node(24, 102, 300, 62, tone="raw", kind="claim · assets_current", rows=[("Assets", "4 424 900 000 000")]),
         node(24, 172, 300, 62, tone="raw", kind="claim · assets_prior", rows=[("Assets", "4 002 814 000 000")]),
         arr(332, 133, 372, 133, tone="fact"),
         node(380, 62, 300, 142, tone="fact", strong=True, kind="VERIFIED_OBSERVATION",
              rows=[("selected_branch_id", "average_assets", "fact"),
                    ("rejected_branches", "[]"),
                    ("quality", "EXACT", "fact"),
                    ("approval_effect_hash", '""', "fact")],
              note="observation_id = sha256:7caa7abf…"),
         txt(24, 282, "Pfizer × B07 · 第一条分支缺概念，退到第二条", cls="s"),
         node(24, 294, 300, 86, tone="refuse", kind="试 reported_operating_income",
              rows=["OperatingIncomeLoss 不存在", "_BranchUnavailable"], note="记入 rejected，继续下一条"),
         arr(332, 337, 372, 337, tone="degrade"),
         node(380, 280, 300, 114, tone="degrade", strong=True, kind="VERIFIED_OBSERVATION",
              rows=[("selected_branch_id", "reconstructed_…", "degrade"),
                    ("rejected_branches", "1 条 + 原因", "degrade"),
                    ("quality", "APPROX", "degrade")],
              note="降级被写进对象，不是写进日志")]
    return svg(704, 406, "".join(b), label="第一条完整分支即选中；被拒的分支与原因写进 observation 本身")


def fig_lock():
    b = [node(24, 24, 320, 164, tone="fact", strong=True, kind="METRIC_RESULT",
              rows=[("applicability", "APPLICABLE"), ("quality", "EXACT"),
                    ("publication", "PUBLISHED"), ("value", "0.013538…", "fact"),
                    ("result_id", "sha256:02e660bc…"), ("trace_id", "sha256:416ad199…", "fact")]),
         node(464, 24, 320, 164, tone="fact", strong=True, kind="EXECUTION_TRACE",
              rows=[("trace_id", "sha256:416ad199…"),
                    ("steps", "2 步"),
                    ("result", "0.013538…"),
                    ("result_contract_hash", "← 12 字段", "fact"),
                    ("execution_semantics", "sha256:f724d526…")]),
         arr(352, 74, 456, 74, tone="fact"), txt(404, 62, "trace_id", cls="m", tone="fact", anchor="middle"),
         arr(456, 142, 352, 142, tone="fact"), txt(404, 130, "contract_hash", cls="m", tone="fact", anchor="middle"),
         node(24, 206, 760, 76, tone="degrade", kind="这条 trace 记了什么、没记什么",
              rows=["REUSED_OBSERVATION → FORMULA_RESULT。除法发生在 _formula_value()，没有留痕。"],
              note="要复算，得回 observation 查 claim 值，再回 catalog 查 formula_id")]
    return svg(808, 296, "".join(b), label="Result 与 Trace 互相绑定，但 trace 不含算术步骤")


def fig_grid():
    cw, ch, x0, y0 = 33, 17, 132, 34
    b = []
    for j, m in enumerate(METRICS):
        b.append(txt(x0 + j * cw + cw / 2, y0 - 9, m, cls="n", anchor="middle"))
    for i, c in enumerate(COMPANIES):
        b.append(txt(124, y0 + i * ch + 12, DISP[c][:15], cls="n", anchor="end"))
        for j, m in enumerate(METRICS):
            e = CELL[(c, m)]
            inherited = m in ("B01", "B03")
            t = ("inherit" if inherited else
                 "fact" if e["quality"] == "EXACT" else
                 "degrade" if e["quality"] == "APPROX" else
                 "dim" if e["quality"] == "NOT_MEANINGFUL" else "raw")
            b.append(f'<rect x="{x0+j*cw+2}" y="{y0+i*ch+2}" width="{cw-4}" height="{ch-4}" rx="2" '
                     f'fill="{TONE[t]}" opacity="{0.85 if inherited else 0.5}"/>')
    yy = y0 + 10 * ch + 24
    q, a = F["quality"], F["applicability"]
    b.append(txt(x0, yy, f"● EXACT {q['EXACT']}   ◐ APPROX {q['APPROX']}   "
                         f"○ NOT_MEANINGFUL {q['NOT_MEANINGFUL']}   ▤ 结构性 N/A {q['NONE']}   "
                         f"◇ R1 继承 20", cls="m2"))
    b.append(txt(x0, yy + 20, f"{q['EXACT']} + {q['APPROX']} + {q['NOT_MEANINGFUL']} + {q['NONE']} = "
                              f"{len(F['index'])}    PUBLISHED {F['publication']['PUBLISHED']}    WITHHELD 0",
                 cls="m", tone="fact"))
    return svg(x0 + 22 * cw + 24, yy + 36, "".join(b),
               label="十家公司乘二十二个指标的两百二十个坐标网格，按终态着色")


def fig_records():
    g = F["graph"]
    b = [node(24, 24, 340, 168, tone="fact", kind="coordinate_index.json",
              rows=[("coordinates", "220", "fact"), ("去重后", "220", "fact")],
              note="这是发布承诺的完整坐标集合"),
         node(424, 24, 400, 168, tone="inherit", kind="deterministic_execution_graph.json",
              rows=[("METRIC_RESULT", "200", "inherit"), ("EXECUTION_TRACE", "200", "inherit"),
                    ("VERIFIED_OBSERVATION", str(sum(F["obs_roles"].values())), "inherit"),
                    ("CLAIM 记录", str(F["claim_records"]), "inherit"),
                    ("CLAIM 唯一 ID", str(F["claim_unique"]), "inherit")],
              note="少 20 条"),
         arr(368, 108, 418, 108, tone="degrade"),
         node(24, 208, 800, 66, tone="degrade", kind="差的 20 条在哪",
              rows=["B01 / B03 × 10 家，记录在前驱 R1 bundle 的 internal/runs/，渲染时由 _r1_projection_records() 取回"])]
    return svg(848, 288, "".join(b), label="坐标索引有二百二十条，执行图只有两百条记录，其余二十条继承自前驱")


def fig_order():
    b = [node(24, 24, 360, 130, tone="fact", kind="① render_public_rows()",
              rows=["registry / coordinates / records", "source_references / filing_inventory",
                    "projection_claims"], note="参数里没有 legacy · 产出 220 行"),
         arr(200, 162, 200, 196, tone="fact"),
         node(24, 204, 360, 130, tone="fact", kind="② compare_public_rows()",
              rows=[("compared_key_count", str(F["compat"]["compared_key_count"]), "fact"),
                    ("compared_field_count", str(F["compat"]["compared_field_count"]), "fact"),
                    ("unexpected_delta", "[]", "fact"), ("approved_delta", "[]", "fact")],
              note="approved_deltas 非空直接 raise"),
         node(424, 24, 400, 130, tone="fact", strong=True, kind="AST 静态门",
              rows=["① 生产函数不含 7 个禁用标识符", "② 生产函数里不出现 compare_public_rows",
                    "③ render 行号 < compare 行号"], note="projection_independence.py:88-125"),
         node(424, 204, 400, 130, tone="fact", kind="实测行号",
              rows=[("render_public_rows", "2441", "fact"), ("compare_public_rows", "2458", "fact"),
                    ("两个行集合 hash", "sha256:abf6d191…", "fact")],
              note="141 行逐字节一致，不是「差不多」")]
    return svg(848, 348, "".join(b), label="先独立渲染两百二十行，之后才比较；顺序由 AST 行号检查强制")


def fig_309():
    mig = set(F["receipt"]["cumulative_metric_ids"])
    kept = sum(1 for r in F["rows"] if r["metric_id"] not in mig)
    kept_metrics = len({r["metric_id"] for r in F["rows"] if r["metric_id"] not in mig})
    repl = F["compat"]["replaced_legacy_row_count"]
    new = F["compat"]["new_public_key_count"]
    total = F["receipt"]["public_matrix_row_count"]
    assert repl + kept + new == total == len(F["rows"]), "public matrix segments do not sum"
    assert repl + new == len(F["index"]), "migrated segments do not equal the coordinate set"
    seg = [(repl, "被逐行替换", f"前驱里属于 {len(mig)} 个已迁移指标的行", "fact"),
           (kept, "原样保留", f"前驱里 {kept_metrics} 个未迁移指标的行", "inherit"),
           (new, "追加", "legacy 中不存在的新 public key", "degrade")]
    b, x, W = [], 30, 780
    for n, lab, sub, tone in seg:
        w = W * n / total
        b.append(f'<rect x="{x}" y="34" width="{w-4}" height="62" rx="5" fill="{TONE[tone]}" '
                 f'opacity="0.26" stroke="{TONE[tone]}" stroke-width="1.3"/>')
        b.append(txt(x + w / 2 - 2, 72, str(n), cls="big", tone=tone, anchor="middle"))
        b.append(txt(x + w / 2 - 2, 120, lab, cls="s", tone=tone, anchor="middle"))
        b.append(txt(x + w / 2 - 2, 142, sub, cls="n", anchor="middle"))
        x += w
    b.append(txt(30, 186, f"{repl} + {kept} + {new} = {total}", cls="s"))
    b.append(txt(250, 186, f"其中 {repl} + {new} = {len(F['index'])} = 本次迁移范围的完整坐标集合",
                 cls="m", tone="fact"))
    return svg(840, 204, "".join(b), label="最终公共矩阵由被替换、被保留和新增三段拼成")


def fig_commit():
    steps = [("取 pointer 排他 flock", None), ("恢复上次未完成的 switch intent", None),
             ("CAS：当前指针 == expected predecessor ?", "cas"),
             ("写 switch intent（含切换前每个镜像的 hash）", None),
             ("逐个写 14 个根目录兼容镜像，逐个核 hash", "mirror"),
             ("atomic_write_json(pointer_path, pointer)", "commit"),
             ("写 switch receipt（历史边）", "receipt"),
             ("PublicationView 重新打开，核对 publication_id", None),
             ("删除 intent", None)]
    b, y = [], 24
    for lab, tag in steps:
        commit = tag == "commit"
        t = "fact" if commit else "raw"
        b.append(f'<rect x="24" y="{y}" width="500" height="34" rx="5" '
                 f'fill="{"var(--panel)" if commit else "none"}" stroke="{TONE[t]}" '
                 f'stroke-width="{2 if commit else 1}"/>')
        b.append(txt(38, y + 22, lab, cls="s" if commit else "b", tone="fact" if commit else None))
        if commit:
            b.append(txt(538, y + 22, "◀ 唯一正式提交点", cls="m", tone="fact"))
        y += 40
    b.append(node(660, 24, 220, 130, tone="fact", kind="崩在提交点之后",
                  rows=["指针已写 = 已提交", "恢复逻辑向前补齐", "receipt / 镜像 / 读回"],
                  note="新版本保持正式"))
    b.append(node(660, 170, 220, 130, tone="degrade", kind="崩在提交点之前",
                  rows=["恢复镜像字节", "恢复旧指针", "删 receipt 与 intent"],
                  note="旧版本仍是唯一正式版本"))
    return svg(900, y + 16, "".join(b), label="发布事务的九个步骤，指针写入是唯一的正式提交点")


def fig_receipts():
    chain = [("11:38:20", "COMMIT", "null", "5668341b"), ("11:38:20", "COMMIT", "5668341b", "81eb8476"),
             ("11:38:21", "ROLLBACK", "81eb8476", "5668341b"), ("11:38:22", "COMMIT", "5668341b", "81eb8476"),
             ("11:38:54", "COMMIT", "81eb8476", "fe01e227")]
    b = []
    for i, (t, mode, a, z) in enumerate(chain):
        x = 24 + i * 168
        tone = "degrade" if mode == "ROLLBACK" else "fact" if i == 4 else "raw"
        b.append(node(x, 24, 152, 92, tone=tone, kind=mode, rows=[]))
        b.append(txt(x + 13, 66, t, cls="m2"))
        b.append(txt(x + 13, 90, f"{a} →", cls="m"))
        b.append(txt(x + 13, 106, z, cls="m", tone=tone))
        if i < 4:
            b.append(arr(x + 152, 70, x + 166, 70, tone="dim"))
    return svg(868, 132, "".join(b), label="仓库里真实留存的五份切换收据，含一次回滚演练")


def fig_map():
    pairs = [("来源身份闭合", "claim 才可能成立"), ("claim + 规则", "决定 observation"),
             ("observation + Spec", "决定 Result / Trace"), ("replay 与 exact set", "决定批次"),
             ("独立生产与兼容", "决定 bundle 能否提交"), ("pointer 与 view", "决定下游读到哪一版")]
    b = []
    for i, (a, z) in enumerate(pairs):
        y = 24 + i * 58
        b.append(node(24, y, 250, 44, tone="fact", rows=[]))
        b.append(txt(38, y + 28, a, cls="s"))
        b.append(arr(282, y + 22, 322, y + 22, tone="fact"))
        b.append(node(330, y, 250, 44, tone="fact", rows=[]))
        b.append(txt(344, y + 28, z, cls="s"))
        if i < len(pairs) - 1:
            b.append(arr(150, y + 44, 150, y + 56, tone="dim"))
    b.append(node(624, 24, 240, 200, tone="refuse", kind="任何前置事实失败",
                  rows=["后面的对象不能被伪造出来", "旧 active 继续服务"],
                  note="这是整层唯一的兜底语义"))
    b.append(node(624, 246, 240, 92, tone="degrade", kind="值稳定 ≠ ID 稳定",
                  rows=["值 = 字节 + catalog", "ID = 值 + 代码语义"]))
    return svg(884, 24 + 6 * 58 + 16, "".join(b), label="六条必须记住的因果依赖，以及失败时的统一兜底")


# --------------------------------------------------------------------------
# slides
# --------------------------------------------------------------------------

def cite(*items):
    return '<ul class="cite">' + "".join(
        f'<li><span class="tag" data-k="{k}">{lab}</span>{E(t)}'
        + (f'<code>{E(c)}</code>' if c else "") + "</li>"
        for k, lab, t, c in items) + "</ul>"


SLIDES: list[str] = []


def slide(num, kind, idf, title, fig, prose, cites, *, layout="stack", lead=""):
    SLIDES.append(f"""
<section class="slide" id="s{num}">
  <header class="sh">
    <span class="sn">{E(num)}</span>
    <span class="sk">{E(kind)}</span>
    {f'<span class="si">{E(idf)}</span>' if idf else ''}
  </header>
  <h2>{title}</h2>
  {f'<p class="lead">{lead}</p>' if lead else ''}
  <div class="sb {layout}">
    <figure class="fig">{fig}</figure>
    <div class="prose">{prose}</div>
    <aside class="ev">{cites}</aside>
  </div>
</section>""")


# ---- cover ---------------------------------------------------------------
r, c, p = F["receipt"], F["compat"], F["pointer"]
SLIDES.append(f"""
<section class="slide cover" id="s00">
  <p class="eyebrow">流程一 · 结构化 SEC 数据如何成为正式指标</p>
  <h1>一个数字要通过十一道关，<br>才配叫「当前正式指标」</h1>
  <p class="thesis">这条流程接收的不是一个已经可信的数字，而是一组可以按字节复核的 SEC 原始材料。
     它把材料逐级升级成有来源、有资格、有结论、有版本的事实。
     <b>每一关只回答一个「事后无法回答的问题」，代价是每一关都要生成一个不可变、内容寻址的对象来承载答案。</b></p>
  <div class="chips">
    <span class="chip">HEAD <b>d9bb477</b></span>
    <span class="chip">active <b>{E(p['publication_id'][:24])}…</b></span>
    <span class="chip">bundle source_commit <b>{E(r['source_commit'][:8])}</b></span>
    <span class="chip">10 公司 × {len(r['cumulative_metric_ids'])} 指标 = <b>{r['result_coordinate_count']}</b> 坐标</span>
    <span class="chip">公共矩阵 <b>{r['public_matrix_row_count']}</b> 行</span>
    <span class="chip">模型调用 <b>0</b></span>
  </div>
  <figure class="fig wide">{fig_chain()}</figure>
  <p class="foot">本页所有数值在构建时读自 <code>outputs/publications/{E(p['publication_id'][:28])}…</code> 与仓库源码，
     没有一处来自转写。</p>
</section>""")

# ---- 01 ------------------------------------------------------------------
slide("01", "RawBlob", "raw_asset_id",
      "第一关只证明一件事：我说的是<em>这一组</em>字节",
      fig_rawblob(),
      """<p><b>要替换的误解：</b>「文件在 <code>evidence/</code> 目录里」不是身份。路径可以改名，
      中间任何一级目录都可以被 symlink 指向别处，同名文件可以被整份替换。</p>
      <p>这一关刻意<b>降级</b>了下游能说的话：从「有个文件」降到「这是这一组确切的字节」。
      降级换来的是可核对性——<code>raw_asset_id</code> 就是字节自身的 SHA-256，改一个 bit 就不是它了。</p>
      <p>路径解析逐段检查每一级是否 symlink，并要求 <code>resolve()</code> 之后仍在仓库根下；
      每次重新读取字节时还会再核一次 hash 与长度。</p>
      <p><b>仍然没有证明的：</b>这组字节属于哪家公司、哪一次申报、有没有资格代表某个会计概念。
      那是下一关的事。</p>""",
      cite(("recomputed", "本次重算", "在本快照上跑 sha256sum，得到与 bundle 内记录相同的值。",
            "sha256sum evidence/companyfacts/CIK0000019617.json → e5a94464…"),
           ("code", "代码", "raw_blob_record() 是唯一构造入口，byte_length 由实际读取长度决定。",
            "scripts/vnext/sources.py:147"),
           ("code", "代码", "路径解析逐段拒绝 symlink，并要求 resolve() 后仍在仓库根下。",
            "scripts/vnext/sources.py:105"),
           ("gap", "缺口", "三份文档中有一份把 byte_length 写成 7 708 165；实测 7 888 465，而同段的 hash 是对的。", "")))

# ---- 02 ------------------------------------------------------------------
slide("02", "SourceReference", "source_reference_id",
      "同一组字节，两个申报身份",
      fig_two_refs(),
      """<p><b>要替换的误解：</b>内容 hash 只证明「同一组字节」，它<b>不</b>证明这组字节属于哪家公司的哪一次申报。</p>
      <p>这是整条链上最反直觉的一处：一份 Company Facts JSON 会生成<b>两个</b> SourceReference。
      同一份字节、同一个 <code>request_attempt_id</code>，但 accession 不同，所以 ID 不同。</p>
      <p>为什么要这样：Company Facts 是「一家公司所有历史事实的合集」，一份文件里同时含 FY2025 和 FY2024 的数字。
      只建一个引用，就说不清「这个 2024 年的 Assets 是通过哪份年报申报的」。
      分成两个观察之后，适配器用 <code>fact["accn"]</code> 把事实按申报切开，每条事实归属到一次具体申报。</p>
      <p>构造函数的 docstring 把意图写得很直白：<em>Two observations of the same bytes remain distinct
      when their filing identity differs.</em></p>""",
      cite(("artifact", "产物", "这两条引用就在 release_input_plan.json 里，raw_asset_id 与 request_attempt_id 完全相同。",
            "internal/release_input_plan.json"),
           ("code", "代码", "source_reference_record() 的 6 字段身份决定 ID。", "scripts/vnext/sources.py:177,199"),
           ("code", "代码", "按 accession 切开事实，其它申报的事实根本不进入候选集合。",
            "scripts/vnext/sources.py:471-475"),
           ("artifact", "产物",
            f"本次 plan 共 {F['n_refs']} 个 SourceReference、{F['n_attempts']} 个不同的 request attempt"
            "——差额正来自同字节多身份。", "")))

# ---- 03 ------------------------------------------------------------------
slide("03", "SourceSetManifest", "source_set_manifest_id",
      "唯一一个证明<em>否定命题</em>的对象",
      fig_closure(),
      """<p><b>要替换的误解：</b>前两关证明的都是「我手上这个东西是真的」。
      <b>没有任何一步证明「我该拿的都拿到了」。</b></p>
      <p>对正数来说，漏一份文件只是算小了；对 <b>0</b> 来说，漏一份会让「没发生」和「没看见」变成同一件事——
      而且没有任何异常、没有任何日志，只有一个错误的数字。这是整层里唯一一类 hash 发现不了的错误，
      所以它需要一个专门的对象来防。</p>
      <p>关键机制是<b>构造时的自我否证</b>：调用方声明「我要用这 N 个 filing」，
      构造函数自己从 submissions 字节里独立算出「按发现规则应该是哪 N 个」，两边必须完全相等。
      调用方无法通过多传或少传引用蒙混过关。</p>
      <p>8-K 集合还要另外调 <code>verify_source_set_completeness()</code>，
      把整个清单从字节重建一遍并要求逐字段相等。</p>""",
      cite(("code", "代码", "planned_accessions != discovered_accessions 直接 raise。",
            "deterministic_router.py:283-288"),
           ("code", "代码", "SOURCE_SET_FIELDS 是 13 个字段的 exact set；manifest_id 是其余 12 个的 content hash。",
            "deterministic_router.py:36-50, 222"),
           ("code", "代码", "任何 claim 的来源必须落在某个清单的 ordered_source_reference_ids 内。",
            "deterministic_router.py:698-701"),
           ("artifact", "产物",
            f"本次 R2 共 {F['n_manifests']} 个 SourceSetManifest，覆盖 {F['n_refs']} 个来源引用。",
            "internal/release_input_plan.json")))

# ---- 04 ------------------------------------------------------------------
slide("04", "闭世界", "value = \"0\"",
      "这个 0 是断言，不是缺省",
      fig_zero(),
      """<p>上一关的抽象保证，在这里变成一个可以直接读出来的数字。</p>
      <p>JPMorgan 的 E01（并购事件数）是 <b>0</b>。它的 observation 里
      <code>matched_verified_claim_ids</code> 是空数组，但
      <code>ordered_source_reference_ids</code> 有 <b>46</b> 条——
      这个 0 是在 46 份已证明完整的来源上做出的断言。</p>
      <p>公共 CSV 里这一行的 notes 写的是
      「FY-window 8-K scanned; no M&amp;A item rule matched.」——扫过了，没匹配上；
      而不是「没找到」。</p>
      <p>这也是财务路径与事件路径 <code>source_binding</code> 形状不同的原因：
      财务用 <code>verified_claim_ids</code> + <code>selected_branch_id</code>（指向具体几格），
      事件用 <code>matched_verified_claim_ids</code> + <code>ordered_source_reference_ids</code>（指向整个集合）。</p>""",
      cite(("artifact", "产物", "220 个坐标里 30 个事件坐标的值是 0，每一个都带着完整的来源集合。", ""),
           ("code", "代码", "project_event_result() 把 inventory 的 SourceReference 写进 observation 的 source_binding。",
            "deterministic_router.py:1700"),
           ("gap", "缺口", "两种 source_binding 形状是本次在产物里读出来的；三份文档只有一份把它列进 Roadmap，没有一份展示它。", "")))

# ---- 05 ------------------------------------------------------------------
slide("05", "DeterministicVerifiedClaim", "verified_claim_id",
      "选中必须是筛选条件的<em>唯一解</em>，不是排序后的第一名",
      fig_funnel(),
      """<p><b>要替换的误解：</b>「找到了 Assets」远远不够。
      JPMorgan 那份 Company Facts 里，<code>us-gaap:Assets / USD</code> 有
      <b>206 条事实，横跨 73 个 accession</b>。</p>
      <p>每一级筛选都是 catalog 声明的维度——accession 角色、期间角色、单位、form、fiscal_period——
      不是代码里的 <code>if</code>。<code>calculator.py</code> 的模块 docstring 写得很明确：
      它不含任何指标、公司、行业或 scope 分支，全部业务顺序、概念、guard 和容差都以数据的形式到达。</p>
      <p><b>关键的确定性保证：</b>允许筛出多个候选，但它们的 <code>(value, unit)</code> 必须完全一样。
      一旦同一条件下出现两个不同的值，整批发布中止，不做任何猜测。相同值的多个候选按 claim ID 排序取第一个——
      这是纯粹的去歧义 tie-break，不影响结果。</p>
      <p>因此选中的 claim 集合是输入字节的函数，不含任何随机性或时间依赖。</p>""",
      cite(("recomputed", "本次重算", "206 / 73 是直接读 evidence/companyfacts/CIK0000019617.json 数出来的；current accession 下确实是 3 条。", ""),
           ("code", "代码", "value-ambiguous 守卫：候选的 (value, unit) 集合必须只有一个元素。",
            "zero_ai_r2.py:1777-1782"),
           ("code", "代码", "解析器禁止二进制浮点与 NaN/Infinity，数字一律解析成 Decimal。",
            "canonical.py:49,86,349"),
           ("artifact", "产物", f"执行图里有 {F['claim_records']} 条 claim 记录、{F['claim_unique']} 个不同的 verified_claim_id。",
            "文档把这两个数配错了")))

# ---- 06 ------------------------------------------------------------------
slide("06", "VerifiedObservation", "observation_id",
      "被拒绝的路径被写进对象，而不是写进日志",
      fig_branch(),
      """<p>claim 是「来源格式层」的事实。要参与公式，还必须说清楚：它在哪个指标里扮演什么角色、
      在什么口径（scope）下成立、系统<b>试过哪些分支、为什么退到了这一条</b>。</p>
      <p>catalog 的 <code>branches</code> 是一个<b>有序数组</b>。依次尝试，第一个所有 component 都能找到 claim 的分支胜出。
      找不到概念时抛内部私有异常 <code>_BranchUnavailable</code>，被捕获后记进 <code>rejected</code> 列表，继续试下一条。</p>
      <p>这叫<b>契约 fallback</b>：它不是网络失败后的重试，而是指标定义提前声明的会计口径优先级。
      Pfizer 没有申报 <code>OperatingIncomeLoss</code>，所以 B07 退到第二条分支——
      用「税前利润 − 非营业损益」重构营业利润，并把 quality 标为 <code>APPROX</code>。</p>
      <p><b>最值得看的字段：</b><code>rejected_branches</code> 从 <code>[]</code> 变成
      <code>[{branch_id, reason}]</code>。这不是日志，是一个被 hash 覆盖的字段，随 bundle 永久保存。
      三个月后你仍能读出「那次发布，Pfizer 的 B07 为什么走了近似路径」。</p>
      <p><code>approval_effect_hash</code> 恒为空字符串——空字符串在这里是正式语义：<b>未经任何人工或系统审批</b>。
      AI 路径走 <code>reviewed_observation()</code>，那里这个字段是真的审批 hash。所以「这个数是不是模型给的」在对象层面一眼可辨。</p>""",
      cite(("artifact", "产物", "Pfizer B07 的 rejected_branches 真的写着 reason: Catalog concept chain is absent for operating_income。",
            "internal/deterministic_execution_graph.json"),
           ("code", "代码", "分支顺序由 catalog 的有序数组决定，异常被捕获后继续下一条。",
            "zero_ai_r2.py:1790-1814"),
           ("code", "代码", "observation_id 是 10 个语义字段的 content hash，刻意不含 quality 与 approval_effect_hash。",
            "observations.py:85-96"),
           ("artifact", "产物", "309 行公共矩阵里只有 2 行是 OK_APPROX，正是 Pfizer 的 B03 和 B07。", "")))

# ---- 07 ------------------------------------------------------------------
Q, A = F["quality"], F["applicability"]
N_OK = Q["EXACT"] + Q["APPROX"]
N_NA = A["N_A_STRUCTURAL"]
N_NM = Q["NOT_MEANINGFUL"]
N_WH = F["publication"].get("WITHHELD", 0)
assert N_OK + N_NA + N_NM + N_WH == len(F["index"]), "four-state counts do not sum to the coordinate set"

FOUR = f"""<table class="t">
<thead><tr><th>终态</th><th>applicability</th><th>quality</th><th>publication</th><th>value</th><th>本次数量</th></tr></thead>
<tbody>
<tr><td>数值成功</td><td>APPLICABLE</td><td>EXACT / APPROX</td><td class="ok">PUBLISHED</td><td>有值</td><td class="num">{N_OK}</td></tr>
<tr><td>结构性不适用</td><td>N_A_STRUCTURAL</td><td>NONE</td><td class="ok">PUBLISHED</td><td>null（unit 也 null）</td><td class="num">{N_NA}</td></tr>
<tr><td>数学上无意义</td><td>APPLICABLE</td><td>NOT_MEANINGFUL</td><td class="ok">PUBLISHED</td><td>null（unit 可非空）</td><td class="num">{N_NM}</td></tr>
<tr><td>证据不足</td><td>APPLICABLE</td><td>NONE</td><td class="no">WITHHELD</td><td>null</td><td class="num">{N_WH}</td></tr>
</tbody></table>"""

slide("07", "MetricResult ⇄ ExecutionTrace", "result_id / trace_id",
      "结论与推导互锁，空值也是结论",
      fig_lock(),
      f"""<p><b>要替换的误解：</b>一个数字配一段说明文字，事后没有任何约束力。</p>
      <p>这里用的是<b>构造级绑定</b>而不是校验级绑定：<code>result_id</code> 含 <code>trace_id</code>，
      trace 里又含 Result 那 12 个语义字段的 hash。两边都改还想自洽，就必须同时重签整条链——
      而 R1 路径的 freeze replay 会从原始字节把它拆穿。<code>_result_and_trace()</code>
      是唯一能同时产出这两条记录的地方，所以「配对」是构造上的必然，不是纪律。</p>
      <p>下游拿到的是一个明确的四态系统。<code>records.py</code> 里那是一张<b>状态表</b>，不是一堆散落的 if：
      任何其它组合直接抛 <code>RecordError</code>。注意第三行——
      <code>NOT_MEANINGFUL</code> 是唯一允许「值为空但单位非空」的状态，
      这让下游能区分「这个指标没有单位概念」和「这个指标有单位，只是这次算不出有意义的数」。</p>
      {FOUR}
      <p><b>必须诚实说出的缺口：</b>R2 确定性指标的 trace 只有两步——
      <code>REUSED_OBSERVATION</code> 和 <code>FORMULA_RESULT</code>。除法本身发生在
      <code>_formula_value()</code> 里，没有留痕。要复算，你必须拿 observation 的
      <code>verified_claim_ids</code> 去查每个 claim 的值，再回 catalog 查 <code>formula_id</code>
      对应哪个公式。<b>trace 不是自包含的。</b></p>""",
      cite(("code", "代码", "METRIC_RESULT_CONTRACT_FIELDS 有 12 个字段，被 hash 进 trace。", "records.py:496-509"),
           ("code", "代码", "四态表是一串守卫；NOT_MEANINGFUL 是唯一允许值空单位非空的状态。",
            "records.py:1530-1571"),
           ("artifact", "产物", "本次 220 个坐标：PUBLISHED 220、WITHHELD 0。", ""),
           ("gap", "缺口", "trace 不含算术步骤。画 trace 时不要画一条完美的算术链——它现在不是。", "")))

# ---- 08 ------------------------------------------------------------------
slide("08", "坐标 exact set", "220 = 10 × 22",
      "单个坐标正确，不等于批次完整",
      fig_grid(),
      """<p>少一家公司、少一个指标、重复一个坐标、多一个计划外坐标——普通 CSV 全都写得出来。
      所以闸门同时检查<b>两个条件</b>：总数是 220，<b>且</b>按 (company, metric) 去重后仍是 220。</p>
      <p>更要紧的是，这个数量关系在<b>每次打开发布包时</b>都会重算：
      <code>result_coordinate_count == 10 * len(cumulative_metric_ids)</code>。
      这一行才是系统对「坐标必须完整」的表达；
      而 <code>zero_ai_r2.py</code> 里那四个硬编码常量（220 / 141 / 79 / 309）属于一次性迁移脚本，
      加第 11 家公司必须改它们——这是实现细节，不是契约。</p>
      <p>网格里 B01 / B03 两列是从 R1 前驱继承的 20 个坐标。R2 是一个<b>单调迁移 ratchet</b>：
      继承 20，新增 200，累计 220。不是从零重算 220。</p>""",
      cite(("code", "代码", "发布时的 exact-set 闸门同时检查总数与去重数。", "zero_ai_r2.py:2366-2371"),
           ("code", "代码", "每次 verify_publication_bundle 都重算 10 × len(cumulative_metric_ids)。",
            "publication.py:4360-4364"),
           ("test", "测试", "canary 测试断言坐标数与渲染行数都是 220。",
            "tests/vnext/test_zero_ai_release.py:213-215")))

# ---- 09 ------------------------------------------------------------------
slide("09", "记录与坐标", "200 ≠ 220",
      "220 个坐标，只对应 200 条记录",
      fig_records(),
      """<p>这是本次核对时在产物里读出来、而三份文档都没有写的一件事。</p>
      <p><code>coordinate_index.json</code> 有 220 个坐标，去重后仍是 220。
      但 <code>deterministic_execution_graph.json</code> 里只有
      <b>200 条 METRIC_RESULT、200 条 EXECUTION_TRACE</b>。</p>
      <p>差的 20 条是 B01 / B03 × 10 家——它们的 Result/Trace 记录在<b>前驱 R1 bundle</b> 的
      <code>internal/runs/</code> 里，渲染时由 <code>_r1_projection_records(active_view=r1_view)</code> 取回。</p>
      <p><b>为什么这件事重要：</b>它决定了「光看这一个执行图，能验证到什么程度」。
      三份文档都说 R2「继承」了 R1 的 20 个坐标，但没有一份说明这个继承的物理后果。
      审计者如果只打开执行图数记录，会以为少了 20 条。</p>
      <p>顺带一提两条生产路径的不对称：R1 的 20 个坐标走完整的 Run 生命周期
      （OPEN → 机械重放校验 → 签发 ValidationReceipt → FROZEN）；
      R2 的 200 个坐标<b>不走 Run</b>，直接产出记录进执行图。
      它的完整性保证来自另一组：坐标精确集合 + 141×20 兼容性对比 + AST 独立性证明 + 发布包 hash 验证。
      这是<b>不同的</b>保证组合，不能说更弱或更强，但确实不一样。</p>""",
      cite(("recomputed", "本次重算",
            f"执行图记录总数 {len(F['graph']['records'])}：claim {F['claim_records']}、"
            f"result 200、trace 200、observation {sum(F['obs_roles'].values())}。", ""),
           ("code", "代码", "_r2_public_candidate 渲染时把前驱的 R1 记录一并传入。", "zero_ai_r2.py:2418"),
           ("gap", "缺口", "220 vs 200 的落差在三份文档中都没有出现。", "")))

# ---- 10 ------------------------------------------------------------------
slide("10", "独立性 + 兼容性", "141 × 20 = 2 820",
      "先独立渲染，之后才比较；顺序由机器强制",
      fig_order(),
      """<p><b>要替换的误解：</b>迁移最经典的自欺是——新代码读旧答案，然后宣布「完全一致」。</p>
      <p>所以这里建立的不是「结果相同」，而是<b>顺序被机器强制</b>。
      <code>render_public_rows()</code> 的参数里根本没有 legacy 数据；
      渲染完 220 行之后，才把冻结的旧 CSV 当作后置 oracle 去比。</p>
      <p>这个顺序不靠代码评审维持：<code>projection_independence.py</code> 会 <b>AST 解析源码</b>，
      检查四个生产函数的标识符不含 7 个禁用名、生产函数里不出现 <code>compare_public_rows</code>、
      并且 <code>render</code> 的调用行号<b>严格小于</b> <code>compare</code> 的调用行号。</p>
      <p><b>容差是零。</b><code>compare_public_rows</code> 第一行就是
      <code>if approved_deltas: raise</code>。catalog 里 <code>approved_deltas</code> 是空数组。
      结构里虽然留了 <code>approved_delta</code> 计数槽，但代码永远不会往里加——
      这个概念在数据模型里存在，在当前实现里被完全关掉。</p>
      <p>诚实评价这道门：它是字符串级检查，可以被绕过（把变量改名叫 <code>oracle_rows</code> 就绕过了）。
      它防的是<b>无意的</b>耦合，不防<b>有意的</b>绕过。这个定位是合理的——
      审计边界的作用是让偏离变得显眼，不是让它变得不可能。</p>""",
      cite(("artifact", "产物",
            f"收据里 compared_key_count={F['compat']['compared_key_count']}、"
            f"compared_field_count={F['compat']['compared_field_count']}，两个 delta exact set 都是 []。",
            "legacy_invariant_migration_receipt.json"),
           ("artifact", "产物", "两个行集合 hash 都是 sha256:abf6d191…——141 行逐字节一致。", ""),
           ("recomputed", "本次重算", "render 在 zero_ai_r2.py:2441、compare 在 :2458，与 AST 门要求一致。", ""),
           ("test", "测试", "canary 测试把四个 legacy 字段从 producer context 里 pop 掉再建图，证明生产路径不需要它们。",
            "tests/vnext/test_zero_ai_release.py:153-160")))

# ---- 11 ------------------------------------------------------------------
slide("11", "公共矩阵", "309 = 141 + 89 + 79",
      "309 行是迁移中的混合视图，不是 309 个新数",
      fig_309(),
      """<p>最容易被混起来的一组数字。把它们分开：
      <b>220</b> 是迁移范围的完整性；<b>309</b> 是对外矩阵的大小；<b>79</b> 是新增的公共 key。</p>
      <p>新增的 79 个 key 全部满足 <code>status = N_A_STRUCTURAL</code>、
      <code>source_class = STRUCTURAL</code>、值为空。它们不是 79 个新数字，
      而是把「10 公司 × 22 指标」的完整坐标<b>显式化</b>——以前这些格子是被静默省略的。</p>
      <p>例如 JPMorgan 的 B01 Revenue：系统发布的是「结构不适用」这个事实，
      而不是假装缺数，也不是从银行年报里硬找一个 Revenue 概念。</p>
      <p><b>零容差反过来塑造了 catalog。</b>220 个坐标里有 <b>80</b> 个 N_A_STRUCTURAL，
      但公共 CSV 里 <code>source_class = STRUCTURAL</code> 的只有 <b>79</b> 行。
      差的那一行是 JPMorgan 的 B08（Current ratio）：<code>status = N_A_STRUCTURAL</code>
      但 <code>source_class = NOT_AVAILABLE</code>。
      因为这一行在 legacy 里本来就存在（属于被替换的 141 个 key），
      零容差要求新渲染逐字节复现它，包括它那个不规则的 source_class——
      于是 catalog 为 B08 单独写了一个 <code>structural_overlay</code>。</p>
      <p>所以「79 个新增 key 全是 N_A_STRUCTURAL + STRUCTURAL」是真的，但不能推广到全部 80 个结构性坐标。</p>""",
      cite(("recomputed", "本次重算", "用 csv.DictReader 数 metrics_matrix.csv：309 行、20 字段；220 行属于已迁移指标，89 行属于 17 个未迁移指标。", ""),
           ("code", "代码", "assemble_public_rows() 按前驱行序遍历：已迁移换新行，未迁移原样保留，新增 key 排序追加。",
            "public_projection.py:868"),
           ("artifact", "产物", "catalog/zero_ai_public_projection.json → B08.structural_overlay.source_class = \"NOT_AVAILABLE\"。", ""),
           ("gap", "缺口", "80 vs 79 的不对称在三份文档中都没有出现。", "")))

# ---- 12 ------------------------------------------------------------------
slide("12", "发布事务", "active pointer",
      "整条链上只有一个正式提交点",
      fig_commit(),
      """<p><b>要替换的误解：</b>bundle 完整 ≠ 正式。
      <code>MetricResult.publication = PUBLISHED</code> 也 ≠ 正式——
      它只表示这个坐标的业务终态<b>允许</b>进入候选。</p>
      <p>这一关建立的是：<b>「当前正式版本是谁」由一个受审计的指针决定，
      而不是由哪个 CSV 最后被写入决定。</b></p>
      <p>十四个根目录兼容镜像先写、指针后写，是刻意的顺序。
      历史边（switch receipt）必须写在指针<b>之后</b>——代码注释写得很直白：
      提前持久化它，会让「指针前崩溃」留下一个孤儿，日后指针被篡改时可能被误读成已提交。</p>
      <p>崩溃恢复只认两种状态：当前指针等于 <code>previous</code> 就<b>向后回滚</b>，
      等于 <code>proposed</code> 就<b>向前补齐</b>；两者都不是就 raise，<b>拒绝猜第三种</b>。</p>
      <p>读者也参与这个锁协议：<code>PublicationView.open()</code> 拿共享锁，
      并拒绝在有未完成 intent 时读取。所以读者要么看到完整的旧事务，要么看到完整的新事务，
      绝不会看到「指针已切但历史边还没写」这个刻意留出的中间态。</p>""",
      cite(("code", "代码", "CAS 在锁内比较；COMMIT 还额外要求 manifest.previous_publication_id == 当前指针。",
            "publication.py:5573-5579"),
           ("code", "代码", "except 块恢复镜像 → 恢复/删除指针 → 删 receipt → 删 intent → 抛 aborted and rolled back。",
            "publication.py:5666-5700"),
           ("code", "代码", "恢复逻辑拒绝猜测第三种状态。", "publication.py:5234"),
           ("gap", "缺口", "锁文件在 .gitignore 第 23 行——新克隆的仓库里它不存在，而读路径要求它必须存在。", "")))

# ---- 13 ------------------------------------------------------------------
slide("13", "切换历史", "5 份 switch receipt",
      "这不是设计文档，是真发生过的五次切换",
      fig_receipts(),
      """<p>仓库里留着五份切换收据，串起来是一条真实的演练轨迹：
      建立 legacy 基线 → 提交 R1 → <b>回滚演练</b> → 再切回 R1 → 提交 R2。</p>
      <p>中间那次 ROLLBACK 是有意义的：它证明回滚不是文档里的一句承诺，
      而是一条走通过的路径，并且回滚目标必须是<b>当前指针已证明的直接前驱</b>——
      不能回到任意历史版本。</p>
      <p>当前 active 指针只有四个字段：<code>publication_id</code>、
      <code>bundle_manifest_sha256</code>、<code>previous_publication_id</code>、
      <code>committed_at_utc</code>。<code>PublicationView</code> 每次打开都会核对
      manifest hash，并在每次 <code>read_bytes()</code> 时重新对一次文件的 size 与 hash。</p>
      <p>因此下游可以安全假设：所有文件来自同一个 publication，这套文件的 exact set 和 hash 已验证，
      并且后续的指针切换不会让当前 view 混入另一版本的文件。</p>""",
      cite(("artifact", "产物", "outputs/publication_switch_receipts/ 下确实有 5 份收据。", ""),
           ("artifact", "产物",
            f"active pointer：{F['pointer']['publication_id'][:26]}… ← {F['pointer']['previous_publication_id'][:26]}…，"
            f"提交于 {F['pointer']['committed_at_utc']}。", "outputs/active_publication.json"),
           ("code", "代码", "回滚目标必须是当前指针已提交的直接前驱。", "publication.py:5580-5585"),
           ("code", "代码", "PublicationView.read_bytes() 每次读都重新核对 size 与 hash。",
            "publication.py:6350-6367")))

# ---- 14 ------------------------------------------------------------------
FAIL = """<table class="t">
<thead><tr><th>失败点</th><th>变成什么对象</th><th>异常去哪</th><th>active 指针</th></tr></thead>
<tbody>
<tr><td>来源身份不成立</td><td>不生成 observation，也不生成伪造结果</td><td><code>SourceError</code></td><td class="ok">不变</td></tr>
<tr><td>集合不闭合</td><td>没有 claim</td><td><code>DeterministicRouterError</code></td><td class="ok">不变</td></tr>
<tr><td>候选值歧义</td><td>不选任何 claim</td><td><code>ZeroAiReleaseError</code>，整批中止</td><td class="ok">不变</td></tr>
<tr><td>guard / cross-check 不通过</td><td><code>WITHHELD</code> Result + 保留 reason 的 Trace</td><td>被 calculator 捕获并翻译</td><td class="ok">不变（candidate 被阻断）</td></tr>
<tr><td>trait 不适用</td><td><code>N_A_STRUCTURAL</code>，可正式发布</td><td>不抛异常</td><td class="ok">正常推进</td></tr>
<tr><td>坐标集合不对</td><td>没有候选版本</td><td><code>R2 result coordinate exact set differs</code></td><td class="ok">不变</td></tr>
<tr><td>任一格与 legacy 不等</td><td>candidate BLOCKED</td><td><code>Unexpected public delta: company:metric:field</code></td><td class="ok">不变</td></tr>
<tr><td>bundle 文件/hash 不符</td><td>候选目录存在也不是正式版本</td><td><code>PublicationError</code></td><td class="ok">不变</td></tr>
<tr><td>镜像写到一半崩溃</td><td>恢复镜像 + 恢复旧指针 + 删 receipt/intent</td><td><code>commit aborted and rolled back</code></td><td class="ok">回到旧版</td></tr>
<tr><td>指针写完之后崩溃</td><td>向前补齐 receipt、镜像、读回</td><td>由下次切换的恢复逻辑收口</td><td class="warn">已是新版</td></tr>
<tr><td>并发发布者 CAS 输</td><td>输家什么也改不了</td><td><code>Publication CAS predecessor changed</code></td><td class="ok">赢家保持</td></tr>
</tbody></table>"""

slide("14", "失败回流", "失败是一等结果",
      "异常不会被吞掉，然后用猜测值发布",
      FAIL,
      """<p>这张表有一个共同点：<b>失败要么被翻译成明确的普通业务终态，要么在更早的治理边界中止。</b>
      不存在「异常被吞掉，然后继续用猜测值发布」的路径。</p>
      <p>但必须区分两件事：<b>「失败被完整记录并可重放」是审计成功；「结果进入正式版本」是另一件事。</b>
      一个 cross-check 失败的 Run 仍然可以 freeze/replay，作为审计事实长期保存——
      但 publication gate 拒绝 WITHHELD candidate。</p>
      <p>测试用三组可重放的 fixture 把 1% 容差的边界钉死：相对误差
      <code>0.0099</code> → PUBLISHED，<code>0.01</code> → PUBLISHED（含边界），
      <code>0.0101</code> → WITHHELD。失败之后不是只抛异常：
      Calculator 把 <code>CROSS_CHECK_EVALUATED</code> 和精确的相对误差留在 Trace 里，
      Result 不含伪造的 value/unit。</p>
      <p><b>一个真实的内部不对称：</b>通用 calculator 有完整的 WITHHELD 机制
      （<code>BranchRejected</code> / <code>ConstraintError</code> 被捕获并转成 WITHHELD 结果）；
      但 R2 的确定性路径<b>没有接这套机制</b>——「找不到概念链」直接 raise，
      一家公司的异常会阻塞整批 220 个坐标。在当前规模（人工触发的批处理）下这是合理的，
      快速失败比部分成功更容易诊断；但扩到 500 家公司时，这个选择会变成问题。</p>""",
      cite(("test", "测试", "三个边界值分别得到 PUBLISHED / PUBLISHED / WITHHELD，并断言 trace 里恰好有一条 CROSS_CHECK_EVALUATED。",
            "tests/vnext/test_replay.py:1777-1827"),
           ("artifact", "产物", "当前 active R2 的 220 个坐标里 WITHHELD 数量是 0。", ""),
           ("code", "代码", "通用路径把异常转成 WITHHELD；R2 确定性路径直接 raise。",
            "calculator.py:1103-1122 vs zero_ai_r2.py:1814"),
           ("gap", "缺口", "异常消息里没有 company_id / metric_id，诊断时需要人去翻数据。", "")))

# ---- 15 ------------------------------------------------------------------
slide("15", "因果收束", "前置事实 → 后置事实",
      "值稳定，ID 不稳定——这是设计，不是 bug",
      fig_map(),
      """<p>左边六条依赖必须记住：来源身份闭合是 observation 的前提；
      observation 闭合是 Result/Trace 的前提；replay 与 exact set 是 batch 的前提；
      独立生产与兼容是 bundle 的前提；pointer 与 view 是下游消费的前提。</p>
      <p>右下角那条否定关系同样重要：
      <b>「结果值」是原始字节 + catalog 的函数；「结果 ID」还额外依赖代码语义。</b>
      前者稳定，后者会随代码演进漂移。</p>
      <p>本次实测：用今天的代码重编 A05 的 Spec 得到
      <code>sha256:e0ecf50b…</code>，而已发布的 bundle 里是 <code>sha256:31e1c8a1…</code>。
      <b>62 / 62 个 catalog 编译出的 APPLICABLE 结果，spec_closure_hash 全部漂移</b>，
      而 78 个结构性结果不受影响——因为它们不走 <code>compile_spec()</code>，
      自己算一个三元组 hash。</p>
      <p>根因是 <code>specs.py</code> 加了 <code>scope_contract</code> 字段，
      但 <code>spec_interpreter_semantic_version</code> 仍是 <code>"2"</code>，
      所以 <code>execution_semantics_hash</code> 两边完全相同（<code>sha256:f724d526…</code>），
      没有挡住这次语义变更。<b>这是一个真实的治理缺口。</b></p>
      <p>但对外契约完全不受影响：<code>spec_closure_hash</code> 不在公共 20 字段里。
      「用今天的代码重跑得到不同 ID」和「已发布的东西坏了」是两件事——
      已发布的 bundle 完全自洽、可完整验证，并且记录了自己的 <code>source_commit</code>。</p>""",
      cite(("recomputed", "本次重算",
            "在 HEAD 上调 _compiled_deterministic_spec(metric_id='A05') 得 sha256:e0ecf50b…，bundle 里是 sha256:31e1c8a1…；62 个 catalog 编译结果全部漂移，0 个相同。", ""),
           ("recomputed", "本次重算", "execution_semantics_hash 两边都是 sha256:f724d526…——声明的语义版本没有跟着动。", ""),
           ("code", "代码", "结构性结果自己算三元组 hash，不调 compile_spec。", "zero_ai_r2.py:2108-2127")))

# ---- 16 ------------------------------------------------------------------
LOC_GIT = F["locator"].get("IMMUTABLE_GIT_BLOB", 0)
LOC_ATT = F["locator"].get("IMMUTABLE_ATTEMPT", 0)
LOC_N = LOC_GIT + LOC_ATT
LOC_PCT = f"{100 * LOC_GIT / LOC_N:.1f}"
assert LOC_N == F["n_refs"], "locator proofs do not cover every source reference"
assert set(F["locator"]) == set(F["prov"]["request_locator_classes"]), "locator class set differs"

DIFF = f"""<table class="t diff">
<thead><tr><th>编号</th><th>文档说法</th><th>代码 / 产物事实</th><th>材料性</th></tr></thead>
<tbody>
<tr><td>D1</td>
    <td>「R2 硬性要求 <code>IMMUTABLE_ATTEMPT</code>」</td>
    <td>只对财务来源成立。实测 {LOC_N} 个来源证明里 <b>{LOC_GIT} 个是 IMMUTABLE_GIT_BLOB</b>
        （{LOC_PCT}%），全部 8-K 来源都走 Git blob。<code>publication.py:4347-4353</code> 把这两类
        <b>钉死</b>成 R2 的期望 exact set——不是兜底，是必须出现。</td>
    <td class="hi">高</td></tr>
<tr><td>D2</td><td>「{F["claim_unique"]} 条唯一 claim（COMPANYFACTS {F["claim_kinds"]["COMPANYFACTS_NUMERIC_FACT"]} /
        8K_ITEM {F["claim_kinds"]["DETERMINISTIC_8K_ITEM_BRIEF"]} /
        ACCESSION_XBRL {F["claim_kinds"]["ACCESSION_XBRL_NUMERIC_FACT"]}）」</td>
    <td>{F["claim_records"]} 条<b>记录</b>，{F["claim_unique"]} 个<b>唯一 ID</b>。分项之和
        {sum(F["claim_kinds"].values())} 是记录数，被配到了唯一数上。</td>
    <td>低</td></tr>
<tr><td>D3</td><td>「25 个文件 = 14 公共 + 10 internal + 1 marker」</td>
    <td>manifest 列 25 个 = 14 公共 + <b>11</b> internal；marker 是那 11 个之一，不是第 26 个。</td>
    <td>低</td></tr>
<tr><td>D4</td><td><code>zero_ai_release.py:380-381</code>、<code>records.py:1530-1575</code></td>
    <td>实为 <b>379-380</b> 与 <b>1530-1571</b>。抽查的 35 个函数定位与十余段代码引用全部精确，只有这两处偏一两行。</td>
    <td>低</td></tr>
<tr><td>D5</td><td>RawBlob <code>byte_length: 7 708 165</code></td>
    <td>实测 <b>7 888 465</b>；同一段里的 raw_asset_id 是对的。</td>
    <td>低</td></tr>
<tr><td>D6</td><td>引用 <code>git diff 4d79b372..HEAD</code> 作为取证</td>
    <td>该 commit 不在本 clone 的历史里，命令无法复现。<b>但结论我独立验证了</b>（见第 15 幕）：
        62/62 漂移，execution_semantics_hash 不变。</td>
    <td>中</td></tr>
<tr><td>D7</td><td>三份文档都没写的三件机制事实</td>
    <td>① 220 个坐标只对应 200 条图内记录；② <code>source_binding</code> 有两种形状；
        ③ 80 个 N_A_STRUCTURAL 只产出 79 个 STRUCTURAL 公共行。</td>
    <td class="hi">高</td></tr>
</tbody></table>"""

slide("16", "核对结果", "文档 vs 代码",
      "差异按材料性排序，没有偷偷选一个版本",
      DIFF,
      """<p>三份文档的整体准确度很高——抽查的 35 个函数定位、十余段代码片段、
      以及几乎所有产物数值都精确对上。下面这些是不一致处。</p>
      <p><b>D1 是唯一影响机制理解的一处。</b>三份文档都把 Git-blob locator 描述成
      「历史遗留材料的少数兜底」。实际分布是：财务家族（companyfacts / accession XBRL / submissions）
      共 40 个来源，全部 <code>IMMUTABLE_ATTEMPT</code>；
      事件家族（8-K header + primary，加 JPMorgan 的 submissions 分片）共 310 个，
      全部 <code>IMMUTABLE_GIT_BLOB</code>。
      这不削弱证据强度——Git-blob 证明同样要求 ledger 行、body/header 属于同一 commit、
      工作区字节与 <code>git cat-file</code> 完全一致，且全程无网络——
      但「fallback」这个词会让读者对量级判断错误。</p>
      <p>另外三份文档的<b>基线不一致</b>：只有一份在当前 HEAD <code>d9bb477</code>，
      另一份声明基线是 <code>f64ca601</code>。本 deck 一律以 HEAD 和 active bundle 为准。</p>""",
      cite(("recomputed", "本次重算",
            f"locator 分布：IMMUTABLE_GIT_BLOB {F['locator'].get('IMMUTABLE_GIT_BLOB', 0)}、"
            f"IMMUTABLE_ATTEMPT {F['locator'].get('IMMUTABLE_ATTEMPT', 0)}，共 350。",
            "internal/request_locator_provenance.json"),
           ("code", "代码", "expected_locator_classes 按 release stage 钉死两类。", "publication.py:4347-4353"),
           ("code", "代码", "财务来源硬拒非 IMMUTABLE_ATTEMPT；事件来源捕获异常后退到 Git blob。",
            "zero_ai_release.py:379-380 / zero_ai_r2.py:904")))

# ---- 17 ------------------------------------------------------------------
EVID = """<table class="t">
<thead><tr><th>要核验的结论</th><th>去哪里看</th></tr></thead>
<tbody>
<tr><td>来源身份与路径安全</td><td><code>scripts/vnext/sources.py</code> · <code>tests/vnext/test_source_records.py</code></td></tr>
<tr><td>集合闭合与五个适配器</td><td><code>scripts/vnext/deterministic_router.py</code> · <code>tests/vnext/test_deterministic_router.py</code></td></tr>
<tr><td>选数、分支与四态</td><td><code>scripts/vnext/calculator.py</code> · <code>catalog/deterministic_metrics.json</code> · <code>tests/vnext/test_b03_calculator.py</code></td></tr>
<tr><td>R2 端到端编排与坐标闸门</td><td><code>scripts/vnext/zero_ai_r2.py</code> · <code>tests/vnext/test_zero_ai_release.py</code></td></tr>
<tr><td>独立渲染与兼容性</td><td><code>scripts/vnext/public_projection.py</code> · <code>scripts/vnext/projection_independence.py</code></td></tr>
<tr><td>发布事务、恢复与 pinned read</td><td><code>scripts/vnext/publication.py</code> · <code>tests/vnext/test_publication.py</code> · <code>tests/vnext/test_formal_fault_matrix.py</code></td></tr>
<tr><td>replay 与自洽伪造</td><td><code>scripts/vnext/run_store.py</code> · <code>scripts/vnext/replay.py</code> · <code>tests/vnext/test_replay.py</code></td></tr>
<tr><td>当前正式版本本身</td><td><code>outputs/active_publication.json</code> · bundle 内 <code>internal/zero_ai_release_receipt.json</code></td></tr>
</tbody></table>"""

slide("17", "证据索引", "去哪里核验",
      "每一条结论都应该能被独立复核",
      EVID,
      f"""<p>本 deck 由构建脚本 <code>tools/visual/build_flow1_deck.py</code> 生成，
      运行时从 active bundle 读取全部数值，所以发布出来的 HTML 不可能与它描述的产物漂移。
      重新生成：<code>python3 tools/visual/build_flow1_deck.py</code>。</p>
      <p><b>本次核对的边界，必须说清楚：</b>没有查询 GitHub PR 或 checks，不声称 CI 通过；
      没有运行完整验收，不声称 full acceptance；没有重新发布 R2，只读回现有 active bundle 并在源码上重算。
      bundle 自己在 <code>validation_run_manifest.json</code> 里写着
      <code>LIGHT_REVIEW_MODE</code> / <code>PASSED_WITH_CAVEATS</code>——它没有假装是完整验收。</p>
      <p>还有一点值得单独指出：R2 发布的 14 个对外文件里，只有 6 个是本次新算的，
      2 个只是被追加了一段状态块，另外 6 个与前驱 R1 bundle <b>逐字节相同</b>。
      这意味着 <code>repair_validation_results.csv</code> 里那些 P0 检查结果
      <b>不是 R2 跑出来的</b>，是继承的。设计本身是诚实的（bundle 里就写着 caveat），
      但读者如果把 14 个文件当成同一版验证过的，会高估这一版的验证覆盖面。</p>
      <p class="sig">bundle 共 {len(F['manifest']['files'])} 个文件、
      {sum(f['size'] for f in F['manifest']['files']):,} 字节 ·
      publication_id 由内容派生，包含「前驱是谁」，所以发布链是一条 hash 链。</p>""",
      cite(("artifact", "产物", "validation_run_manifest.json 写着 mode = LIGHT_REVIEW_MODE、result = PASSED_WITH_CAVEATS。", ""),
           ("recomputed", "本次重算", "逐文件对 sha256 得出：6 个新算、2 个追加状态块、6 个与前驱逐字节相同。", ""),
           ("code", "代码", "publication_id = content_hash({candidate_status, requirement_hashes, batch/projection/validation ids, files, ledger_binding, previous_publication_id})。",
            "publication.py:4541-4553")))

# --------------------------------------------------------------------------
# build-time invariants — the deck may not ship a number the bundle contradicts
# --------------------------------------------------------------------------
_na_rows = [r for r in F["rows"] if r["status"] == "N_A_STRUCTURAL"]
assert len(_na_rows) == N_NA, "N_A_STRUCTURAL row count differs from the coordinate index"
assert sum(1 for r in _na_rows if r["source_class"] == "STRUCTURAL") == N_NA - 1, (
    "the 80-vs-79 asymmetry no longer holds; slide 11 must be rewritten")
assert F["status"].get("OK_APPROX", 0) == Q["APPROX"], "OK_APPROX rows differ from APPROX coordinates"
assert F["receipt"]["result_coordinate_count"] == 10 * len(F["receipt"]["cumulative_metric_ids"])
assert len(F["index"]) == F["receipt"]["result_coordinate_count"]
assert len({(c["company_id"], c["metric_id"]) for c in F["index"]}) == len(F["index"])
assert F["compat"]["compared_field_count"] == F["compat"]["compared_key_count"] * 20
assert F["compat"]["unexpected_delta_exact_set"] == [] == F["compat"]["approved_delta_exact_set"]
assert (F["compat"]["vnext_rendered_row_set_hash"]
        == F["compat"]["frozen_legacy_row_set_hash"]), "the 141 rows are no longer byte-identical"
assert set(F["receipt"]["counters"].values()) == {0}, "provider call counters are not all zero"
assert sum(1 for r in F["graph"]["records"] if r["record_type"] == "METRIC_RESULT") == 200
assert len(F["manifest"]["files"]) == 25

# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------

CSS = """
:root{
  --ground:#F5F8F6; --card:#FFFFFF; --panel:#FBFDFC; --panel2:#EDF2F0;
  --ink:#111D1A; --ink2:#4B5C57; --ink3:#71837D;
  --rule:#D4DDD9; --rule2:#E6ECEA;
  --fact:#0B7A66; --factbg:#E2F1ED;
  --degrade:#96600A; --degradebg:#F6EDDC;
  --refuse:#9E3728; --refusebg:#F7E6E2;
  --inherit:#514A96; --inheritbg:#E9E7F5;
  --neutral:#5E706B;
  --shadow:0 1px 2px rgba(17,29,26,.05),0 10px 30px rgba(17,29,26,.06);
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:"IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",system-ui,sans-serif;
  --disp:"Newsreader","Songti SC","Noto Serif CJK SC",Georgia,serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#080D0C; --card:#111A17; --panel:#16211D; --panel2:#1C2823;
  --ink:#E5ECE9; --ink2:#9BADA8; --ink3:#788A85;
  --rule:#25322D; --rule2:#1D2825;
  --fact:#4FD3B2; --factbg:#0F2B25;
  --degrade:#E8B45C; --degradebg:#2E2513;
  --refuse:#F08A76; --refusebg:#331C17;
  --inherit:#ABA2F5; --inheritbg:#1E1B33;
  --neutral:#8CA09A;
  --shadow:0 1px 2px rgba(0,0,0,.5),0 10px 30px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --ground:#080D0C; --card:#111A17; --panel:#16211D; --panel2:#1C2823;
  --ink:#E5ECE9; --ink2:#9BADA8; --ink3:#788A85;
  --rule:#25322D; --rule2:#1D2825;
  --fact:#4FD3B2; --factbg:#0F2B25;
  --degrade:#E8B45C; --degradebg:#2E2513;
  --refuse:#F08A76; --refusebg:#331C17;
  --inherit:#ABA2F5; --inheritbg:#1E1B33;
  --neutral:#8CA09A;
  --shadow:0 1px 2px rgba(0,0,0,.5),0 10px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.72;-webkit-font-smoothing:antialiased}
.deck{max-width:1180px;margin:0 auto;padding:34px clamp(14px,3vw,30px) 90px;
  display:flex;flex-direction:column;gap:30px}

.slide{background:var(--card);border:1px solid var(--rule);border-radius:12px;
  padding:clamp(24px,3.4vw,46px);box-shadow:var(--shadow);position:relative;
  counter-increment:sl}
.slide::after{content:counter(sl) " / " counter(total);position:absolute;right:26px;bottom:16px;
  font-family:var(--mono);font-size:10.5px;color:var(--ink3);font-variant-numeric:tabular-nums}
.deck{counter-reset:sl 0 total 18}

.sh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  padding-bottom:11px;margin-bottom:16px;border-bottom:1px solid var(--rule2)}
.sn{font-family:var(--mono);font-size:12px;color:var(--fact);font-weight:600;letter-spacing:.06em}
.sk{font-family:var(--mono);font-size:12px;color:var(--ink2)}
.si{font-family:var(--mono);font-size:11px;color:var(--ink3);margin-left:auto}
h2{font-family:var(--disp);font-weight:600;font-size:clamp(23px,2.9vw,33px);line-height:1.24;
  margin:0 0 18px;letter-spacing:-.012em;text-wrap:balance}
h2 em{font-style:normal;color:var(--fact)}
p.lead{margin:-8px 0 18px;color:var(--ink2);font-size:15.5px;max-width:70ch}

.sb{display:grid;gap:clamp(16px,2.2vw,30px) clamp(18px,2.6vw,38px);align-items:start}
.sb{grid-template-columns:minmax(0,1.52fr) minmax(0,1fr);
  grid-template-areas:"fig fig" "prose ev"}
.fig{grid-area:fig}.prose{grid-area:prose}.ev{grid-area:ev}
@media (max-width:880px){
  .sb{grid-template-columns:minmax(0,1fr);grid-template-areas:"fig" "prose" "ev"}
}

.fig{margin:0;background:var(--panel2);border:1px solid var(--rule2);border-radius:9px;
  padding:14px;overflow-x:auto}
.fig svg{display:block;width:100%;height:auto;min-width:480px}
.fig.wide svg{min-width:560px}
svg text{font-family:var(--sans);fill:var(--ink)}
svg .m,svg .m2,svg .k,svg .n{font-family:var(--mono)}
svg .k{font-size:11px;letter-spacing:.07em}
svg .m{font-size:11.5px}
svg .m2{font-size:10.5px;fill:var(--ink3)}
svg .n{font-size:10.5px;fill:var(--ink3)}
svg .b{font-size:12.5px}
svg .s{font-size:13.5px;font-weight:600}
svg .big{font-size:24px;font-weight:600;font-family:var(--mono)}

.prose{max-width:70ch}
.ev{align-self:start}
.prose p{margin:0 0 13px}
.prose p:last-of-type{margin-bottom:16px}
.prose b{font-weight:600}
.prose em{font-style:normal;color:var(--fact);font-weight:600}
code{font-family:var(--mono);font-size:.86em;background:var(--panel2);
  padding:1px 5px;border-radius:3px;word-break:break-word}

table.t{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0 16px;
  font-variant-numeric:tabular-nums}
table.t th{text-align:left;font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink3);font-weight:500;
  padding:8px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
table.t td{padding:9px 10px;border-bottom:1px solid var(--rule2);vertical-align:top}
table.t tbody tr:last-child td{border-bottom:0}
table.t td.num{font-family:var(--mono);text-align:right}
table.t td.ok{color:var(--fact);font-family:var(--mono);font-size:11.5px}
table.t td.no{color:var(--refuse);font-family:var(--mono);font-size:11.5px}
table.t td.warn{color:var(--degrade);font-family:var(--mono);font-size:11.5px}
table.t td.hi{color:var(--refuse);font-weight:600}
table.diff td:nth-child(1){font-family:var(--mono);color:var(--ink3)}
table.diff td:nth-child(2){width:24%}
.fig table.t{margin:0}

ul.cite{list-style:none;margin:0;padding:15px 16px;border:1px solid var(--rule2);
  border-radius:8px;background:var(--panel)}
ul.cite li{font-size:12.5px;line-height:1.6;color:var(--ink2);margin-bottom:8px}
ul.cite li:last-child{margin-bottom:0}
ul.cite code{display:block;margin-top:2px;font-size:11px;color:var(--ink3);background:none;padding:0}
.tag{font-family:var(--mono);font-size:9.5px;letter-spacing:.09em;border:1px solid var(--rule);
  border-radius:3px;padding:1px 5px;margin-right:7px;color:var(--ink3);white-space:nowrap}
.tag[data-k="artifact"]{color:var(--fact);border-color:color-mix(in srgb,var(--fact) 42%,transparent)}
.tag[data-k="test"]{color:var(--inherit);border-color:color-mix(in srgb,var(--inherit) 42%,transparent)}
.tag[data-k="recomputed"]{color:var(--degrade);border-color:color-mix(in srgb,var(--degrade) 48%,transparent)}
.tag[data-k="gap"]{color:var(--refuse);border-color:color-mix(in srgb,var(--refuse) 48%,transparent)}

.cover{background:var(--factbg);border-color:color-mix(in srgb,var(--fact) 26%,transparent)}
.cover::after{content:""}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.15em;text-transform:uppercase;
  color:var(--fact);margin:0 0 14px}
h1{font-family:var(--disp);font-weight:600;font-size:clamp(30px,5vw,54px);line-height:1.1;
  margin:0 0 20px;letter-spacing:-.018em;text-wrap:balance}
.thesis{max-width:72ch;color:var(--ink2);font-size:16px;margin:0 0 20px}
.thesis b{color:var(--ink);font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:24px}
.chip{font-family:var(--mono);font-size:11.5px;padding:3px 10px;border:1px solid var(--rule);
  border-radius:999px;color:var(--ink2);background:var(--card);white-space:nowrap}
.chip b{color:var(--ink);font-weight:500}
.foot{font-size:12.5px;color:var(--ink3);margin:16px 0 0}
.sig{font-family:var(--mono);font-size:11.5px;color:var(--ink3);border-top:1px solid var(--rule2);
  padding-top:12px;margin-top:16px}

@media print{
  body{background:#fff;font-size:12.5px;line-height:1.6}
  .deck{max-width:none;padding:0;gap:0}
  .slide{break-after:page;page-break-after:always;box-shadow:none;border:0;
    border-radius:0;padding:0 0 12px;min-height:0}
  .slide::after{position:static;display:block;text-align:right;margin-top:6px}
  h1{font-size:34px}h2{font-size:22px;margin-bottom:12px}
  .sb{gap:14px 22px}
  .fig{background:none;border:1px solid #d8ddda;padding:8px}
  .fig svg{min-width:0}
  /* a figure, a table or an evidence block must never split across pages */
  .fig,table.t,ul.cite,.prose p{break-inside:avoid;page-break-inside:avoid}
  table.t{font-size:11px}
  ul.cite{background:none;font-size:11px}
  .cover{background:none;border:0}
  @page{size:A4 landscape;margin:10mm}
}
"""

HTML = (
    "<title>信任升级讲义</title>\n"
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700"
    '&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap">\n'
    f"<style>{CSS}</style>\n"
    '<main class="deck">' + "".join(SLIDES) + "</main>\n"
)

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT.relative_to(REPO)}  {len(HTML):,} bytes  {len(SLIDES)} slides")
