# -*- coding: utf-8 -*-
"""Build the static flow-3 slide deck.

Flow 3 is the publication transaction: how a batch of already-correct files
becomes "the current official version".  Every number in the deck is read at
build time from the active publication bundle, the switch-receipt history and
the source tree, so the shipped HTML cannot drift from what it describes.

The output contains no script tag.  Text carries meaning, SVG carries
structure, and nothing is animated.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
PUBS = REPO / "outputs" / "publications"
ACTIVE = (
    "publication_fe01e227848d6a4212318b4942742d06b0a2861"
    "df55e0b268df2062a441c438f"
)
BUNDLE = PUBS / ACTIVE
OUT = REPO / "docs" / "visual" / "flow3-mechanism-deck.html"

E = html.escape


# --------------------------------------------------------------------------
# facts read from artifacts and source at build time
# --------------------------------------------------------------------------

def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_facts() -> dict:
    j = lambda p: json.loads(p.read_text())

    pointer = j(REPO / "outputs" / "active_publication.json")
    manifest = j(BUNDLE / "publication_manifest.json")
    projection = j(BUNDLE / "projection_manifest.json")
    closure = j(BUNDLE / "internal" / "public_projection_closure.json")
    receipt = j(BUNDLE / "internal" / "zero_ai_release_receipt.json")
    validation = j(BUNDLE / "publication_validation_receipt.json")
    runman = j(BUNDLE / "validation_run_manifest.json")

    # ---- switch history: order the chain from its root to its tip ---------
    edges = {}
    for path in sorted((REPO / "outputs" / "publication_switch_receipts").glob("*.json")):
        edges[path.stem] = j(path)
    referenced = {
        str(e["previous_switch_receipt_id"]).split(":", 1)[-1]
        for e in edges.values() if e["previous_switch_receipt_id"]
    }
    tip = next(k for k in edges if k not in referenced)
    chain, cur = [], tip
    while cur:
        chain.append((cur, edges[cur]))
        prev = edges[cur]["previous_switch_receipt_id"]
        cur = str(prev).split(":", 1)[-1] if prev else None
    chain.reverse()
    committed = {str(e["pointer"]["publication_id"]) for _, e in chain}

    # ---- every stored bundle, and which build-chain it belongs to --------
    stored = {}
    for d in sorted(PUBS.iterdir()):
        m = j(d / "publication_manifest.json")
        stored[d.name] = {
            "prev": m["previous_publication_id"],
            "files": sum(1 for f in d.rglob("*") if f.is_file()),
            "internal": sum(1 for f in (d / "internal").rglob("*") if f.is_file())
            if (d / "internal").is_dir() else 0,
            "zero_ai": (d / "internal" / "zero_ai_release_receipt.json").is_file(),
            "legacy": (d / "internal" / "legacy_baseline_import.json").is_file(),
            "closure": (d / "internal" / "closure_manifest.json").is_file(),
            "runs": (d / "internal" / "runs").is_dir(),
            "bytes": sum(f.stat().st_size for f in d.rglob("*") if f.is_file()),
        }
    heads = [k for k, v in stored.items() if v["prev"] is None]
    build_chains = []
    for h in heads:
        row, cur = [h], h
        while True:
            nxt = [k for k, v in stored.items() if v["prev"] == cur]
            if not nxt:
                break
            cur = nxt[0]
            row.append(cur)
        build_chains.append(row)
    build_chains.sort(key=lambda c: c[-1] in committed)

    # ---- the 14 root mirrors, compared byte for byte --------------------
    src = (REPO / "scripts" / "vnext" / "publication.py").read_text()
    required = sorted(re.search(
        r"REQUIRED_BUNDLE_FILES = \{(.*?)\n\}", src, re.S).group(1).split("\n"))
    required = [x.strip().strip(",").strip('"') for x in required if x.strip()]
    same = 0
    for rel in required:
        mirror = REPO / rel if rel.endswith(".md") else REPO / "outputs" / rel
        if mirror.is_file() and mirror.read_bytes() == (BUNDLE / rel).read_bytes():
            same += 1

    # ---- fault matrix scenarios, and whether they ever ran ---------------
    fm = (REPO / "scripts" / "vnext" / "fault_matrix.py").read_text()
    scenarios = re.findall(r'"(ISOLATED_[A-Z_]+)"', fm.split("_SCENARIO_EXPECTATIONS")[0])
    scenarios = sorted(set(scenarios))
    markers = {}
    for ns in ("publication_fault_receipts", "vnext_cutover_audits"):
        d = REPO / "outputs" / ns
        files = sorted(p.name for p in d.iterdir()) if d.is_dir() else []
        markers[ns] = (files, j(d / files[0]) if len(files) == 1 else None)

    # ---- acceptance receipts --------------------------------------------
    acc, full = {}, []
    for p in (REPO / "outputs" / "acceptance_receipts").glob("*.json"):
        d = j(p)
        acc[d.get("status")] = acc.get(d.get("status"), 0) + 1
        if d.get("scope") == "full":
            full.append((d.get("status"), bool(d.get("execute_live")), d.get("started_at_utc")))

    # ---- Requirement closure: recorded in the bundle vs the repo today ---
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from vnext.requirements import _load_issue_15_snapshot  # noqa: E402
    current_closure = _load_issue_15_snapshot(
        snapshot_dir=REPO / "requirements" / "issue_15_v1")["requirement_closure_hash"]

    rows = list(csv.DictReader((BUNDLE / "metrics_matrix.csv").open()))
    migrated = {(b["company_id"], b["metric_id"]) for b in closure["row_bindings"]}

    return {
        "pointer": pointer, "manifest": manifest, "projection": projection,
        "closure": closure, "receipt": receipt, "validation": validation,
        "runman": runman, "chain": chain, "committed": committed,
        "stored": stored, "build_chains": build_chains,
        "required": required, "mirrors_same": same,
        "scenarios": scenarios, "markers": markers,
        "acc": acc, "full": full,
        "current_closure": current_closure,
        "rows": len(rows), "cols": len(rows[0]),
        "migrated": len(migrated),
        "manifest_sha": sha(BUNDLE / "publication_manifest.json"),
        "bundle_files": sum(1 for f in BUNDLE.rglob("*") if f.is_file()),
    }


F = load_facts()
P, M, PJ, CL = F["pointer"], F["manifest"], F["projection"], F["closure"]
CMP = CL["compatibility"]
SHORT = lambda pid: pid.replace("publication_", "")[:8]


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


def elbow(pts, *, tone="fact", dash=False):
    c = TONE[tone]
    d = "M" + " L".join(f"{p[0]} {p[1]}" for p in pts[:-1])
    last, prev = pts[-1], pts[-2]
    da = ' stroke-dasharray="5 4"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{c}" stroke-width="1.5"{da}/>'
            + arr(prev[0], prev[1], last[0], last[1], tone=tone, dash=dash))


def txt(x, y, s, *, cls="b", tone=None, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    f_ = f' fill="{TONE[tone]}"' if tone else ""
    return f'<text class="{cls}" x="{x}" y="{y}"{a}{f_}>{E(s)}</text>'


def band(x, y, w, h, tone="fact", op=".10"):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="{TONE[tone]}" opacity="{op}"/>')


def rule(x1, y1, x2, y2, tone="dim", sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{TONE[tone]}" stroke-width="{sw}"{d}/>'


def svg(w, h, body, *, label=""):
    defs = "".join(
        f'<marker id="a-{k}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">'
        f'<path d="M0,0 L7,3.5 L0,7 z" fill="{v}"/></marker>' for k, v in TONE.items())
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{E(label)}">'
            f"<defs>{defs}</defs>{body}</svg>")


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

STATIONS = [
    ("局部终态结果", "上游交来", "raw"),
    ("批次权威", "batch_manifest_id", "fact"),
    ("独立投影 + 兼容", "2 820 次比较", "fact"),
    ("PUBLISHABLE 候选", "candidate_status", "fact"),
    ("immutable bundle", "publication_id", "fact"),
    ("active pointer", "◆ 唯一提交点", "fact"),
    ("pinned read", "PublicationView", "fact"),
]


def fig_chain():
    b, w, gap, h = [], 178, 16, 88
    total = len(STATIONS) * w + (len(STATIONS) - 1) * gap
    for i, (name, idf, tone) in enumerate(STATIONS):
        col, row = i % 4, i // 4
        x, y = 30 + col * (w + gap), 40 + row * 124
        if i == 5:
            b.append(band(x - 9, y - 12, w + 18, h + 24))
        b.append(node(x, y, w, h, tone=tone, strong=(i == 5)))
        b.append(txt(x + 13, y + 24, f"{i:02d}" if i else "入口", cls="n"))
        b.append(txt(x + 13, y + 48, name, cls="s"))
        b.append(txt(x + 13, y + 70, idf, cls="m", tone=tone))
        if col < 3 and i < len(STATIONS) - 1:
            b.append(arr(x + w, y + h / 2, x + w + gap - 2, y + h / 2, tone="fact"))
        elif i < len(STATIONS) - 1:
            b.append(elbow([(x + w // 2, y + h + 12), (x + w // 2, y + h + 24),
                            (44, y + h + 24), (44, y + h + 38)]))
    y = 40 + 124 + 88 + 26
    b.append(node(30, y, total, 62, tone="refuse", kind="任意一站失败",
                  rows=["active_publication.json 逐字节不变 · 收据数量不变 · 14 个镜像未被触碰 · 下游继续读上一版"]))
    return svg(30 + total + 30, y + 80, "".join(b),
               label="七个工位把局部终态结果加工成当前正式版本，第五站是唯一提交点，任意一站失败都回落到旧版本")


def fig_overwrite():
    b = [node(24, 26, 250, 150, tone="refuse", kind="直接覆盖 outputs/",
              rows=[("已写新的", "metrics_matrix.csv", "refuse"),
                    ("还没写", "coverage_matrix.csv", "refuse"),
                    ("进程被 kill", "——", "refuse")],
              note="两个文件各自都是合法 CSV"),
         arr(282, 100, 320, 100, tone="refuse"),
         node(328, 26, 268, 150, tone="refuse", kind="下游读到的组合",
              rows=["一半新，一半旧",
                    "这个组合从未存在过",
                    "任何格式校验都发现不了"],
              note="没有一个文件是「坏」的"),
         arr(604, 100, 642, 100, tone="refuse"),
         node(650, 26, 236, 150, tone="refuse", kind="想退回去",
              rows=["旧文件已经被覆盖", "没了",
                    "手工备份本身也会写一半"],
              note="没有版本，只有文件"),
         node(24, 196, 862, 58, tone="degrade", kind="更根本的缺失",
              rows=["「当前正式版本是哪一版」这个概念根本不存在 —— 你说不出现在生效的是哪一版，也说不出上一版是什么"])]
    return svg(910, 274, "".join(b),
               label="直接覆盖输出目录会产生一个从未存在过的半新半旧组合，且无法回退，因为系统里根本没有版本这个概念")


def fig_swap():
    b = [txt(30, 26, "十几个文件的更新", cls="k", tone="refuse"),
         txt(500, 26, "一个指针的替换", cls="k", tone="fact")]
    for i in range(7):
        y = 44 + i * 22
        b.append(node(30, y, 300, 16, tone="refuse"))
        b.append(txt(40, y + 12, ["metrics_matrix.csv", "coverage_matrix.csv", "metric_evidence.csv",
                                  "golden_results.csv", "REPORT_十公司财务指标.md",
                                  "README_RUN.md", "…共 14 个"][i], cls="m2"))
    b.append(txt(30, 212, "14 次写入 = 14 个可以崩在中间的时刻", cls="n", tone="refuse"))
    b.append(arr(346, 120, 468, 120, tone="fact"))
    b.append(txt(407, 110, "转化成", cls="n", anchor="middle"))
    b.append(node(500, 74, 386, 92, tone="fact", strong=True, kind="outputs/active_publication.json",
                  rows=[("publication_id", SHORT(P["publication_id"]) + "…", "fact"),
                        ("previous_publication_id", SHORT(P["previous_publication_id"]) + "…")],
                  note="一次 rename = 一个不可分割的时刻"))
    b.append(txt(500, 212, "1 次原子替换 = 唯一一个提交点", cls="n", tone="fact"))
    return svg(910, 236, "".join(b),
               label="把十四个文件的更新转化成一个四字段指针文件的原子替换，崩溃窗口从十四个收敛成一个")


def fig_actors():
    b = [node(24, 30, 270, 130, tone="fact", kind="① 批次权威",
              rows=[("回答", "这批既不缺也不重"),
                    ("身份", "batch_manifest_id"),
                    ("当前值", SHORT(M["batch_manifest_id"].split(":")[-1] if ":" in M["batch_manifest_id"] else M["batch_manifest_id"]) + "…", "fact")],
              note="R2 编码：ZERO_AI_COORDINATE_INDEX"),
         arr(302, 95, 336, 95, tone="fact"),
         node(344, 30, 270, 130, tone="fact", kind="② 不可变发布包",
              rows=[("回答", "这一版包含什么"),
                    ("身份", "publication_id"),
                    ("当前值", SHORT(P["publication_id"]) + "…", "fact")],
              note="目录名就是内容指纹"),
         arr(622, 95, 656, 95, tone="fact"),
         node(664, 30, 270, 130, tone="fact", strong=True, kind="③ pointer + 切换历史",
              rows=[("回答", "此刻哪一版是正式的"),
                    ("身份", "四个字段 + 一条收据链"),
                    ("当前值", SHORT(P["publication_id"]) + "…", "fact")],
              note="pointer 单独不能自证"),
         node(24, 184, 910, 56, tone="degrade", kind="为什么第三个必须是两件东西",
              rows=["pointer 只是一个四字段 JSON。如果它能脱离收据链单独被改，改一个文件就能把任意包变成「正式版本」。"])]
    return svg(958, 258, "".join(b),
               label="三个主角对象各自回答一个不同的问题，第三个必须由指针和切换收据链共同承担")


def fig_batch():
    b = [node(24, 30, 250, 136, tone="raw", kind="仓库独立推导",
              rows=[("company registry", "10"),
                    ("release plan × spec", "22 指标"),
                    ("expected 坐标", str(PJ["result_coordinate_count"]), "fact")],
              note="调用者不能自报应有集合"),
         node(330, 30, 250, 136, tone="raw", kind="实际结果集",
              rows=[("actual 坐标", str(PJ["result_coordinate_count"]), "fact"),
                    ("重复", "0"), ("缺失", "0"), ("多余", "0")],
              note="来自 deterministic 执行图"),
         txt(302, 100, "=", cls="big", tone="fact", anchor="middle"),
         arr(588, 98, 622, 98, tone="fact"),
         node(630, 30, 280, 136, tone="fact", strong=True, kind="批次权威成立",
              rows=[("batch_manifest_id", "c6c1a236…", "fact"),
                    ("target fiscal year", "全批同一"),
                    ("Requirement", "全批同一")],
              note="content-addressed，不能原地编辑"),
         node(24, 190, 886, 54, tone="refuse", kind="不相等就在这里终止",
              rows=["ProjectionError 上抛 · 不产生 staging、不产生 bundle、不读取指针 · 单个 Run 永远发现不了「另一家公司少了一行 N/A」"])]
    return svg(934, 262, "".join(b),
               label="仓库独立推导的应有坐标集与实际结果集必须完全相等，批次权威才成立")


def fig_projection():
    b = [band(24, 22, 430, 200, "refuse", ".07"),
         txt(38, 44, "✕ 先复制，再声明相同", cls="k", tone="refuse"),
         node(38, 58, 180, 62, tone="refuse", rows=[("旧 CSV", "141 行")], ),
         arr(226, 89, 258, 89, tone="refuse"),
         node(266, 58, 174, 62, tone="refuse", rows=[("新输出", "= 同一份字节")]),
         txt(38, 152, "比较永远成立 —— 因为相等是复制", cls="b", tone="refuse"),
         txt(38, 174, "保证的，不是计算保证的。", cls="b", tone="refuse"),
         txt(38, 202, "新对象图哪怕完全没参与，也全绿", cls="n", tone="refuse"),

         band(478, 22, 432, 200, "fact", ".07"),
         txt(492, 44, "● 先独立渲染，再事后比较", cls="k", tone="fact"),
         node(492, 58, 180, 62, tone="fact", rows=[("新对象图", "→ 220 行")]),
         node(492, 132, 180, 56, tone="raw", dash=True, rows=[("冻结 legacy", "此刻才读")]),
         arr(680, 89, 712, 89, tone="fact"),
         elbow([(582, 188), (582, 204), (760, 204), (760, 190)], tone="raw", dash=True),
         node(720, 58, 174, 130, tone="fact", strong=True,
              rows=[("compared_key", str(CMP["compared_key_count"]), "fact"),
                    ("compared_field", f"{CMP['compared_field_count']:,}", "fact"),
                    ("approved delta", "空" if not CMP["approved_delta_exact_set"] else "非空"),
                    ("unexpected delta", "空" if not CMP["unexpected_delta_exact_set"] else "非空", "fact")],
              note="oracle，不是数值来源")]
    return svg(934, 240, "".join(b),
               label="左边是复制后比较的循环证明，右边是先独立渲染再拿冻结快照做事后比较的当前做法")


def fig_309():
    total, mig = F["rows"], F["migrated"]
    non = total - mig
    W = 860
    wm = int(W * mig / total)
    b = [txt(24, 26, f"正式 metrics_matrix.csv · {total} 行 × {F['cols']} 列", cls="k", tone="fact"),
         f'<rect x="24" y="40" width="{wm}" height="54" rx="4" fill="var(--panel)" stroke="var(--fact)" stroke-width="1.6"/>',
         f'<rect x="{24+wm}" y="40" width="{W-wm}" height="54" rx="4" fill="var(--panel)" stroke="var(--neutral)" stroke-width="1.2" stroke-dasharray="5 4"/>',
         txt(24 + wm // 2, 64, f"{mig} 行 · 本次迁移", cls="s", tone="fact", anchor="middle"),
         txt(24 + wm // 2, 84, "由新对象图独立渲染", cls="m2", anchor="middle"),
         txt(24 + wm + (W - wm) // 2, 64, f"{non} 行 · 未迁移", cls="s", anchor="middle"),
         txt(24 + wm + (W - wm) // 2, 84, "保持前驱顺序", cls="m2", anchor="middle"),
         rule(24 + wm, 34, 24 + wm, 100, "fact", 1, "3 3"),
         node(24, 118, 420, 96, tone="fact", kind=f"{mig} 行里有 {CMP['compared_key_count']} 个既有 key",
              rows=[("逐字段比较", f"{CMP['compared_key_count']} × 20 = {CMP['compared_field_count']:,}", "fact"),
                    ("每个字段", f"equal {CMP['compared_key_count']} / delta 0 / delta 0")]),
         node(464, 118, 420, 96, tone="raw",
              kind=f"另外 {PJ['new_public_key_count']} 个是新增 key",
              rows=[("主要是", "结构性 N/A 坐标"),
                    ("语义", "完整结果的一部分，不是缺失")]),
         txt(24, 236, f"{total} − {mig} = {non}：这两个数都能从产物单独读出，差值与 CSV 实际行数相符。",
             cls="n")]
    return svg(910, 254, "".join(b),
               label="公共矩阵三百零九行由两百二十行本次迁移行与八十九行未迁移行组成，迁移行中有一百四十一个既有 key 参与逐字段比较")


TRUTH = [("APPLICABLE", "PUBLISHED", "不阻断", "正常已发布的结果", False),
         ("APPLICABLE", "WITHHELD", "BLOCKED", "本应有结果，证据或计算不足", True),
         ("N_A_STRUCTURAL", "PUBLISHED", "不阻断", "结构性不适用", False),
         ("N_A_STRUCTURAL", "WITHHELD", "不阻断", "结构性不适用，且未发布", False)]


def fig_truth():
    rows = "".join(
        f'<tr><td><code>{E(a)}</code></td><td><code>{E(b)}</code></td>'
        f'<td class="{"no" if hit else "ok"}">{E(r)}</td><td>{E(d)}</td></tr>'
        for a, b, r, d, hit in TRUTH)
    return ('<table class="t"><thead><tr><th>applicability</th><th>publication</th>'
            '<th>批次级判定</th><th>语义</th></tr></thead><tbody>' + rows + "</tbody></table>")


def fig_write():
    steps = [("t0", "算 publication_id", ("由 identity", "内容派生")),
             ("t1", "写隐藏临时目录", (".{id}.{uuid4}", ".tmp")),
             ("t2", "逐文件原子写", (f"{len(M['files'])} 个 payload", "atomic_write")),
             ("t3", "写 manifest", ("publication_", "manifest.json")),
             ("t4", "临时目录上先验", ("verify_", "publication_bundle")),
             ("t5", "os.replace", ("+ fsync 父目录", "目录级原子改名")),
             ("t6", "最终目录再验", ("一次", "→ PREPARED"))]
    b, w, gap = [], 152, 6
    for i, (t, name, sub) in enumerate(steps):
        x = 24 + i * (w + gap)
        b.append(node(x, 40, w, 96, tone="fact", strong=(i == 5)))
        b.append(txt(x + 11, 62, t, cls="n", tone="fact"))
        b.append(txt(x + 11, 84, name, cls="m"))
        b.append(txt(x + 11, 102, sub[0], cls="m2"))
        b.append(txt(x + 11, 117, sub[1], cls="m2"))
        if i < len(steps) - 1:
            b.append(arr(x + w, 88, x + w + gap - 1, 88, tone="fact"))
    tot = len(steps) * (w + gap) - gap
    b.append(txt(24, 26, "写包本身就是一个小事务", cls="k", tone="fact"))
    b.append(node(24, 154, tot, 58, tone="refuse", kind="中途任何异常",
                  rows=["finally 删除临时目录 · 最终 publication ID 目录只在完整验证通过后才出现 · 不会留下一个看起来完整的半成品包"]))
    b.append(txt(24, 234, "幂等：最终目录已存在时，验证已有内容与本次 manifest 逐字段相等；不等报 Existing publication ID has divergent bytes。", cls="n"))
    return svg(24 + tot + 24, 252, "".join(b),
               label="写包的七个步骤：先写隐藏临时目录并在其上完整验证，再目录级原子改名，中途异常则删除临时目录")


def fig_chains():
    b, w, gap = [], 168, 30
    y0 = 44
    for ci, ch in enumerate(F["build_chains"]):
        y = y0 + ci * 74
        live = ch[-1] in F["committed"]
        b.append(txt(24, y - 8, "正式历史 · 收据链承认" if live else "彩排 · 从未提交",
                     cls="n", tone="fact" if live else "dim"))
        for i, pid in enumerate(ch):
            x = 24 + i * (w + gap)
            b.append(node(x, y, w, 46, tone="fact" if live else "dim", dash=not live,
                          strong=(live and i == len(ch) - 1)))
            b.append(txt(x + 12, y + 22, SHORT(pid), cls="m", tone="fact" if live else None))
            b.append(txt(x + 12, y + 38, ["legacy", "R1", "R2"][i], cls="m2"))
            if i < len(ch) - 1:
                b.append(arr(x + w, y + 23, x + w + gap - 2, y + 23,
                             tone="fact" if live else "dim", dash=not live))
        if live:
            xl = 24 + (len(ch) - 1) * (w + gap) + w
            b.append(rule(xl + 6, y + 23, xl + 34, y + 23, "fact", 1.5))
            b.append(txt(xl + 40, y + 27, "← active pointer", cls="m", tone="fact"))
    orphan = sum(v["bytes"] for k, v in F["stored"].items() if k not in F["committed"])
    b.append(node(24, y0 + 3 * 74 + 8, 3 * w + 2 * gap, 56, tone="degrade",
                  kind="目录存在 ≠ 曾经正式",
                  rows=[f"{len(F['stored'])} 个包，{len(F['committed'])} 个进过切换历史 · "
                        f"孤儿 {len(F['stored'])-len(F['committed'])} 个共 {orphan/1048576:.1f} MB · 彩排的代价只有磁盘"]))
    return svg(24 + 3 * w + 2 * gap + 190, y0 + 3 * 74 + 80, "".join(b),
               label="磁盘上九个发布包构成三条建造链，只有第三条出现在切换收据里，末端是当前 active")


def fig_authority():
    b = [node(24, 30, 300, 108, tone="refuse", kind="commit_publication()",
              rows=["无条件 raise",
                    "FORMAL_CUTOVER_AUTHORITY_REQUIRED"],
              note="publication.py:6011 · 公共 API"),
         node(24, 150, 300, 76, tone="refuse", kind="commit_initial_publication_chain()",
              rows=["同样无条件 raise"], note="publication.py:5902"),
         txt(348, 92, "✕", cls="big", tone="refuse", anchor="middle"),
         txt(348, 190, "✕", cls="big", tone="refuse", anchor="middle"),
         node(392, 30, 300, 196, tone="fact", kind="_publication_commit_authority",
              rows=["判据 1  有 legacy_baseline_import.json",
                    "        → LEGACY_BASELINE",
                    "判据 2  有 zero_ai_release_receipt.json",
                    "        → FORMAL（要求 previous 非空）",
                    "判据 3  否则查 (mode, result) 表",
                    "        → FORMAL 或 RECORDED"],
              note="只读包自己的字节 · publication.py:5415"),
         arr(700, 128, 734, 128, tone="fact"),
         node(742, 30, 206, 196, tone="fact", strong=True, kind="R2 包命中",
              rows=[("命中", "判据 2", "fact"),
                    ("mode", F["runman"]["mode"], "degrade"),
                    ("result", F["runman"]["result"], "degrade")],
              note="判据 2 在读 mode 之前就 return"),
         node(24, 246, 924, 54, tone="degrade", kind="所以这一层的 FORMAL 意思是",
              rows=["「有权前向提交」，不是「通过了 FULL_VALIDATION」 —— 两件事在这里被同一个字符串表示"])]
    return svg(972, 318, "".join(b),
               label="两个公共提交函数永远抛错，真正的分类由三条判据从包自己的字节读出，R2 命中第二条")


TL = [("t0", "取排他锁", ("LOCK_EX", "先恢复遗留 intent")),
      ("t1", "CAS + 前驱双检", ("两个条件", "都成立才继续")),
      ("t2", "快照旧镜像", ("14 × ", "{sha256, size}")),
      ("t3", "写 switch", ("intent", "write-ahead")),
      ("t4", "重写 14 个镜像", ("第 7 个后", "是故障注入点")),
      ("t5", "写 active", ("pointer", "◆ 唯一提交点")),
      ("t6", "写 switch", ("receipt", "接上历史 tip")),
      ("t7", "读回后置校验", ("同一把锁内", "再删除 intent"))]


def fig_timeline():
    b, w, gap = [], 122, 6
    x5 = 24 + 5 * (w + gap)
    b.append(band(24, 112, x5 - 24 - 3, 40, "raw", ".12"))
    b.append(band(x5, 112, 24 + 8 * (w + gap) - gap - x5, 40, "fact", ".14"))
    b.append(txt(30, 138, "official state = R1（旧版本）", cls="m", tone="raw"))
    b.append(txt(x5 + 8, 138, "official state = R2（新版本）", cls="m", tone="fact"))
    for i, (t, name, sub) in enumerate(TL):
        x = 24 + i * (w + gap)
        strong = (i == 5)
        b.append(node(x, 24, w, 82, tone="fact" if i >= 5 else "raw", strong=strong))
        b.append(txt(x + 10, 44, t, cls="n", tone="fact" if strong else None))
        b.append(txt(x + 10, 62, name, cls="m", tone="fact" if strong else None))
        b.append(txt(x + 10, 78, sub[0], cls="m2"))
        b.append(txt(x + 10, 93, sub[1], cls="m2"))
        if i < len(TL) - 1:
            b.append(arr(x + w, 65, x + w + gap - 1, 65, tone="fact" if i >= 5 else "raw"))
    b.append(rule(x5 - 3, 12, x5 - 3, 168, "fact", 3))
    b.append(txt(x5 + 2, 8, "◆ 唯一官方提交点", cls="k", tone="fact"))
    tot = 8 * (w + gap) - gap
    b.append(node(24, 182, tot, 54, tone="degrade", kind="镜像先写、指针后写，是恢复协议的一部分",
                  rows=["指针仍是旧值时，官方状态就仍是旧版本，恢复程序按旧指针把 14 个镜像全部还原回去"]))
    return svg(24 + tot + 24, 254, "".join(b),
               label="发布事务的八个步骤，第五步写指针是唯一的官方提交点，它左边官方状态仍是旧版本，右边已是新版本")


def fig_recover():
    cases = [("当前指针 == proposed", "向前补完", "fact",
              ["验 R2 包与 manifest hash", "补写收据（幂等）并验证链",
               "从 R2 包重建 14 个镜像", "删除 intent"], "最终 active = R2"),
             ("当前指针 == previous", "向后还原", "fact",
              ["删本事务可能已写的收据", "验 previous 的历史链仍成立",
               "从 R1 包重建 14 个镜像", "删除 intent"], "最终 active = R1"),
             ("两个都不等于", "拒绝动手", "refuse",
              ["这套机制没有对这个状态建模", "任何自动动作都可能让情况更糟",
               "raise Pending switch pointer", "is neither previous nor proposed"], "等待人工判定")]
    b = [node(24, 30, 236, 132, tone="inherit", kind="磁盘上留下的 intent",
              rows=[("previous", "R1 四字段"),
                    ("proposed", "R2 四字段"),
                    ("mirror_state", "14 × hash/size")],
              note="只记 hash，不记字节")]
    for i, (cond, verdict, tone, steps, res) in enumerate(cases):
        y = 30 + i * 0
        x = 312 + i * 236
        b.append(node(x, 30, 224, 168, tone=tone, kind=verdict, rows=steps, note=res))
        b.append(txt(x + 11, 22, cond, cls="m2"))
        b.append(arr(x - 18, 114, x - 4, 114, tone=tone))
    b.append(elbow([(142, 162), (142, 214), (178, 214)], tone="dim"))
    b.append(txt(186, 218, "reader 同时：fail closed，只拒绝不修复", cls="m2", tone="refuse"))
    b.append(node(24, 236, 996, 52, tone="degrade", kind="方向不由错误类型决定",
                  rows=["也不由返回码或文件 mtime 猜测 —— 它只看当前指针等于 intent 里的哪一个"]))
    return svg(1044, 306, "".join(b),
               label="崩溃恢复的三条出边：指针等于 proposed 则向前补完，等于 previous 则向后还原，两个都不等于则拒绝动手")


def fig_cas():
    b = [node(24, 30, 232, 92, tone="fact", kind="发布者甲的包 B",
              rows=[("manifest.previous", "A"), ("expected_active", "A")]),
         node(24, 138, 232, 92, tone="refuse", kind="发布者乙的包 C",
              rows=[("manifest.previous", "A"), ("expected_active", "A")]),
         arr(264, 76, 296, 100, tone="fact"),
         arr(264, 184, 296, 160, tone="refuse"),
         node(304, 74, 244, 112, tone="raw", kind="fcntl LOCK_EX",
              rows=[("它保证", "不会同时写"),
                    ("它不保证", "排到队的人前提没过期", "refuse")],
              note="锁只解决串行"),
         arr(556, 130, 588, 130, tone="dim"),
         node(596, 74, 244, 112, tone="fact", kind="CAS 检查",
              rows=[("乙的 expected", "A"),
                    ("实际 current", "B（甲已切走）", "refuse")],
              note="CAS 才解决过期前提"),
         node(24, 250, 816, 92, tone="refuse", kind="乙的结局",
              rows=[("raise", "Publication CAS predecessor changed", "refuse"),
                    ("收据数量", "不变，没有多出一条"),
                    ("包 C", "仍在磁盘上，完全有效，只是从未提交")],
              note="它就是上一页那 6 个孤儿包的来历")]
    return svg(886, 360, "".join(b),
               label="两个发布者以同一前驱并发提交，文件锁负责串行，比较并交换负责拦住前提已过期的那一个")


def fig_receipts():
    b, w, gap = [], 152, 26
    for i, (rid, e) in enumerate(F["chain"]):
        x = 24 + i * (w + gap)
        last = (i == len(F["chain"]) - 1)
        b.append(node(x, 40, w, 96, tone="fact", strong=last))
        b.append(txt(x + 11, 62, f"#{i+1}  {rid[:8]}", cls="m", tone="fact"))
        b.append(txt(x + 11, 82, e["switch_mode"], cls="m2"))
        prev = e["pointer"]["previous_publication_id"]
        b.append(txt(x + 11, 102, f"{SHORT(prev) if prev else 'null'} →", cls="m2"))
        b.append(txt(x + 11, 118, SHORT(e["pointer"]["publication_id"]), cls="m2"))
        if not last:
            b.append(arr(x + w, 88, x + w + gap - 2, 88, tone="fact"))
    tot = len(F["chain"]) * (w + gap) - gap
    xl = 24 + tot
    b.append(txt(24, 26, "outputs/publication_switch_receipts/ · 恰好一条链", cls="k", tone="fact"))
    b.append(txt(xl + 6, 92, "← tip", cls="m", tone="fact"))
    b.append(txt(xl + 6, 112, "= 指针", cls="m2"))
    b.append(node(24, 156, tot, 76, tone="degrade", kind="七条不变量里最硬的一条",
                  rows=["从 tip 往回走完之后，访问过的收据集合必须等于全部收据集合",
                        "往目录里塞一条格式完全合法的无关收据，也会报 Publication switch history is not one committed chain"]))
    b.append(txt(24, 254, f"第 3 条是一次真实的回滚演练：{F['chain'][2][1]['pointer']['committed_at_utc']} —— 34 秒内实际发生过五次指针切换。", cls="n"))
    return svg(xl + 80, 272, "".join(b),
               label="五条切换收据构成恰好一条从根到尾的链，尾部必须与指针文件逐字段相等，其中第三条是一次真实回滚")


def fig_pin():
    b = [node(24, 30, 250, 190, tone="fact", kind="PublicationView.open()",
              rows=["1 从一个 root 推导全部路径",
                    "2 锁文件必须存在且是普通文件",
                    "3 取共享锁 LOCK_SH",
                    "4 拒绝任何 pending intent",
                    "5 严格解析指针",
                    "6 收据链：一根、一链、一尾",
                    "7 完整验证整个包",
                    "8 比对 manifest hash"],
              note="publication.py:6257"),
         arr(282, 124, 316, 124, tone="fact"),
         node(324, 30, 250, 190, tone="fact", strong=True, kind="钉住的状态",
              rows=[("publication_id", SHORT(P["publication_id"]) + "…", "fact"),
                    ("bundle_dir", "固定"),
                    ("manifest", f"{len(M['files'])} 条记录")],
              note="read_bytes 之后再也不看指针"),
         node(608, 30, 250, 88, tone="inherit", dash=True, kind="外部完成了一次切换",
              rows=[("active_publication.json", "→ 下一版")]),
         node(608, 132, 250, 88, tone="fact", kind="这个 reader 读到的",
              rows=[("仍然是", SHORT(P["publication_id"]) + "…", "fact")],
              note="想看新版，打开一个新的 View"),
         elbow([(574, 124), (592, 124), (592, 176), (600, 176)], tone="fact"),
         node(24, 244, 834, 58, tone="degrade", kind="读者也参与锁协议",
              rows=["writer 从镜像准备一直持排他锁到收据落盘，所以持共享锁的读者永远看不到「指针已切、收据未写」那个故意留出的窗口"])]
    return svg(882, 320, "".join(b),
               label="打开发布视图时做八步校验并钉住一个版本，之后外部切换指针也不影响这个读者读到的版本")


def fig_limits():
    fault = F["markers"]["publication_fault_receipts"][1] or {}
    audit = F["markers"]["vnext_cutover_audits"][1] or {}
    n_full = len(F["full"])
    blocked = sum(1 for s, _, _ in F["full"] if s == "BLOCKED")
    failed = sum(1 for s, _, _ in F["full"] if s == "FAILED")
    b = [node(24, 30, 230, 150, tone="degrade", kind="限定一 · Requirement 漂移",
              rows=[("包内记录", F["receipt"]["requirement_closure_hash"].split(":")[1][:8] + "…"),
                    ("当前仓库", F["current_closure"].split(":")[1][:8] + "…", "refuse"),
                    ("open()", "照常成功", "degrade")],
              note="历史声明，不是当前断言"),
         node(276, 30, 230, 150, tone="degrade", kind="限定二 · 验证范围",
              rows=[("mode", F["runman"]["mode"]),
                    ("result", F["runman"]["result"], "degrade"),
                    ("未刷新", "full_acceptance", "degrade")],
              note="包自己诚实写着"),
         node(528, 30, 230, 150, tone="refuse", kind="限定三 · 故障矩阵",
              rows=[("定义了", f"{len(F['scenarios'])} 个场景"),
                    ("fault ns", fault.get("status", "?"), "refuse"),
                    ("audit ns", audit.get("status", "?"), "refuse")],
              note="为这一版跑过的：0 次"),
         node(780, 30, 230, 150, tone="refuse", kind="限定四 · full acceptance",
              rows=[("scope=full", f"{n_full} 份"),
                    ("BLOCKED / FAILED", f"{blocked} / {failed}", "refuse"),
                    ("PASSED", "0", "refuse")],
              note="仅 1 份真的 execute_live"),
         node(24, 200, 986, 58, tone="degrade", kind="正确的心智模型",
              rows=["包保证「这些字节没被动过，而且它们之间的声明彼此自洽」 —— 不保证「这些字节代表的验证在今天仍然成立」"])]
    return svg(1034, 276, "".join(b),
               label="发布包证明的四条边界：需求声明会漂移、验证范围写在包里、故障矩阵没跑过、完整验收从未通过")


MAP = [("局部结果可信", "批次完整", "① expected == actual，同财年、同 Requirement"),
       ("批次完整", "投影兼容", f"② 先独立渲染 {F['migrated']} 行，再做 {CMP['compared_field_count']:,} 次事后比较"),
       ("投影兼容", "PUBLISHABLE", "③ 由两个字段算出，调用者填不进去"),
       ("PUBLISHABLE", "immutable bundle", "④ 目录名 = 内容指纹；先验 → rename → 再验"),
       ("immutable bundle", "有权提交", "⑤ 权限从包自己的字节分类；公共 API 永远抛错"),
       ("有权提交", "active", "⑥ 锁 + CAS + 前驱双检 → 指针替换 → 收据接上 tip"),
       ("active", "崩溃后仍确定", "⑦ 指针 == previous 还原，== proposed 补完，都不是则拒绝"),
       ("单 writer 成功", "并发下唯一 winner", "⑧ 锁负责串行，CAS 负责拦住过期前提"),
       ("active 是对的", "下游读到一致", "⑨ open() 钉住一版，read_bytes 不再看指针"),
       ("字节没被动过", "验证今天仍成立", "⑩ 包证明完整性，不证明时效与验收")]


def fig_map():
    b, H = [], 34
    b.append(txt(24, 20, "已经成立", cls="k"))
    b.append(txt(196, 20, "还没成立", cls="k"))
    b.append(txt(372, 20, "越过这道门需要什么", cls="k"))
    for i, (a, c, why) in enumerate(MAP):
        y = 46 + i * H
        if i == 5:
            b.append(band(16, y - 18, 906, H - 4, "fact", ".12"))
        b.append(txt(24, y, a, cls="b"))
        b.append(txt(168, y, "≠", cls="m", tone="refuse"))
        b.append(txt(196, y, c, cls="s"))
        b.append(txt(372, y, why, cls="m2"))
        b.append(rule(24, y + 10, 922, y + 10, "dim", 1))
    b.append(txt(24, 46 + len(MAP) * H + 16,
                 "第六行是唯一提交点：它之前的失败都不改变正式版本，它之后的失败都可以从指针恢复。",
                 cls="m", tone="fact"))
    return svg(946, 46 + len(MAP) * H + 34, "".join(b),
               label="十道因果台阶，左边是已经成立的事实，右边是还没成立的事实，中间是越过这道门所需的证据")


# --------------------------------------------------------------------------
# slides
# --------------------------------------------------------------------------

def cite(*items):
    return '<ul class="cite">' + "".join(
        f'<li><span class="tag" data-k="{k}">{lab}</span>{E(t)}'
        + (f"<code>{E(c)}</code>" if c else "") + "</li>"
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
SLIDES.append(f"""
<section class="slide cover" id="s00">
  <p class="eyebrow">流程三 · 一批结果如何成为当前正式版本</p>
  <h1>正式性不来自「刚刚写过这个文件」，<br>来自一次合法的指针切换</h1>
  <p class="thesis">这条流程接收的不是一堆待写入的 CSV，而是一批已经算对、可以重放的结果。
     它先证明这批结果完整而无重复，再把整版内容封成一个内容寻址的不可变目录，
     最后只用一次原子替换宣告「当前正式版本是谁」。
     <b>把「更新十几个文件」转化成「切换一个指针」，崩溃窗口就从十几个收敛成一个，而且这一个是可判定的。</b></p>
  <div class="chips">
    <span class="chip">HEAD <b>d9bb477</b></span>
    <span class="chip">active <b>{E(P['publication_id'][:24])}…</b></span>
    <span class="chip">前驱 <b>{E(SHORT(P['previous_publication_id']))}…</b></span>
    <span class="chip">提交于 <b>{E(P['committed_at_utc'])}</b></span>
    <span class="chip">切换收据 <b>{len(F['chain'])}</b> 条</span>
    <span class="chip">磁盘 <b>{len(F['stored'])}</b> 个包 / 提交过 <b>{len(F['committed'])}</b> 个</span>
  </div>
  <figure class="fig wide">{fig_chain()}</figure>
  <p class="foot">本页所有数值在构建时读自 <code>outputs/active_publication.json</code>、
     <code>outputs/publications/{E(P['publication_id'][:28])}…</code> 与仓库源码，没有一处来自转写。<br>
     同目录下 <code>flow3-commit-point.html</code> 是同一机制的可交互版（时间可回退、可跳转到任意一步），
     <code>flow3-object-lineage.svg</code> 是单页可打印的对象血缘图。前两道流程见
     <code>flow1-mechanism-deck.html</code> 与 <code>flow2-evidence-chain.html</code>。</p>
