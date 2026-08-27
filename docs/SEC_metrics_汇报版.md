# SEC_metrics：技汇报版

> 基于 `agent/issue-15-final-delivery` 快照 `f64ca6013e18df6b8e6587da3d17debd22d95d65`。
>
> 目标：不用审计论文式语言，直接讲清楚系统做什么、做到哪、为什么复杂、当前卡在哪里。

---

# 1. 先说结论

这套系统不是一个“从 SEC 抓数据、算几个指标”的脚本集合。

它真正解决的是：

> **一个数字算出来以后，怎么证明它来自正确的 SEC 文件、经过了正确的处理、没有漏项，并且可以安全地交给下游使用。**

所以它交付的不只是数字，还交付数字背后的完整证据链和发布版本。

用一句技术汇报的话说：

> **这是一个审计优先的本地批处理系统。它把 SEC 原始文件逐步加工成可追溯、可重算、可回滚的年度指标快照。**

当前状态可以直接概括成三句话：

1. **已经正式上线的是 zero-AI R2**：22 个指标、220 个结果坐标，最终公共矩阵 309 行。
2. **AI 读表链路已经能真实调用模型，也有完整的失败保护，但还没有任何 AI 结果进入正式发布。**
3. **当前 lodging 路径在做 qualification，financial 路径仍被表格展开的资源上限卡住。**

---

# 2. 这套系统到底替业务解决什么

假设业务要拿十家上市公司的年度指标去做分析。

普通脚本通常只能回答：

> “结果是 69.8%。”

但真正进入生产后，技术和业务会继续问：

- 69.8% 来自哪家公司、哪份年报、哪张表？
- 为什么选这一格，不是旁边那一格？
- 如果模型选错表，谁来发现？
- 如果代码后来改了，这个历史结果还能不能重算？
- 如果新批次失败，会不会把上一批正确结果覆盖掉？
- 一批十家公司里漏了一家公司，系统会不会仍然显示成功？

SEC_metrics 的设计，就是逐个回答这些问题。

因此系统的对外责任不是“尽量多出数”，而是：

> **只有证据闭合的结果才允许进入正式版本；证据不够时，宁可明确失败或 withheld，也不猜。**

---

# 3. 当前做到哪了

## 3.1 已经完成并正式生效的部分

### Zero-AI R2 已经是 active

当前正式版本是 zero-AI R2：

- 已迁移指标：22 个；
- 十家公司对应 220 个结果坐标；
- 对外公共矩阵：309 行；
- 这条正式发布路径没有使用模型；
- 新结果先独立生成，再与 legacy 结果做兼容性对比；
- 发布后支持回滚和恢复。

这部分是已经发生过的正式交付，不是未来设计。

## 3.2 已实现但尚未进入正式发布的部分

AI 表格链路已经具备：

- 把整份 SEC HTML 解析成表格网格；
- 生成严格的模型请求；
- 控制真实 provider 调用；
- 避免同一请求被并发调用两次；
- 保存请求、响应、token usage 和失败原因；
- 用机械规则重新读取模型给出的单元格；
- 只有 Evidence 通过后才允许进入 Review 和计算；
- 对整个 Run 做离线重放验证。

也就是说，AI 链路已经不是 demo，但它仍处于 qualification 阶段。

## 3.3 当前还没有完成的部分

- AI 结果进入 active publication：**0 个**；
- lodging 的完整 qualification sequence：未完成；
- production semantic freeze：未完成；
- financial table family：被 `EXPANDED_GRID_RESOURCE_LIMIT` 阻塞；
- 39 个指标全部迁移：未完成；
- full acceptance：未完成；
- API、前端、scheduler、长期 worker：没有，这是当前产品边界。

---

# 4. 整体架构，不按目录讲，只按责任讲

整个系统可以看成四块。

## 4.1 第一块：确认“原始材料是什么”

这一层负责从 SEC 获取文件，并把来源说清楚。

它要建立的不是“我下载了一个 HTML”，而是：

> 这组字节来自 SEC 官方地址，属于这家公司、这份 filing、这个 accession，并且对应请求账本里的这一次请求。

主要产物包括：

- 原始文件；
- response headers；
- SHA-256；
- 请求日志；
- 公司、filing、document 和 source role 的绑定。

这层只证明来源，不解释数字含义。

## 4.2 第二块：把原始材料变成可计算事实

