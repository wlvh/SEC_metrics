# D04 原件语义路线：新来源组件与实际材料验收

本轮仅新增两个独立文件，不改 V13 规则、Spec、CI 或历史证据。13 项组件测试通过；十家公司普通输入均完成保存和全新 Python 进程从原件重建。没有创建 Run、冻结、原生 Result、EvidenceCheck、Review 或 publication；provider / paid / SEC = 0 / 0 / 0。

## 业务结论与范围

原批准定义 `02_指标定义_SEC_10公司单年指标.md` 第 479–483 行允许经检查确认“未披露持续经营疑虑”成为正常定性结果；这不等于可以把关键词未命中变成该结果。当前 SourceStrategy 的 D04 是 auditor_report / structured_first_ai_fallback / CLOSED_WORLD；Issue #15 原合同的 CLOSED_WORLD 仍要求完整语义覆盖。

对十家公司当前原始年报的 native concept 全集按 GoingConcern / substantial-doubt 名称筛查均为 0。此项只是可疑概念清单，不是已批准 taxonomy 中布尔事实的穷尽语义解释。新组件对任何命中概念保留 namespace、原值和完整 context，标记 UNMAPPED_CONCEPT_REQUIRES_SEMANTIC_AUTHORITY，不把 false、零或缺事实当无疑虑。

旧去向导航找到的 going-concern 词语仅 Pfizer 一处，实际是 Seagen 收购商誉的 going-concern element。新组件额外保留 ability-to-continue 线索，因此还保留 Ford 招聘能力与 Ford Credit 融资能力、Paramount 吸引订阅者、Enphase 供应商投资能力的原文；这五项（Ford 两段）都不是已确认本公司当前持续经营疑虑。它们必须作为后续模型的负例，而不是被正向计数。

十家公司实际共有 17 段审计报告导航：10 段财务报表审计（部分同时包含内控意见）、6 段单独内控审计、1 段 Paramount 前身报告。源内主体和期间人工核对可定位十段本期财务审计。新组件严格机械名称匹配仅 8/10；Marriott DEI 的 /MD/ 后缀和 Ford 的 Co / Company 差异保留未决，没有加入公司特例。所有报告、两种名称及全文仍在输入中，未决名称不会丢弃来源或冒充审阅结论。

## 新组件 API

- `prepare_ordinary_going_concern_source(repo_root, company_id)`：仅由正常保存输入发现最新普通年度，纳入全部同期间 10-K/A，重验完整现有保存来源准入。返回 prepared annual identity、全部 proof、逐文件来源组件和完整文本输入分组。
- `verify_ordinary_going_concern_source(packet, repo_root, company_id)`：不信 caller 的重签哈希；从同一普通来源发现和原件重建全部内容后完全比较。
- `inspect_going_concern_source(...)` / `verify_going_concern_source(component, ...)`：用于独立原件和隔离反例的低层 API；明确 `source_admission=NOT_GRANTED_BY_COMPONENT_API`，不授来源准入或来源信用。
- 所有 source units 按原始块顺序覆盖整个可见文档；每块保留原文，每份 document 保留字节起止及 raw_span_sha256。单个超 65,536 字节的块不会截断，显式 oversized。分组不是模型请求，source_payload_bytes 不是 token 计数或调用预算。
- Named + dated 的完整疑虑 / 否定句只形成 DIRECT_SOURCE_DECLARATION_CANDIDATE；report opening 的主体 / 日期相符也不代表已验证作者身份或语义。`semantic_review_required=true`、`not_disclosed_confirmed=false` 一直保留。

## 十公司实际索引

表中分组和字节数包含已保存的本期修订年报；日期从正常输入和原件取得。全新进程是源码当前安装下的来源包重建，不是 FROZEN Run portable credit。

| 公司 | 文档 | 原文块 | 可见字符 | UTF-8 源载荷字节 | 分组 | 冷重建 |
|---|---:|---:|---:|---:|---:|---|
| marriott_international | 1 | 1965 | 271428 | 291503 | 5 | PASS |
| southwest_airlines | 2 | 2704 | 559947 | 588768 | 10 | PASS |
| ford_motor_company | 1 | 4176 | 630830 | 674750 | 11 | PASS |
| pfizer | 1 | 4507 | 629666 | 676788 | 11 | PASS |
| jpmorgan_chase | 1 | 11146 | 1153348 | 1273478 | 20 | PASS |
| salesforce | 1 | 2392 | 403488 | 427903 | 7 | PASS |
| lumen_technologies | 1 | 4488 | 474832 | 521332 | 8 | PASS |
| macys | 1 | 2165 | 290303 | 312003 | 5 | PASS |
| paramount_skydance_paramount_global | 2 | 5188 | 663595 | 717988 | 12 | PASS |
| enphase_energy | 1 | 2709 | 454845 | 483352 | 8 | PASS |

合计 12 份文件、97 个分组、5,967,865 UTF-8 源载荷字节；实际 oversized 分组为 0。以上统计由材料索引求和，之前进度消息的 107 已更正为 97。

日期、原件路径、原件 SHA、审计开头精确字节和逐公司实际 cold command / exit status 均在 [index.json](/tmp/sec_metrics_issue28_continuous/pr43-review/d04-ten-source-material-v1/index.json)。12 份来源包括 Southwest 与 Paramount 的当前 10-K/A。

