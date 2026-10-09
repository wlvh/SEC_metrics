# 普通候选 CLI 与文本公共行独立复核

本次受审代码来自 `5376a06596eb753a879929363b6130bee18a42da` checkout 中新增的 CLI / normal_projection / presentation policy / 对应测试。首次实际文件哈希和原文件副本分别保存在 `reviewed-source-identity.json`、`source-snapshot/`。审阅过程中主代理只在本次受审集合内修改 CLI 和说明文档；修前、修后哈希在 `repair-recheck.json`。本代理只写全新 `/tmp` 证据目录，未编辑共享源码、提交、联网或写正式结果。

结论：实际发现的一项 P2 已修复并用全新的普通 CLI 批次复核通过。本轮未留下已复现、未修复的 P1/P2。公共 schema 实际为 **20 列矩阵、18 列证据**；原“19 列”是文档误数，已纠正，历史 schema 未改。

## P2：被限制的坐标丢失具体原因与分类——已修复

首次直接运行普通 CLI，Marriott B06 形成真实 `FROZEN/WITHHELD`，D01 随后真实冻结且完成公共行。退出码为 2、批次为 `COMPLETED_WITH_GAPS`，继续处理行为正确。但修前 CLI 只保留 `result.reason_code=B06_SOURCE_RELATIONSHIP_UNRESOLVED`，丢弃底层返回的完整 `selection`，B06 没有诊断文件；具体开发缺口无法在 coordinate 或 summary 中读取。

首次产物 `real-b06-d01/` 与日志 `real-b06-d01.log` 保持原样。对该 B06 冻结 Run 使用原生完整重放得到：

```json
{"reason":"DISCLOSURE_NOTE_MISSING_OR_AMBIGUOUS:us-gaap:DebtDisclosureTextBlock","classification":"IMPLEMENTATION_GAP"}
```

结果保存在 `b06-omitted-selection.json`。问题位置为修前 CLI 原文件第 81–86 行（见 `source-snapshot/tools/vnext_normal_candidate.py`）：读取结果后未保存返回的 selection 就进入投影分支。这会把“实现尚不支持”与真正披露不足混在泛化错误码里。

主代理修复在现 CLI 第 86–93 行：保存不可变 `selections/<company>-<metric>.json`，coordinate/summary 同时保存路径、内容哈希和具体原因/分类/details 摘要。

独立修后命令使用新目录：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 tools/vnext_normal_candidate.py --output-root /tmp/sec_metrics_issue28_continuous/pr43-review/normal-cli-review-20260912a/repaired-b06-d01 --company marriott_international --metric B06 --metric D01
```

实际退出 **2**；B06 `FROZEN/WITHHELD_CANDIDATE`、D01 `FROZEN/FROZEN_CANDIDATE/CANDIDATE_ROW_PREPARED`。summary 和 coordinate 都直接含上述具体原因与 `IMPLEMENTATION_GAP`。完整 selection 与首次重放逐字段相等，内容哈希 `sha256:e8540a4b800b1e588fbdf803de577338656ceb57444bd8609ad6beefa8cd4396` 正确。见 `repair-recheck.json`、`repaired-b06-d01.log`。

## 其他实际检查

- 现有两组测试：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_candidate_cli tests.vnext.test_normal_projection`，4 项通过，29.047 秒。完整日志 `baseline-tests.log`。
- 全新独立脚本：`PYTHONDONTWRITEBYTECODE=1 python3 /tmp/sec_metrics_issue28_continuous/pr43-review/normal-cli-review-20260912a/probe.py`，实际退出 **0**，7 组全部通过。脚本所有网络 socket 操作均被审计钩子禁止。
- 输出路径：源码子目录、相对目录、已存在目录、指向源码的父符号链接、发布 workspace 后代、经符号链接指向发布 workspace 的后代，6 种全部拒绝。安全的新外部路径被接受但检查本身不创建目录。
- Marriott、Salesforce、Macy’s、Paramount 的已有真实冻结原件重新生成公共行，4 行矩阵和 **151 行证据**逐条验证：整份原件 SHA、原件字节范围 SHA、独立 HTML 文本解码得到逐字引文、引文顺序、完整结果文本、来源主体/申报/accession、实际起止期间、CSV 往返全部一致。真实新投影保存在 `rendered/`，未将旧文件冒充本轮新生成结果。
- Salesforce：2025-02-01 → 2026-01-31；Macy’s：2025-02-02 → 2026-01-31。Paramount 原文与公共行的 CIK 均为 2041610，D01 期间为报告自身的 2025-01-01 → 2025-12-31；未借用 C03 的薪酬计量短期来改写 D01。
- 新建一个真正 `freeze=False` 的 D01 Run，其内部 Result 为 `PUBLISHED`、Run 为 `OPEN`；`render_normal_text_run` 实际以 `Replay requires a FROZEN Run` 拒绝。未生成 CSV。见 `actual-open-run/`。
- 明确标记为测试的局部 I/O 异常：对第一个 B06 输入准备注入 OSError，保留逐坐标错误与 traceback，第二个 D01 则走真实原件、实际冻结与正常投影成功。批次退出 2、状态 `COMPLETED_WITH_GAPS`。该项仅证明编排对局部异常的继续与留档，不声称原件自然触发此异常。见 `injected-local-failure-batch/`。
- `probe-results.json` 含各项详细结果；受保护的 active pointer、正式矩阵/证据/报告、validation manifest 和原请求账本/manifest 哈希在探针前后完全一致。

## 覆盖边界

本轮验证普通 CLI 和现有 D01 文本行投影；没有重新执行全部 40 个普通坐标，也没有声称尚未接入 CLI 的 B06/C03/C04 公共行已完成。WITHHELD 的实际业务缺口仍存在，只是现在被准确保留。本文使用已有冻结材料重新投影，新的 B06/D01 CLI 流程则实际新建并冻结；两种证据没有混称。收据 `CANDIDATE_ONLY`、批次 `production_authorized=false`、`full_issue_acceptance=false` 均保留，不构成正式发布/上线/采纳，provider/paid/SEC = **0/0/0**。