结构化数据路径会从 Company Facts、XBRL 或事件材料中提取事实，再按指标规则计算。

AI 路径则多了一层：

1. 模型先指出它认为正确的表格和单元格；
2. 系统自己重新读取这些单元格；
3. 检查值、标签、单位和 scope 是否真的一致；
4. 通过后才变成可计算事实。

两条路径最终都会汇总成同一种对象：

> **VerifiedObservation：已经有资格参与计算的事实。**

然后通用 Calculator 再生成：

- `MetricResult`：最终业务结论；
- `ExecutionTrace`：这个结论是怎么计算出来的。

## 4.3 第三块：证明这次执行是完整的

一次运行会被保存成一个 Run。

Run 里包括：

- 使用了哪些 source；
- 模型是否调用过；
- 模型返回了什么；
- Evidence 是否通过；
- Review 做了什么决定；
- 最后生成了什么 Result 和 Trace。

Run 不能只靠一个 `status=PASS` 就宣布成功。

冻结前，系统会从原始 source 重新跑一遍关键逻辑，确认保存下来的结果和重新计算的结果一致。

所以这里的核心不是“记录写完整了”，而是：

> **记录里的关系能够从原始材料重新证明。**

## 4.4 第四块：把完整结果安全发布给下游

系统不会直接覆盖根目录里的 CSV 和报告，然后祈祷中途不要崩。

它的做法是：

1. 先生成一个完整、不可变的新版本目录；
2. 检查里面所有文件的 hash、数量和前驱版本；
3. 用一个 active pointer 表示“当前正式版本是谁”；
4. 发布时原子切换 pointer；
5. 失败时仍然保留上一版；
6. 读者通过 `PublicationView` 固定读取同一版，不会半旧半新。

可以把它理解为：

> **先把新版本整个打包好，再切换版本号，而不是逐个覆盖线上文件。**

---

# 5. 三条最重要的主流程

# 流程一：结构化 SEC 数据如何成为正式指标

这是已经正式落地的 zero-AI 路径。

大白话流程：

```text
SEC 原始文件
→ 确认公司和 filing 身份
→ 提取结构化事实
→ 按指标规则计算
→ 生成结果和计算轨迹
→ 检查十家公司 × 已迁移指标是否一个不少
→ 先独立生成新结果
→ 再与 legacy 做兼容性比较
→ 打成不可变版本
→ 切 active pointer
```

这里最重要的两个点：

### 第一，新实现不能偷看旧答案

新 producer 必须先从 SEC 原始数据独立算出结果，之后才能拿 legacy 结果做对照。

否则所谓“迁移成功”，可能只是把旧结果重新复制了一遍。

### 第二，不能只抽样看几个结果

系统要求完整坐标集合：

- 少一个公司不行；
- 少一个指标不行；
- 重复一个坐标也不行；
- 多出意外坐标也不行。

这是为什么系统强调 exact set，而不是“看起来差不多”。

---

# 流程二：模型读表如何变成可信事实

这条链路最值得在面试里讲，因为它体现了 AI 系统怎么做可靠性控制。

大白话流程：

```text
整份 SEC HTML
→ 展开成全部表格和稳定坐标
→ 生成固定模型请求
→ 先登记这次调用，再真正发请求
→ 模型返回“我认为这格是答案”
→ 系统自己重新读取该格和相关标签
→ Evidence 通过
→ 人或授权 SYSTEM 做 Review
→ 变成 VerifiedObservation
→ 再交给 Calculator 算指标
```

关键思想是：

> **模型只负责提候选答案，系统负责证明候选答案。**

模型返回严格 JSON，只能证明格式正确，不能证明内容正确。

因此系统把几个责任分开：

- Reader：解析模型说了什么；
- Evidence：检查模型指的单元格是不是真的支持它的说法；
- Review：处理剩下的语义判断；
- Calculator：做确定性计算；
- Run freeze：重新验证整条链。

这比“再调用一个模型判断第一个模型对不对”更稳定，因为机械检查可以重复、可以测试，也不会产生第二层模型幻觉。

---

# 流程三：一批结果如何成为当前正式版本

大白话流程：

```text
完整 Runs
→ 检查结果集合和兼容性
→ 生成完整版本目录
→ 保存切换意图
→ 更新兼容镜像
→ 原子切 active pointer
→ 写切换收据
→ 重新打开并读回验证
```