## 精确原文反例

Pfizer FY2025，accession 0000078003-26-000026，申报日期 2026-02-26：[原 HTML](/Users/lyuhongwang/Developer/SEC_metrics/evidence/request_attempts/17/175e07c21ee258eddd9952e443d34df2a297d0c38e2d1312dff0a64a31c401ab/pfe-20251231.htm)。block 2356，bytes [2598750,2599100)，raw span SHA 810c4a13fe23089ad1b602b0c13ad9b46d8559a13cf73cb9c48089789265b3e2；原文是“the value of the going-concern element of Seagen’s existing businesses”及收购净资产比较。它不能证明 Pfizer 本期存在疑虑，也不能单凭排除此段就证明全文没有疑虑。

Paramount FY2025：[原 HTML](/Users/lyuhongwang/Developer/SEC_metrics/evidence/request_attempts/4c/4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d/psky-20251231.htm)，accession 0002041610-26-000011，2026-02-25 申报。当前 Successor opening bytes [1657516,1659750)，主体 Paramount Skydance Corporation，资产负债表 2025-12-31、经营期间 2025-08-07 至 2025-12-31。前身 opening bytes [1683293,1685274)，主体 Paramount Global，资产负债表 2024-12-31、经营期间到 2025-08-06。前身不能因为出现在同份 10-K 或同为 Company 就继承当前主体身份。当前补充年报 accession 0001140361-26-016758、2026-04-24 一并供语义检查。

## 首次失败、修复与验证

第一次组件测试保留在 component-tests-first.log：Paramount source unit 经现有 canonical NFC 改写原字符后覆盖比较失败。实际首差是 block 344 结尾 U+037E（Greek question mark）被规范成 ASCII semicolon，不是业务数字或原件身份变化。修复仅在新组件保留原始 Unicode JSON 字符、另存精确 UTF-8 payload SHA；规范内容 ID 仍复用既有算法。第二轮发现 native context 的 mappingproxy 不能直接 JSON 保存，保留 component-tests-second.log 后增加新组件内递归容器归一化（不改字符）。第三轮 13 tests / 5.290s / OK，component-tests-third.log。

三个完整普通包实际负例各保存修改后的 JSON、重签 ID 和第一次拒绝：删除 Paramount amendment 并裁剪显式集合；删除最后文本分组并重签组件/总包；把总包改成 semantic coverage 完整及“未披露疑虑”。均由 verify_ordinary_going_concern_source 从原件重建，返回 ORDINARY_GOING_CONCERN_SOURCE_REPLAY_CHANGED。见 [负例索引](/tmp/sec_metrics_issue28_continuous/pr43-review/d04-source-development/packet-tampering-v1/index.json)。

实际命令：

```text
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_going_concern_source -v
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d04-source-development/run_material.py --repo /Users/lyuhongwang/Developer/SEC_metrics --output /tmp/sec_metrics_issue28_continuous/pr43-review/d04-ten-source-material-v1
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d04-source-development/replay_tampering.py
```

run_material.py 要求新的外部目录；重跑请换未存在的 --output。测试和材料阶段没有网络连接，材料父/子进程 audit hook 禁止 socket connect/getaddrinfo。请求账本及 manifest 的前后 SHA 未变；其他正式状态没有调用写入路径。本轮不声称独立证明所有正式输出前后哈希。

受测新文件 SHA256：

- `scripts/vnext/going_concern_source.py`: `a789a87041c1a6316fa9319d224dbe325637f81796817f37a07688c545f92f2c`
- `tests/vnext/test_going_concern_source.py`: `38828bd8e598ec5733f3e3b30f7c7e49c475331604d7bc77512ad51ec2ef6ca4`

## 接线与剩余工作

本轮先做只读原件调查，随后按根任务指派成为这两个新文件的作者。组件测试和材料重验是作者自验，不冒充独立代码审阅；根任务仍需独立核验后纳入后继接线。

本轮把普通来源发现、补充年报集合、报告身份线索和可重验完整文本输入做成了组件；未把它写进冻结 V13，也未新增平行发布器。后继须在批准的 D04 policy/Spec 下复用同一模型 Reader、Evidence/Review、原生 Text Result 和 PublicationView。不要将此组件的 source preparation 状态映射为已完成 D04。

十公司当前没有能直接取代语义判断的已验证结构化事实，因而还需要后继模型路线检查本公司/被收购方/前身、当前/历史/假设/否定/已缓解、审计报告归属及管理层说明，并处理全文与补充材料的冲突。不得把 97 个分组机械等同 97 次模型调用；应先依现有模型请求限制组装实际请求、测定其预算需求并集中申请，旧额度不得恢复。

本地 HTML 可见范围完整供给不等于 CLOSED_WORLD semantic coverage：head/script/style/ix:header/ix:hidden 不在可见块中，native facts 另作概念候选清单；外部引用文件的语义关联尚未检查。任何无疑虑结论仍需按既有 EvidenceCheck 内的 coverage_proof 闭合所需 source set / sections / examined spans；本组件没有新造 CoverageReceipt，也没有把模型自报“已读完”当足够证明。

可以在无新增调用下继续实现后继请求/响应和覆盖核验接线、做隔离模型响应反例与独立审阅；真实模型执行等待根任务集中核实/申请新额度。这个子项完成不代表 Issue #28 完成或任何生产采纳权限。
