# D04 后继：基于同原件封面关系的名称匹配

根任务指出 /MD/ 与 Co / Company 是可消除的实现性限制后，本轮只修改尚未纳入 V13 的两个新文件。先前 HANDOFF.md 和 d04-ten-source-material-v1 继续保留为当时版本的真实结果；本文件与 v2 材料描述最新版本。

两项来源关系均已实现自动识别，不需要日常填写别名或公司特例。十家公司每家本期财务报表审计开头均匹配到 1 份；Paramount 的前身旧期报告仍不匹配当前主体。18 tests / 8.771s PASS，最新十家公司普通包保存与全新 Python 进程重建 10/10 PASS。仍无 D04 语义结论、Run、freeze、Result 或正式信用；provider/paid/SEC=0/0/0。

## 原文关系与一个重要区别

Marriott 原件封面 block 11、bytes [136236,136264) 为 MARRIOTT INTERNATIONAL, INC.；紧邻 block 12、bytes [136419,136473) 明示 Exact name of registrant as specified in its charter。官方 DEI EntityRegistrantName ordinal 4、context c-1、CIK 0001048286、period_end 2025-12-31，值为 MARRIOTT INTERNATIONAL INC /MD/。然而 DEI EntityIncorporationStateCountryCode 和封面实际注册州都是 Delaware，因此不能把 MD 当作本期注册州。新规则仅借明确封面名字证明两个名称属于同一原件注册人，输出 marker_jurisdiction_meaning_asserted=false。

Ford 封面 block 10、bytes [609699,609733) 为 Ford Motor Company；紧邻 block 11、bytes [609902,609956) 是相同的 Exact-name 标签。官方 DEI EntityRegistrantName ordinal 60、context c-1、CIK 0000037996、period_end 2025-12-31，值 Ford Motor Co。这是同一文件两个明确注册人名字之间的末尾法律形式缩写关系，不能推广为 Ford Credit。

两份完整 packet 中 registrant_name_binding 保存所有上述 DEI fact/context、封面名字与标签的 source_reference / 原字节 span / SHA，不依赖手写 alias 表。原件路径和所有 SHA 在 v2/index.json 与逐公司 JSON 中。

## 通用规则及拒绝边界

1. 使用官方 DEI namespace 的 EntityRegistrantName；所有候选必须属于同 CIK、本期、无维度 context，且唯一名称。错误 context 或冲突名称不会获得 alias。
2. 首个 FORM 10-K(/A) 的封面内，必须有唯一 Exact-name 标签，其直接前一可见块是注册人全名。封面范围在证券列表、正文 Part/Item 等之前结束；不从全文邻近公司段落找 alias。
3. 只对这两个明确注册人名字比较完整词元序列；允许 DEI 末尾 /AA/ 形式的标记、末尾 Co/Company、Inc/Incorporated、Corp/Corporation 的等价形式。标记不解释为注册州，法律词只在末尾处理。Motor、Credit、Holdings、地点及其他实词全部保留，词边界不消失；Corporation 不等于 LLC。
4. 关系成立后仅接受实际 DEI 原名和封面原名，审计开头必须匹配其中一个；不扩大为全局模糊匹配或凭空生成别名。没有封面关系就只保留严格 DEI 原名；重复标签、封面/DEI 冲突或错误 DEI context 保留未决。
5. 名称关系和当前余额表日期相符只关闭来源身份线索中的这两个实现缺口，不证明报告作者身份、疑虑的语义或全文不存在疑虑。所有原有 semantic review / CLOSED_WORLD 限制不变。

新增反例涵盖 Ford Motor / Ford Credit，Co/Company 位于中间的区别词，不同法律形式，假尾标 /XYZ/，邻近公司审计报告，重复封面标签，外公司 DEI context，以及重签新增 Ford Credit alias。它们均不能获当前注册人匹配。真实 Marriott 与 Ford 均通过自动封面关系，无公司名/CIK 特例分派。

## 实际命令与证据

```text
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_going_concern_source -v
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d04-source-development/run_material.py --repo /Users/lyuhongwang/Developer/SEC_metrics --output /tmp/sec_metrics_issue28_continuous/pr43-review/d04-ten-source-material-v2
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d04-source-development/replay_tampering_v2.py
```

v2 仍覆盖 12 份年报/修订年报，97 个全文分组，5,967,865 UTF-8 源载荷字节。材料父/子进程禁网络，完整 source proofs 重新验证，正文与日期来自原件；分组数不等于调用数，未测 provider token。受检请求账本及 manifest 前后 SHA 不变。普通包删补充文件、删分组和伪造无疑虑的三个重签负例另存 packet-tampering-v2，不拿旧版本的拒绝代替当前版本验证。

当前源文件 SHA256：

- `scripts/vnext/going_concern_source.py`: `0b4ae2ef128d66cf4ad35ff77cd1afb3102aef4819b32967795ff18eb5edb05e`
- `tests/vnext/test_going_concern_source.py`: `d0b99477df8c00dabfdcde7b77807daefaf37490ffb4865b70823d0af17bc6ae`

当前 API 名称未变：prepare_ordinary_going_concern_source / verify_ordinary_going_concern_source；低层 inspect/verify_going_concern_source 仍显式无 source admission。新增的 registrant_name_binding 可用于后继正常 D04 语义输入身份说明。完整语义模型执行、EvidenceCheck 中 CLOSED_WORLD coverage proof、Review 和原生 Text Result 接线仍需根任务继续；这份作者自验不代替独立代码审阅，也不改变已冻结 V13 或任何生产权限。