失败时的原则很简单：

- pointer 还没切：继续使用旧版本；
- pointer 已切但后续没完成：根据切换意图恢复或补齐；
- 两个发布者同时提交：只有一个能赢；
- 新版本终态验证失败：回滚到上一版；
- 旧版本文件本身永远不修改。

---

# 6. 只需要记住的八个核心对象

不用记全部 schema，记这八个就够了。

| 对象 | 大白话含义 |
|---|---|
| `RawBlob` | 这组原始字节确实存在，hash 是什么 |
| `SourceReference` | 这组字节属于哪个公司、哪份 filing、哪个 document |
| `ObservationCandidate` | 模型声称某张表某个单元格是目标值 |
| `EvidenceCheck` | 系统自己重读后，判断模型说法是否成立 |
| `ReviewDecision` | 人或授权 SYSTEM 对整包证据作批准或拒绝 |
| `VerifiedObservation` | 已经有资格参与计算的原子事实 |
| `MetricResult + ExecutionTrace` | 最终结论，以及结论如何产生 |
| `Run + Publication` | 一次完整执行，以及一批结果的正式发布版本 |

这八个对象背后是一条清晰的信任升级：

```text
原始字节
→ 有来源的材料
→ 模型的主张
→ 被验证的主张
→ 可计算事实
→ 业务结果
→ 完整执行
→ 正式版本
```

---

# 7. 为什么系统要设计得这么严格

## 7.1 不能让调用者随便指定关键输入

调用者可以说“我要跑哪个 task”，但不能随便改：

- 公司；
- source；
- filing；
- Spec；
- provider；
- publication root。

这些必须由仓库当前配置重新推导。

否则 CLI 参数就会变成绕过治理的后门。

## 7.2 有 hash 还不够，必须重新计算

如果攻击者同时修改：

- Observation；
- Result；
- Trace；
- 以及它们所有 hash；

整个对象图仍然可能看起来“内部一致”。

所以 freeze 不能只检查 hash，而要从原始 source 重新计算。

一句话：

> **hash 证明“这是同一份内容”，replay 才证明“内容之间的业务关系是真的”。**

## 7.3 模型调用要先留下痕迹，再真正出网

付费模型调用最危险的情况不是普通报错，而是：

> 请求可能已经发出，但本地进程不知道远端到底执行没有。

系统因此先做 reservation，再写 egress marker，最后才打开 socket。

如果进程在发出请求后死亡，又没有拿到明确结果，系统会记录：

```text
UNKNOWN_REMOTE_OUTCOME
```

并且不自动重试。

这不是保守过度，而是避免重复扣费和产生两条无法对账的结果。

## 7.4 正式发布不能直接覆盖文件

如果要更新十几个相关文件，逐个覆盖必然有半新半旧风险。

所以系统把一个版本做成完整 bundle，再用 pointer 切换。

这相当于把“更新很多文件”转化成“切换一个版本 ID”。

## 7.5 失败也必须是明确结果

系统会区分：

- `N_A_STRUCTURAL`：这个指标本来就不适用；
- `NOT_MEANINGFUL`：适用，但这个数在当前条件下没有意义；
- `WITHHELD`：应该有结果，但证据或计算不够，不能发布。

这三种情况不能统一成一个空值，否则下游不知道是正常没有、数学无意义，还是系统失败。

---

# 8. 当前最值得讲的真实失败

最新的一次真实 qualification 调用是 Marriott FY2024 Occupancy，SECOND_LAYOUT 第一轮。

远端调用本身成功：

```text
HTTP 200
prompt tokens     159376
completion tokens 550
total tokens      159926
retry             0
```

模型返回的 geography 标签是：

```text
Worldwide (2)
```

但表格单元格保存的 exact raw text 是：

```text
\nWorldwide (2)
```

也就是前面多了一个换行。

Evidence checker 按当前契约逐字比较，因此返回：

```text
SCOPE_LABEL_TEXT_MISMATCH
EVIDENCE_FAILURE
```

结果是：

- 没有进入 Review；
- 没有生成 Result；
- Run 没有冻结；
- qualification 没有通过；
- active R2 完全不受影响。

这个案例同时说明两件事。

## 8.1 好的一面

系统没有把以下事实混在一起：

