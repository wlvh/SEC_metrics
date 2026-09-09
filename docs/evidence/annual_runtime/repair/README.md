# PR38 修复交付

受限年度候选运行已通过一次新的真实验证：B01 生成 FY2025 收入候选
261.86 亿美元，B10 经原生 Evidence、SYSTEM Review 和 Calculator 生成
69.3% 候选。再处理同一输入返回 `NO_NEW_ANNUAL_FILING`，新增调用为零。
PR38 保持 Draft，最终合并由用户审核决定，正式 R3 未改变。

## 修复了什么

原失败发生在同一已定位单元格的两种文本表示之间：来源 `raw_text` 为
`"\nWorldwide (2)"`，模型返回 `"Worldwide (2)"`，恰好等于来源的 `text`。
新规则复用原有确定性比较能力，只接受同一已验证来源单元格的 raw_text 或
text；范围计算仍使用读回的来源原文。没有修改模型字符串、原始响应或来源。

同时补齐了数值与范围标签的行、分组、指标/年份表头及单位关联。否则只放宽
文本表示仍可能接受同表错误行或业务分组。脚注差异、未知别名、冲突、错值、
错单位、错期间和错定位继续拒绝。规则没有公司、年份、数值或答案坐标补丁。

新 `issue_28_v6` / V7 明确选择普通 B10 修复政策。旧快照、engine、批准与原失败
继续保留；没有借用 R4 授权或恢复 PR34。调用仍走原执行器和 provider 边界。

## 真实尝试与对照

| 尝试 | provider/paid/SEC | 结果 |
|---|---:|---|
| 原阶段唯一请求 | 1/1/0 | B10 Evidence 拒绝，原失败完整保留 |
| 修复验证 #1 | 1/1/0 | B01/B10 原生候选成功 |
| 同输入重入 | 0/0/0 | 不执行模型 |
| 修复验证 #2 | 0/0/0 | 未使用；首次修复已成功，不满足第二次条件 |
| 累计 | **2/2/0** | 每次零自动重试 |

新请求 ID 为 `7ac51432-8a8c-49ec-bc32-95f9b56d3b07`，HTTP 200；
实际输入 161707、输出 580、合计 162287 tokens，符合输入不超过 200000 的
事后接受条件。供应商报告输入缓存命中 161664、未命中 43。原始响应 envelope、
请求 ID、marker 和 execution 均为新记录；assistant 正文与原失败相同。
这证明修复处理了原有表示差异，不是等待模型偶然补回换行。

| 指标 | 隔离旧候选 FY2024 | 新候选 FY2025 | 当前正式 R3 FY2025 |
|---|---:|---:|---:|
| B01 收入 | 251.00 亿美元 | 261.86 亿美元 | 261.86 亿美元，未改变 |
| B10 入住率 | 69.8% | 69.3% | 69.3%，未改变 |

旧年报 accession 为 `0001628280-25-004818`，目标为程序从保存清单选择的
`0001048286-26-000007`。B01 来自 Company Facts，B10 来自对应 10-K。
详细文件引用、原始字节哈希、期间和状态见 [对照记录](candidate-comparison.json)。
旧 B01 与新普通候选 Run 均如实标为 OPEN；B10 旧资格 Run 为 FROZEN。
候选中的 Result 状态不等于正式 active 更新。
当前正式 B01 的对照来自固定 R3 的继承公开行及证据行；其原始 Company Facts
哈希为 `8767de51…`，本 R3 bundle 不包含该 blob，本轮没有重做父级认证。
新候选原始 Company Facts 哈希为 `af2fea71…`，与正式行来源分开记录。
新 B10 与 R3 的内容型 Result ID 相同；新执行由独立 request/response/marker/
execution 证明，不能用相同内容 ID 代替调用记录，也不重签旧资格。

## 审阅与验证

实际受审和执行代码都是 `bb7e3f35198c662b9f36dbd433e6fd7b30284526`，
runtime tree 为 `sha256:9e4552a242f7ce9af14d36dcbe1aa1e46ca42005d7234f680e844bcd1310c113`。
Requirement closure 为 `sha256:ae514fce489eaef055e4c2c38d915d00954ef38734c9550cb5a433e83ec644de`。

- 未修改原失败响应的 23 项固定正反回归全部符合预期。
- 两项完整原生运行回归通过，覆盖成功、失败保留、重入、固定额度及伪造失败负例。
- 标签及年度输入/变化检测共 26 项通过；Python 3.9 标签四项通过。
- 本地 33 项 fast entries、受审 head 的 GitHub CI、provider 边界、语义、
  能力契约和公司常量检查通过。完整命令、时长及日志哈希另存测试记录。
- [独立模型代码复核](independent-review-final.json)为 NO_BLOCKING_FINDINGS；
  [独立原文与原生记录核对](source-audit-independent.json)为
  SOURCE_AND_NATIVE_CANDIDATE_SUCCESS_CONFIRMED。两者均不冒称人工审核。

[真实执行摘要](live-verification.json)、[完整测试记录](test-verification.json)与
[28 个原生文件的哈希清单](native-manifest.json)均可单独核对。`native-candidate/`
为逐字节审计副本，不是新的运行根；原始失败仍在相邻 `../live/` 中按旧身份保留。

具体执行记录由 Codex 依据用户委托，在独立复核和测试通过后登记：
[阶段批准](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5596431062)。
记录不冒称用户逐字审阅未来 head。预算委托固定唯一目录，原一次与两个有条件
修复名额累计核对；成功之后没有继续消费剩余额度。

## 使用入口与未证明部分

实际入口为 `tools/vnext_annual_runtime.py` 的 initialize、stage-proposal、run。
代码从原 checkout 加载，来源、ledger 和输入快照位于 Git 之外。运行验证只读取
Issue 阶段评论，不以 open/unmerged PR 为前提；测试会拒绝所有非 Issue 评论 API。
完整参数见 `docs/annual_label_repair.md` 和已保存的 stage proposal。

本轮验证使用已有 FY2025 材料和隔离的 FY2024 起点，没有请求 SEC，不能代表
未见材料泛化或长期稳定。当前只支持明确的行/分组与指标、年份两级表头布局，
不支持的布局拒绝。没有新增公司、指标或修改模型、Reader、prompt/schema、
MetricSpec、范围别名、数值及业务口径。

35 项正式 root/ledger 文件、旧成功和原失败记录均按原字节保留。正式版本接入
仍需沿同一条路径接到既有发布资格、版本对照、publication 与 rollback/restore
验收。本轮不实施它们；24 指标/240 坐标、剩余 15 指标、WB-7 和旧路径退出
责任不变，也不开始下一业务阶段。