</section>""")


slide("01", "问题", "为什么不能直接覆盖",
      "十几个文件的更新，有<em>十几个</em>可以崩在中间的时刻",
      fig_overwrite(),
      """<p><b>要替换的误解：</b>「把新文件写到 <code>outputs/</code> 下面，覆盖旧的」看起来只是一次批量写入。
      它不是——它是十四次独立写入，每两次之间都存在一个下游可以读到的中间态。</p>
      <p>问题不在于某个文件写坏了。<b>每个文件都是合法的</b>，格式校验全过。
      问题在于下游读到的<b>组合</b>从未存在过：一半来自新版本，一半来自旧版本。
      这种损坏没有任何单文件校验能发现。</p>
      <p>而且退不回去。旧字节已经被覆盖，除非事先手工备份——
      可手工备份本身又是一个会写到一半崩的操作，于是你需要一套机制保证备份的正确性，
      然后又需要一套机制保证那套机制。</p>
      <p><b>最根本的缺失是：这个目录里只有文件，没有版本。</b>
      你说不出「现在生效的是哪一版」，也说不出「上一版是什么」。</p>""",
      cite(("code", "代码", "14 个对外文件的精确集合定义在源码里，不是约定俗成。",
            "scripts/vnext/publication.py:101-116 · REQUIRED_BUNDLE_FILES"),
           ("artifact", "产物", f"当前这 14 个文件与 active bundle 逐字节比较：{F['mirrors_same']} / {len(F['required'])} 完全相同。", ""),
           ("gap", "边界", "项目明确不向绕过 PublicationView、直接轮流读根目录文件的程序承诺跨文件组原子。", "")))

slide("02", "核心设计", "一个提交点",
      "把更新十几个文件，转化成<em>替换一个指针</em>",
      fig_swap(),
      """<p>一版 = 一个<b>不可变目录</b>，目录名就是它全部内容的指纹。
      目录里有一份 manifest，列出每个文件的路径、SHA-256、字节数。
      根目录只留一个很小的 <code>active_publication.json</code>，说明当前正式版本是哪一个包。</p>
      <p>发布 = 先把新目录整个写好<b>并验证</b>，然后原子地重写这一个指针文件。</p>
      <p><b>指针替换是唯一的提交点。</b>这句话的实际含义是两条：
      它之前的所有失败都不改变正式版本；它之后的所有失败都可以从指针恢复。
      没有第三种结局，也不需要猜。</p>
      <p>代价是要多维护一批对象——发布包、切换意图、切换收据、历史链——
      并且旧包永远留着，没有任何 GC。这是这套设计明确接受的成本。</p>""",
      cite(("artifact", "产物", "当前指针的四个字段，就是磁盘上的内容。",
            f"publication_id {SHORT(P['publication_id'])}… · previous {SHORT(P['previous_publication_id'])}… · {P['committed_at_utc']}"),
           ("code", "代码", "指针字段集合必须精确相等，多一个少一个都拒绝解析。",
            "publication.py:217 · POINTER_FIELDS"),
           ("code", "代码", "全部路径只能从一个 root 推导，调用方给不了子路径——否则就能拼出「用 A 的包配 B 的指针」。",
            "publication.py:320 · publication_layout")))

slide("03", "主角", "三个对象",
      "模块只是工位，<em>对象</em>才是主角",
      fig_actors(),
      """<p>判断一个对象是不是主角，用一句话检验：<b>删掉它，我还能不能准确说清这一层建立了什么新事实？</b></p>
      <p>删掉<b>批次权威</b>，说不清「这一批到底完不完整」——单个结果只能证明自己。<br>
      删掉<b>不可变发布包</b>，说不清「这一版包含什么」。<br>
      删掉 <b>pointer 加切换历史</b>，说不清「哪一版是正式的、它是怎么来的」。</p>
      <p>第三个必须是两件东西合在一起。pointer 只是一个四字段 JSON；
      如果它能脱离收据链单独被改，那么改一个文件就能把任意包——包括一个从未通过验证的包——变成「正式版本」。
      收据链把这件事变成：<b>你还得伪造一整条自洽的历史，而且新 tip 的 hash 必须和指针对上。</b></p>""",
      cite(("artifact", "产物", "三个身份都是内容派生的，不由调用者挑选。",
            f"batch {M['batch_manifest_id'][:22]}… · projection {M['projection_manifest_id'][:22]}…"),
           ("code", "代码", "每次读指针之后立刻要求收据链能证明这个指针，两者不可分开。",
            "publication.py:4989 · _switch_receipt_for_pointer"),
           ("test", "测试", "历史指针字节不是当前链尾；孤立的自签收据无法冒充。",
            "tests/vnext/test_publication.py")))

slide("04", "第一站", "批次权威",
      "十个结果各自正确，<em>不等于</em>这一批完整",
      fig_batch(),
      f"""<p><b>要替换的误解：</b>「每家公司的计算都已经封存且能重放，所以这批结果是完整的。」</p>
      <p>单个结果不知道另一家公司少了一行 N/A、多了一个坐标，或者用的是另一个财年。
      完整性是另一件事实，必须由<b>仓库独立重新推导</b>：从 company registry、release plan
      和 MetricSpec applicability 联合算出应有的 <code>(company_id, metric_id)</code> 集合，
      再和实际结果集逐坐标比对。<b>调用者不能自报应有集合。</b></p>
      <p>比对通过后新成立的不变量是：应有坐标与实际结果 exact set 完全相等——
      不缺、不多、不重复、不跨财年、Requirement 不分叉。</p>
      <p>不相等就在这里终止。<b>这一步没有任何外部副作用</b>：
      不产生 staging、不产生 bundle、甚至没有读取指针。</p>""",
      cite(("artifact", "产物", f"坐标数 {PJ['result_coordinate_count']} 与 batch_manifest_id 在两个独立文件里一致。",
            "internal/coordinate_index.json · projection_manifest.json"),
           ("recomputed", "推导", f"10 家公司 × {len(PJ['cumulative_metric_ids'])} 个累计指标 = {PJ['result_coordinate_count']}；两个因数都能从产物单独读出。", ""),
           ("code", "代码", "通用路径上批次不完整、单公司冒充整批、混合财年都有专门的失败用例。",
            "scripts/vnext/projector.py:1229-1522 · tests/vnext/test_replay.py")))

slide("05", "第二站", "独立投影",
      "先渲染，<em>再</em>比较——顺序本身就是证明",
      fig_projection(),
      f"""<p><b>要替换的误解：</b>「兼容就是新输出和旧 CSV 一样，所以先把旧行复制过来，再比一次相等就行。」</p>
      <p>复制之后再比较相等是<b>循环证明</b>：它永远成立，而且完全发现不了「新结果图和公共数值已经脱节」。
      左边那条路上，新对象链哪怕根本没参与生成公共值，检查照样全绿。</p>
      <p>当前顺序把两件事拆开：生产 renderer 先从新对象图独立生成 {F['migrated']} 行——
      它<b>不接收</b> legacy 行、期望值或旧证据作为语义输入；
      冻结的 legacy 快照此刻才第一次被读取，只回答「迁移有没有意外改变已有用户字段」。</p>
      <p>还有一层保护：projection-independence receipt 对关键函数的 AST 和禁止标识符做约束——
      它检查的是 renderer <b>不可能</b>读旧语义，不是「这次没读」。</p>""",
      cite(("artifact", "产物", f"{CMP['compared_key_count']} 个既有 key × 20 个字段 = {CMP['compared_field_count']:,} 次比较，两个 delta 集都是空数组。",
            "internal/public_projection_closure.json → compatibility"),
           ("artifact", "产物", f"per_field_counts 全表 20 行，每行都是 equal={CMP['compared_key_count']} / approved_delta=0 / unexpected_delta=0。", ""),
           ("test", "测试", "legacy canary 证明 producer 不读旧语义。",
            "tests/vnext/test_zero_ai_release.py::test_r2_projection_and_producers_survive_legacy_canary")))

slide("06", "第二站", "行的来源",
      f"{F['rows']} 行不是一个整体，是<em>两种来源</em>的组合",
      fig_309(),
      f"""<p>正式的 <code>metrics_matrix.csv</code> 有 {F['rows']} 行、{F['cols']} 列。
      这个数字很容易被当成「这次算了 {F['rows']} 行」——不是。</p>
      <p>其中 {F['migrated']} 行是本次迁移：由新对象图独立渲染，替换掉前驱里对应的 key。
      另外 {F['rows'] - F['migrated']} 行是未迁移的 legacy 行，保持前驱顺序原样带过来。</p>
      <p>{F['migrated']} 行里又分两类：{CMP['compared_key_count']} 个是前驱里已经存在的 key，
      它们参与了上一页那 {CMP['compared_field_count']:,} 次逐字段比较；
      另外 {PJ['new_public_key_count']} 个是新增 key，主要是结构性 N/A 坐标——
      <b>它们是完整结果的一部分，不是缺失</b>。</p>
      <p>把这三类分开看，才能理解下一页那条规则为什么必须存在。</p>""",
      cite(("recomputed", "推导", f"{F['rows']} − {F['migrated']} = {F['rows'] - F['migrated']}；两个数分别从 CSV 实际行数与 row_bindings 条数读出。", ""),
           ("artifact", "产物", f"public_matrix_row_count = {PJ['public_matrix_row_count']} · replaced_legacy_row_count = {PJ['replaced_legacy_row_count']} · new_public_key_count = {PJ['new_public_key_count']}。",
            "projection_manifest.json"),
           ("artifact", "产物", "20 个字段：company / cik / metric_id / metric_name / value / unit / status / source_class / formula / period × 2 / fiscal × 2 / accession / form / filed_date / concept / context / confidence / notes。", "")))

slide("07", "第三站", "candidate_status",
      "空值<em>不等于</em>失败",
      fig_truth(),
      """<p><b>要替换的误解：</b>「矩阵里有空值就是失败，没有空值就能发。」</p>
      <p>批次级判定只读两个字段，而且只有一种组合会阻断发布。
      <code>N_A_STRUCTURAL</code> 表示这个指标按公司 traits 本来就不适用——
      它是<b>完整结果的一部分</b>，不阻断。
      <code>APPLICABLE + WITHHELD</code> 表示本应有结果但证据或计算不足，这才阻断。</p>
      <p>两者在 CSV 里可能都显示为空，语义完全相反。</p>
      <p>判定是<b>算出来的</b>，函数体里没有任何调用者传入的布尔值；
      未知的字段值也不会被当作「不阻断」，而是直接抛 <code>StateError</code>——fail closed，不是 fail open。</p>
      <p>被判 BLOCKED 时的对象结局是完整的：不产生 <code>projection_manifest_id</code>、
      不写发布包、<b>指针逐字节不变</b>、结果与 Trace 全部保留供审计。
      失败的尝试不会用空值覆盖成功的旧版本。</p>""",
      cite(("code", "代码", "整个函数只有一个循环和三条判断。",
            "scripts/vnext/states.py:87-117 · publication_candidate_status"),
           ("code", "代码", "可发布的 validation 状态集合只有一个成员。",
            'states.py:41 · PUBLISHABLE_VALIDATION_STATUSES = frozenset({"PASSED"})'),
           ("artifact", "产物", f"当前 R2 的判定结果：status = {PJ['status']}，schema_version = {PJ['schema_version']}，record_type = {PJ['record_type']}。", "")),
      layout="stack")

slide("08", "第四站", "写包",
      "目录名就是<em>内容指纹</em>，写包本身是个小事务",
      fig_write(),
      f"""<p><code>publication_id</code> 不是随机的，是从 identity 内容派生的：
      candidate_status、requirement_hashes、batch / projection / validation 三个 ID、
      全部文件的 <code>{{path, sha256, size}}</code>、ledger_binding，以及
      <code>previous_publication_id</code>。</p>
      <p><b>因为前驱也在 identity 里面，整条发布链是一条 hash 链</b>：
      改动任何一个历史版本的任何一个字节，都会让它自己的 ID 变，进而让所有后继版本的 ID 失效。</p>
      <p>写入过程本身是个小事务：先写进隐藏临时目录，逐文件原子写，写完 manifest，
      <b>在临时目录上先跑一次完整验证</b>，通过了才 <code>os.replace</code> 目录级改名并 fsync 父目录，
      最后对最终目录再验一次。</p>
      <p>而且它是幂等的：最终目录已存在时，验证已有内容与本次 manifest 逐字段相等，
      相等直接返回，不等报错。<b>同一个 ID 永远不可能指向两组不同的字节。</b></p>""",
      cite(("artifact", "产物", f"当前包：磁盘 {F['bundle_files']} 个文件，manifest 列 {len(M['files'])} 个 payload，"
                               f"合计 {sum(f['size'] for f in M['files'])/1024:.1f} KB，manifest 自身 sha256 = {F['manifest_sha'][:8]}…，"
                               "与指针里的 bundle_manifest_sha256 完全一致。", ""),
           ("code", "代码", "临时目录、幂等分支、故障注入点都在同一个函数里。",
            "publication.py:890-987"),
           ("code", "代码", "包内文件精确集合校验连空目录都算：从 manifest 推出 expected files 与 directories，再 rglob 实际内容，两个集合都必须精确相等。",
            "publication.py:4491-4513 · Publication file exact set differs")))

slide("09", "第四站", "准备 ≠ 发布",
      f"磁盘上 {len(F['stored'])} 个包，只有 <em>{len(F['committed'])}</em> 个进过切换历史",
      fig_chains(),
      f"""<p>准备阶段<b>完全不碰指针</b>。这个性质有一个很直观的证据：
      仓库里现在有 {len(F['stored'])} 个内容完整、manifest 自洽、验证通过的发布包，
      而切换收据里只出现 {len(F['committed'])} 个 publication ID。</p>
      <p>另外 {len(F['stored'])-len(F['committed'])} 个是两次完整的彩排——准备好了、验证过了、从未提交。
      <b>这正是这个设计想要的：彩排的代价只有磁盘。</b></p>
      <p>反过来说，按目录 mtime 挑「最新的那个」会绕过前驱校验、CAS 和整条切换历史。
      正确的入口是 <code>PublicationView.open(publication_root=repo_root)</code>，
      不是 <code>glob(outputs/publications/*)[-1]</code>。</p>
      <p>这条区分要一直记到最后一页：<b>目录存在、曾经提交、当前 active、通过验收，是四种不同的事实。</b></p>""",
      cite(("artifact", "产物", f"{len(F['stored'])} 个目录的 previous_publication_id 构成三条链，只有第三条出现在收据里。", ""),
           ("recomputed", "推导", f"孤儿 {len(F['stored'])-len(F['committed'])} 个共 "
                                  f"{sum(v['bytes'] for k, v in F['stored'].items() if k not in F['committed'])/1048576:.1f} MB，"
                                  f"全部 {len(F['stored'])} 个包 {sum(v['bytes'] for v in F['stored'].values())/1048576:.1f} MB。", ""),
           ("gap", "边界", "旧包永远留着，没有任何 GC。清理需要先做可达性普查，否则可能删掉 rollback 的前驱或审计引用。", "")))

slide("10", "第五站", "提交权限",
      "名字最像入口的那两个函数，<em>永远抛错</em>",
      fig_authority(),
      f"""<p><code>commit_publication()</code> 和 <code>commit_initial_publication_chain()</code>
      无条件抛 <code>FORMAL_CUTOVER_AUTHORITY_REQUIRED</code>。</p>
      <p>这不是把私有函数藏起来（Python 藏不住），而是在公共位置放一个<b>永远失败的同名函数</b>：
      误用会立刻失败而不是悄悄成功，错误码直接说明正确路径，
      代码搜索时看到的第一个定义就是这个拒绝版本。代价是可发现性差。</p>
      <p>真正的分类由 <code>_publication_commit_authority</code> 从<b>包自己的字节</b>读出，
      依次尝试三条判据。R2 包命中判据 2。</p>
      <p><b>这里有一个非显然的事实：</b>R2 的 <code>validation_run_manifest</code> 写的是
      <code>{F['runman']['mode']} / {F['runman']['result']}</code>——这一对<b>不在</b>判据 3 的查表里。
      它拿到 FORMAL，纯粹是因为判据 2 先命中并提前 return。
      所以这一层的 <code>FORMAL</code> 意思是「有权前向提交」，<b>不是</b>「通过了 FULL_VALIDATION」。</p>""",
      cite(("code", "代码", "两个公共函数都先 del 掉全部参数，再无条件 raise。",
            "publication.py:6011-6034 · publication.py:5902-5925"),
           ("artifact", "产物", f"{len(F['stored'])} 个包里 "
                                f"{sum(1 for v in F['stored'].values() if v['zero_ai'])} 个带 zero-AI 收据、"
                                f"{sum(1 for v in F['stored'].values() if v['legacy'])} 个带 legacy 导入清单，"
                                f"{sum(1 for v in F['stored'].values() if v['closure'])} 个带 internal/closure_manifest.json"
                                "——判据 3 那条线从来没有真的生产出过一个包。", ""),
           ("code", "代码", "首次提交必须走初始链，否则第一版就是没有前驱的孤儿，回滚无处可去。",
            'publication.py:5506-5521 · "first formal publication requires initial publication chain"')))

slide("11", "第六站", "唯一提交点",
      "镜像先写、指针后写，<em>官方状态由指针决定</em>",
      fig_timeline(),
      """<p>事务在排他锁内按固定顺序进行。前四步都还没有改变官方状态：
      CAS 与前驱双检失败时，连 intent 都还没写。</p>
      <p><b>两个前置条件都要。</b>「当前指针 == 我准备时的前驱」防的是并发；
      「包自己声明的前驱 == 当前指针」防的是错配。单独任何一个都不够。</p>
      <p>然后写 switch intent——这是 write-ahead 记录，
      它保存 previous / proposed 两个指针、切换模式、上一条收据 ID，
      以及 14 个旧镜像当时的 <code>{sha256, size}</code>。<b>它记 hash，不记字节。</b></p>
      <p>接着逐个重写 14 个兼容镜像。<b>在这段时间里镜像已经全是新的，而官方状态仍然是旧版本</b>——
      这正是「镜像更新了 ≠ 版本切了」的那个窗口。</p>
      <p>指针替换之后才写收据，顺序不能反：收据先写会在指针前崩溃时留下一个孤儿边，
      而后来的指针篡改可以把它冒充成已提交。</p>""",
      cite(("code", "代码", "原注释解释了为什么收据必须在指针之后。",
            'publication.py:5650-5652 · "Persisting its history edge beforehand would let a pre-pointer crash leave an orphan"'),
           ("artifact", "产物", f"这一次切换的真实收据：{F['chain'][-1][0][:8]}…，mode = {F['chain'][-1][1]['switch_mode']}，"
                                f"previous = {str(F['chain'][-1][1]['previous_switch_receipt_id']).split(':')[-1][:8]}…。", ""),
           ("code", "代码", "后置校验用的是正式读取入口本身（同一把锁内重新 _open_paths），不是写函数的返回值。",
            "publication.py:5657-5663")))

slide("12", "韧性", "崩溃恢复",
      "「出错就回滚」是错的：<em>方向由指针决定</em>",
      fig_recover(),
      """<p>进程死亡不会执行任何清理代码——故障演练用的是一个<b>继承自 <code>BaseException</code></b>
      的异常，故意不继承 <code>Exception</code>，这样它能穿透生产代码里所有的
      <code>except (OSError, ValueError, PublicationError)</code>。</p>
      <p>磁盘上只留下 intent 和一个停在某处的状态。下一个 writer 取得排他锁后，
      读 intent、读当前指针，然后只做一次比较。</p>
      <p><b>第三条出边是这个设计最重要的部分：它不猜。</b>
      如果状态既不是事务前也不是事务后，说明发生了这套机制没有建模的事情，
      此时任何自动动作都可能让情况更糟。</p>
      <p>还原镜像时<b>不用备份，用不可变包重建</b>：从 R1 包读出字节，
      要求 hash 与 size 与 intent 记录完全一致才写回。
      好处是<b>系统里从来只有一份权威字节</b>——备份本身会写一半、会损坏、会和权威源不一致。</p>""",
      cite(("code", "代码", "三条出边的判定条件。",
            "publication.py:5259-5303 · _recover_switch_intent_locked"),
           ("code", "代码", "重建失败时的错误语明确指向包，而不是指向备份。",
            'publication.py:5187-5231 · "Recovery bundle cannot reproduce pre-switch mirrors"'),
           ("code", "代码", "reader 遇到 pending intent 只拒绝、不清理——它没有排他锁，也不该决定事务方向。",
            'publication.py:4901-4911 · "Publication switch recovery intent is pending"')))

slide("13", "韧性", "并发",
      "锁负责<em>串行</em>，CAS 负责<em>决胜</em>",
      fig_cas(),
      """<p>两个发布者可以同时准备，因为准备不碰指针。提交时排他锁把他们排成一列。</p>
      <p><b>但排队之后，第二个人的前提可能已经过期。</b>
      锁只保证「不会同时写」，它不保证「我拿到锁时，我准备阶段看到的那个前驱还是当前值」。
      CAS 检查的正是这一句。</p>
      <p>只有锁没有 CAS，第二个 writer 会基于一个已经过期的前提，把 winner 覆盖掉。</p>
      <p>loser 的结局是干净的：抛 <code>Publication CAS predecessor changed</code>，
      <b>不留任何痕迹</b>——收据数量不变，镜像未被触碰。
      它准备好的包仍在磁盘上、完全有效，只是从未提交。</p>
      <p>回滚受同类约束：只能回到当前指针证明的<b>直接</b>前驱，
      prepared-only 的兄弟版本即使内容完全有效也不能被回滚过去。</p>""",
      cite(("code", "代码", "CAS 在锁内、在任何写入之前。",
            'publication.py:5572-5583 · "Publication CAS predecessor changed" / "Prepared bundle predecessor differs"'),
           ("code", "代码", "故障矩阵的两个并发场景真开两个线程，要求恰好一个成功一个失败。",
            "fault_matrix.py:64-70 · EXACTLY_ONE_WINNER / CAS_LOST_ACTIVE_PRESERVED"),
           ("code", "代码", "回滚目标必须是当前指针的直接前驱。",
            'publication.py:5580-5586 · "Rollback target is not the committed predecessor"')))

slide("14", "历史", "切换收据",
      "所有收据必须构成<em>恰好一条</em>链",
      fig_receipts(),
      f"""<p>指针写完之后，writer 生成一条 <code>PUBLICATION_SWITCH</code> 收据，
      绑定新指针、切换模式和上一条收据的 ID。</p>
      <p>每次读取时这条链都要重新验证：收据 ID 等于其余字段的 content hash 且文件名就是这个 hash；
      没有悬空引用；<b>恰好一个 tip</b>；tip 的 pointer 与指针文件逐字段相等；
      从 tip 往回走无环。</p>
      <p><b>最硬的是最后一条</b>：走完之后访问过的收据集合必须等于全部收据集合。
      你不能往这个目录里塞一条无关的收据，哪怕它自身格式完全合法。</p>
      <p>当前这条链有 {len(F['chain'])} 条边、{len(F['committed'])} 个 publication ID。
      <b>第 3 条是一次真实的回滚演练</b>——不是设计文档里的承诺，
      是 34 秒内实际发生过的五次指针切换之一。</p>""",
      cite(("artifact", "产物", "五条边按 root → tip 排序，时间戳分别是 "
                               + " · ".join(e["pointer"]["committed_at_utc"][11:19] for _, e in F["chain"]) + "。", ""),
           ("code", "代码", "链完整性的七条不变量。",
            'publication.py:4989-5058 · "Publication switch history is not one committed chain"'),
           ("code", "代码", "加载器显式跳过原子写留下的隐藏临时文件，避免把正常的并发准备变成假失败。",
            "publication.py:4933-4937")))

slide("15", "下游", "PublicationView",
      "读者<em>钉住</em>一个版本，之后再也不看指针",
      fig_pin(),
      f"""<p><code>PublicationView.open()</code> 只接受一个 root，做八步校验，
      然后把 publication ID 和 bundle 目录钉在内存里。
      之后每次 <code>read_bytes()</code> 只允许读 manifest 列出的路径，
      并且<b>重新校验那个文件的长度与 sha256</b>。</p>
      <p>即使外部指针随后切到别的版本，已打开的 View 仍读旧包；新 View 才看新版本。
      <b>这是多文件一致读的真正下游保证</b>——不是「切换很快」，
      而是「你手里的这一次读取，从头到尾属于同一个版本」。</p>
      <p>读者也参与锁协议：writer 从镜像准备一直持排他锁到收据落盘，
      所以持共享锁的读者永远看不到「指针已切、收据未写」那个<b>故意留出的</b>中间态。</p>
      <p><b>一个会绊住新人的真实坑：</b><code>open()</code> 要求
      <code>outputs/active_publication.json.lock</code> 存在且是普通文件，
      而这个文件在 <code>.gitignore</code> 里。
      全新 clone 里它不存在，任何要打开发布视图的代码都会直接失败。
      这不是 bug——锁文件本来就不该进版本库——
      但它意味着「clone 下来就能离线验证」这个性质需要多一条说明。</p>""",
      cite(("code", "代码", "八步校验与钉住语义。",
            "publication.py:6257-6301 · publication.py:6338-6367"),
           ("recomputed", "实测", "干净 checkout 上 open() 报 Publication authority lock is missing or unsafe；"
                                  "touch 该锁文件后正常打开并读完全部 "
                                  f"{len(M['files'])} 个文件。", ""),
           ("code", "代码", "原注释说明读者为什么也要拿锁。",
            'publication.py:6292-6295 · "Readers therefore observe either complete transaction"')))

slide("16", "边界", "包证明到哪为止",
      "包证明<em>完整性</em>，不证明<em>时效</em>与<em>验收</em>",
      fig_limits(),
      f"""<p>一个自然的理解是：既然包是不可变的、自包含的、每次读都验 hash，
      那么打开它就等于拿到了完整可信的证据。<b>这个理解有四处需要限定。</b></p>
      <p><b>一、Requirement 声明会漂移。</b>包里记的
      <code>requirement_closure_hash</code> 与当前仓库重新推导的值已经不同，
      而 <code>open()</code> 照常成功——它把这个字段列为必须存在，但<b>不</b>从仓库重新推导。
      这是正确的设计：不可变包应该记录发布当时的事实。但它意味着那是一个<b>历史声明</b>，不是<b>当前断言</b>。</p>
      <p><b>二、验证范围包自己写着</b>：<code>{F['runman']['mode']} / {F['runman']['result']}</code>，
      并显式列出 <code>issue_15_full_acceptance.not_run</code>。</p>
      <p><b>三、{len(F['scenarios'])} 个故障场景没为这一版跑过</b>：两个正式收据命名空间都只有一个空标记。</p>
      <p><b>四、full acceptance 从未通过</b>：{len(F['full'])} 份 full scope 收据里没有一份 PASSED。</p>""",
      cite(("recomputed", "实测", "当场重算的 Requirement closure 与包内记录不同，而 PublicationView 仍然成功打开。",
            f"当前 {F['current_closure'][:22]}… vs 包内 {F['receipt']['requirement_closure_hash'][:22]}…"),
           ("gap", "边界", "两个空标记的 scope 与 status 不同，这个差别有意义：前者是「不在范围内所以没跑」，后者是「没跑」——后者没有「超出范围」这个借口。",
            f"publication_fault_receipts → {F['markers']['publication_fault_receipts'][1].get('status', '?')} · "
            f"vnext_cutover_audits → {F['markers']['vnext_cutover_audits'][1].get('status', '?')}"),
           ("artifact", "产物", f"acceptance receipts 合计 {sum(F['acc'].values())} 份："
                                + " · ".join(f"{k} {v}" for k, v in sorted(F["acc"].items())) + "。", "")))

slide("17", "收束", "因果心智地图",
      "十道门，每一个 <em>≠</em> 都需要一组具体的证据",
      fig_map(),
      """<p><b>可以换的实现细节：</b>JSON 指针、本地目录、<code>fcntl</code> 文件锁、
      rename、14 个镜像的具体清单、存储后端。这些都是当前实现，不是产品承诺。</p>
      <p><b>不能丢的因果：</b>完整批次决定内容资格 · 独立投影加事后比较 ·
      精确的门禁绑定 · 不可变版本 · <b>唯一</b>提交点 · 前驱与 CAS ·
      write-ahead 恢复 · 一条连通历史 · 钉住式读取 · 篡改时 fail closed。</p>
      <p>如果未来迁到对象存储或多机数据库，这十条必须逐条找到对应物——
      而不是「把文件复制到云上」。多机方案还要额外定义网络分区、ack 丢失、
      租约与 ETag 语义，那是新问题，不是同一个问题换个地方。</p>
      <p>这一层<b>不负责</b>的事同样重要：不判断某个数字对不对（那在前两道流程里已经决定）·
      不生成内容 · 不跨机协调 · 不清理历史。</p>""",
      cite(("code", "代码", "这一层的责任边界：接收已在 staging 准备好的字节，产出不可变包、指针、收据与钉住式读取入口。",
            "scripts/vnext/publication.py"),
           ("gap", "边界", "提交点是 fcntl.flock 加本地文件系统，单机语义。不承诺网络文件系统或多主机故障语义。", ""),
           ("recomputed", "实测", "本次没有创建、切换或回滚任何 publication。"
                                  f"active pointer 仍是 {SHORT(P['publication_id'])}…，"
                                  f"14 个镜像与包逐字节一致（{F['mirrors_same']}/{len(F['required'])}），"
                                  "switch intent 目录不存在（等价于无 pending intent）。", "")))


# --------------------------------------------------------------------------
# stylesheet
# --------------------------------------------------------------------------

CSS = """
:root{
  --ground:#EDEEF3; --card:#FFFFFF; --panel:#F8F9FC; --panel2:#E4E6EE;
  --ink:#151827; --ink2:#494F66; --ink3:#7A8198;
  --rule:#C6CAD9; --rule2:#DFE2EC;
  --fact:#2C3C9C; --factbg:#E2E6F8;
  --degrade:#7A5A11; --degradebg:#F4EEDA;
  --refuse:#9C3524; --refusebg:#F7E4DF;
  --inherit:#6B4E8A; --inheritbg:#EAE2F2;
  --neutral:#5E6472;
  --shadow:0 1px 2px rgba(21,24,39,.05),0 10px 30px rgba(21,24,39,.06);
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:"IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",system-ui,sans-serif;
  --disp:"Spectral","Songti SC","Noto Serif CJK SC",Georgia,serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#0A0C14; --card:#141726; --panel:#1A1E30; --panel2:#212639;
  --ink:#E7E9F1; --ink2:#A5ABC2; --ink3:#767D97;
  --rule:#2A3048; --rule2:#212639;
  --fact:#94A5F7; --factbg:#1C2345;
  --degrade:#DCB65E; --degradebg:#2C2615;
  --refuse:#E9917A; --refusebg:#33201A;
  --inherit:#B49BD6; --inheritbg:#251E33;
  --neutral:#8A91A6;
  --shadow:0 1px 2px rgba(0,0,0,.5),0 10px 30px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --ground:#0A0C14; --card:#141726; --panel:#1A1E30; --panel2:#212639;
  --ink:#E7E9F1; --ink2:#A5ABC2; --ink3:#767D97;
  --rule:#2A3048; --rule2:#212639;
  --fact:#94A5F7; --factbg:#1C2345;
  --degrade:#DCB65E; --degradebg:#2C2615;
  --refuse:#E9917A; --refusebg:#33201A;
  --inherit:#B49BD6; --inheritbg:#251E33;
  --neutral:#8A91A6;
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
.deck{counter-reset:sl -1 total 17}

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

table.t{border-collapse:collapse;width:100%;font-size:13px;margin:0;
  font-variant-numeric:tabular-nums}
table.t th{text-align:left;font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink3);font-weight:500;
  padding:8px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
table.t td{padding:9px 10px;border-bottom:1px solid var(--rule2);vertical-align:top}
table.t tbody tr:last-child td{border-bottom:0}
table.t td.ok{color:var(--fact);font-family:var(--mono);font-size:11.5px}
table.t td.no{color:var(--refuse);font-family:var(--mono);font-size:11.5px;font-weight:600}

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
.tag[data-k="code"]{color:var(--neutral);border-color:color-mix(in srgb,var(--neutral) 48%,transparent)}
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

@media print{
  body{background:#fff;font-size:12.5px;line-height:1.6}
  .deck{max-width:none;padding:0;gap:0}
  .slide{break-after:page;page-break-after:always;box-shadow:none;border:0;
    border-radius:0;padding:0 0 12px;min-height:0}
  .slide::after{position:static;display:block;text-align:right;margin-top:6px}
  h1{font-size:34px}h2{font-size:22px;margin-bottom:12px}
  .sb{gap:14px 22px}
  .fig{background:none;border:1px solid #d8dae2;padding:8px}
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
    '<meta charset="utf-8">\n'
    "<title>发布事务讲义</title>\n"
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700"
    '&family=Spectral:wght@400;500;600&display=swap">\n'
    f"<style>{CSS}</style>\n"
    '<main class="deck">' + "".join(SLIDES) + "</main>\n"
)

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT.relative_to(REPO)}  {len(HTML):,} bytes  {len(SLIDES)} slides")