- HTTP 调用成功；
- 模型输出格式正确；
- 模型答案看起来合理；
- Evidence 真正通过；
- qualification 成功。

它们是五个不同的状态。

## 8.2 暴露的问题

当前 Evidence contract 把模型输出和 HTML 的原始换行也绑得很死。

这里需要技术 Lead 做一个明确选择：

### 方案 A：继续要求模型复述 exact raw text

优点：审计边界最简单、最严格。

缺点：无业务意义的空格或换行也可能让调用失败。

### 方案 B：模型提交规范化文本，Evidence 自己保存 exact raw text

优点：更符合模型能力，减少无意义失败。

缺点：必须把 normalization 规则做成确定性、版本化、可重放的契约，不能偷偷做模糊匹配。

我的判断是：

> 可以考虑方案 B，但这不是“加一个 trim()”那么简单，而是一次 output contract 和 Evidence contract 变更，必须重新 freeze 和 qualification。

---

# 9. 当前设计的主要优点和代价

## 优点

1. 每个结果都能追到原始 SEC 文件。
2. 模型不能直接写业务结果。
3. 保存下来的 PASS 不能自证，系统会重新计算。
4. 一批结果漏一个坐标就不能发布。
5. 远端调用有清楚的并发、重试和未知状态语义。
6. 新版本失败不会覆盖上一版。
7. 读者可以固定读取一个版本，避免混读。

## 代价

1. 对象和 receipt 很多，学习成本高。
2. qualification 改一点契约就要重新冻结很多证据。
3. 全文档、全表格、不预筛的策略消耗大量 token 和内存。
4. 文件系统事务适合单机低并发，不适合未来多机调度。
5. 文档容易成为历史时间线，不能简单当 current truth。
6. 当前 exact-head review 仍有一部分依赖人工流程，而不是完整机器 grant。
7. 系统证明“按 Spec 正确执行”，但 Spec 的会计口径是否正确仍需要业务和人工负责。

---

# 10. 我会怎么安排下一步

## P0：先解决 qualification 契约问题

### 1. 明确 raw text 和 normalized text 的边界

决定 whitespace 是模型责任，还是 Evidence 的确定性 normalization 责任。

不建议临时放宽比较规则，否则会破坏当前 Evidence 的可解释性。

### 2. 把首次 egress review 做成真正的机器 grant

当前代码强绑定了：

- source；
- task；
- request hash；
- usage；
- terminal。

但 first-egress exact-head review 仍主要依赖 operator 流程。

建议引入一个明确 grant artifact，绑定：

```text
reviewed head
+ plan ID
+ request SHA
+ review comment
+ expiry / one-shot scope
```

## P1：完成 lodging qualification sequence

在契约明确后，重新跑：

- second layout；
- production semantic freeze；
- holdout；
- fresh stability ordinals；
- qualification status。

不要在 sequence 中间修改 prompt、schema、serializer 或 Evidence 规则。

## P1：解决 financial resource blocker

financial family 的核心问题不是模型质量，而是完整表格展开超出资源限制。

优先研究：

- 无损压缩；
- 流式表示；
- 不展开重复 span 的表示；
- 可证明完整性的 selector。

不能为了跑通直接静默丢表。

## P2：改善工程可维护性

- 把超长 workflow / qualification recovery 拆成显式状态机或 saga；
- 增加一致的 bootstrap 和 CI；
- 把 current status 文档与历史 decision timeline 分开；
- 为长期多机运行准备数据库或 durable workflow control plane，但保留不可变 evidence bundle。


---

# 关键证据索引

需要继续查代码时，优先看这些位置：

- 当前 active：`outputs/active_publication.json`
- R2 正式收据：active publication 内的 `internal/zero_ai_release_receipt.json`
- AI 调用控制：`scripts/vnext/invocation_control.py`
- 模型 transport：`scripts/vnext/ai_adapter.py`
- 表格坐标系：`scripts/vnext/table_grid.py`
- Reader 输出校验：`scripts/vnext/reader.py`
- 机械 Evidence：`scripts/vnext/evidence.py`
- Review：`scripts/vnext/review.py`
- Run 与 freeze：`scripts/vnext/run_store.py`
- Qualification：`scripts/vnext/qualification.py`
- 发布事务：`scripts/vnext/publication.py`
- 最新 whitespace terminal 测试：`tests/vnext/test_table_qualification_samples.py`
