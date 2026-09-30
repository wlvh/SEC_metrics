# 单公司「外网取数 → 内网算指标」拆分：现状评估与方案建议

状态：评估与建议，未实施。基于 2026-09-30 的 `main`（`af1984a`）、PR43 分支 `task/b06-new-source`（`43d0445f`）与 Issue #28 / #47 正文实读。

## 1. 单个公司到底需要多少 SEC 原始数据（实测）

数据来自当前仓库 `evidence/`（十家公司、单财年口径）。单位 MB。"年度增量"指去掉上一年 10-K 后，每新增一个财年真正要新拉的字节。

| 公司 | 目标 10-K 组 | 上年 10-K | DEF 14A | 8-K（财年窗口） | Company Facts | submissions | 合计 | 年度增量 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| JPMorgan | 28.0 | 14.7 | 2.9 | 0.95 | 7.9 | 9.0 | 63.5 | 48.9 |
| Pfizer | 12.1 | 6.7 | 2.7 | 0.39 | 5.0 | 1.0 | 27.8 | 21.2 |
| Paramount（两个 CIK） | 18.6 | 见注 | 2.4 | 0.93 | 4.9 | 0.6 | 27.4 | 27.4 |
| Ford | 11.0 | 5.8 | 2.3 | 0.65 | 3.7 | 0.7 | 24.1 | 18.4 |
| Lumen | 7.8 | 4.0 | 5.2 | 0.97 | 3.8 | 0.4 | 22.1 | 18.1 |
| Salesforce | 4.9 | 2.1 | 3.9 | 0.40 | 4.7 | 1.5 | 17.5 | 15.4 |
| Marriott | 3.7 | 3.6 | 2.6 | 0.33 | 3.3 | 0.5 | 16.0 | 12.4 |
| Southwest | 5.6 | 2.6 | 2.2 | 0.56 | 4.1 | 0.3 | 15.4 | 12.8 |
| Macy's | 4.4 | 2.0 | 4.2 | 0.38 | 3.8 | 0.5 | 15.3 | 13.3 |
| Enphase | 5.9 | 2.8 | 1.6 | 0.18 | 3.1 | 0.2 | 13.8 | 11.0 |
| 十家合计 | | | | | | | 243 | |

注：Paramount 的上年 10-K 属于前身 CIK 813828，目录归类到目标组里；Paramount 目标组包含 10-K/A 与原始完整 instance 各两份。

构成规律：

- 单份 10-K 的 HTML 主文档 2–13 MB，XBRL instance XML 1.5–15 MB；这两类占单公司体量的 60–75%。JPM 最大：主文档 12.9 MB，instance 14.9 MB。
- 8-K 单份约 25–50 KB，一个财年窗口 6–25 份，合计不到 1 MB。
- Company Facts 每 CIK 3–8 MB；submissions 主文件 0.15 MB，但历史分片可达 12 片 9 MB（JPM）。
- headers sidecar、index.json、FilingSummary.xml 合计不足 0.2 MB。
- 仓库 `evidence/` 总计 467 MB，其中 `request_attempts/` 196 MB 里有 142 MB 与 `accession_materials/` 等目录是相同字节的二次存储；去重后全部原件约 253 MB。

外推：

| 规模 | 估算 |
|---|---|
| 一家公司 × 一个财年 | 11–50 MB，中位数约 15 MB |
| 一家公司 × 五个财年（Issue #47 口径） | 约 60–250 MB |
| 1000 家公司 × 一个财年 | 15–50 GB |
| 1000 家公司 × 五个财年 | 75–250 GB |

结论：**体量不构成拆分理由。** 这个量级放 Databricks Volume 没有压力；拆分的真正收益在更新粒度、失败隔离与传输单元，见第 4 节。

## 2. 现有三条路径里，哪条能"单公司从取数到指标"

### 2.1 legacy 阶段管线 `scripts/00_*` – `12_*`

每个阶段都对 `load_company_registry()` 全量循环；唯一隔离手段是 `sec_pipeline.py --workspace-dir <abs>`，它把 `config/company_registry.csv` 重绑到工作区。理论上可用一行注册表做"单公司工作区"，但 Golden、repair validation 与报告都按十家公司整体验收，且 Issue #28 的目标之一是让 legacy 生产路径退出。**不应在此路径上建新能力。**

### 2.2 `main` 上的 vNext

Run 已经是公司粒度（`batch_workflow.create_companyfacts_release_run` 一家公司一个 Run），但：

- 批次 manifest 要求完整 FROZEN Run 集合，投影要求"完整 legacy 兼容行集合"；
- 发布是整矩阵一个 active pointer；
- `main` 上只有 Marriott 专用的有限刷新（`annual_update.py`），没有通用的"任一公司发现来源、获取、计算"。

已经存在的关键机制：`annual_projection.build_projection` 在完整前驱之上原位替换选中行（PR40 的 2 项采纳 + 238 项继承）。这就是"按公司增量发布"的正确形态：**一个 pointer，按公司 delta 合并**，不需要每公司一个 pointer。

### 2.3 PR43（未合并 Draft，5734 文件变更）上的 ordinary 路径

这才是最接近需求的东西，而且已经把三段拆开了：

| 段 | 入口 | 现状 |
|---|---|---|
| 来源发现 | `normal_source_requirements.discover_saved_source_requirements` | 从 submissions 元数据推导当前/上年 10-K、修订、DEF 14A、财年 8-K、instance 依赖；不取数 |
| 有限获取 | `continuous_sec_acquisition.SecAcquisitionSession.capture` | 一次一个已声明 URL，零重试，追加账本，创建者进程登记 checkpoint；CLI `tools/vnext_ordinary_refresh.py --company X --max-sec-requests N` |
| 安装与计算 | `normal_run_v3.install_normal_inputs(data_root, source_root)` → `create_normal_run` → `ordinary_projection.render_ordinary_run` | 只复制该公司该指标实际引用的文件进 data_root；36/39 路线接通；CLI `tools/vnext_normal_candidate.py --company X --metric M --source-root S --output-root O` |
| 合并成完整版本 | `ordinary_release_preparation.prepare(native_runs=[...])` | 以当前 PublicationView 为前驱，按行替换 |

特别重要的一点：PR43 的可移植安装已经设计了"没有 `.git` 的数据根"这种场景。`ordinary_source_authority._trusted_checkpoint` 在代码根没有 `.git` 时改读 `config/ordinary_source_checkpoint.json`，`install_normal_inputs` 会把 checkpoint 写进 data_root。文档原话是：它信任随运行时一起安装的 checkpoint，不防御同时替换代码与执行历史的操作者。**这正是内网 Databricks 的情形**：内网只能信任"随包到达的 checkpoint"，代码本身无法证明包是外网真实抓取的。

## 3. 真正的耦合点（拆分要动的地方）

### 3.1 全局请求账本 + 行号绑定身份

`evidence/requests_log.csv` 是十家公司共用一张表，`requests_log_manifest.json` 绑定整表 SHA-256。`sec_http.request_log_attempt_id` 用 **行号 + 行内容** 派生 attempt ID；vNext 的 SourceReference、Run、publication provenance 全部引用这个 ID。

后果：把现有账本"按公司重新分表"会改变所有 attempt ID，等于重签全部历史 Run 与发布。**拆分只能前向进行**：新的公司来源根拥有自己的账本命名空间与新 ID；历史 Run 继续指向全局账本。这不是文件布局问题，是身份边界。

### 3.2 来源信任根绑定在代码 checkout 的 `.git`

PR43 的 `ordinary_source_authority._journal()` 与 `continuous_sec_acquisition._journal()` 都写 `ROOT/.git/ordinary-source-authority/{recorded,acquired}/<ledger_sha>.json`，并要求 `.git` 是目录。Issue #47 §2.4 已经因为 linked worktree 撞到这条。Databricks 以 wheel 或 Repo 部署时同样没有这个目录。

可移植回退（`config/ordinary_source_checkpoint.json`）存在，但它的信任前提是"运行时和 checkpoint 一起被安装"。内网侧需要的是一个**显式的包级信任声明**：包 manifest 的哈希 + 谁生成的 + 可选签名，而不是隐式依赖代码目录。

### 3.3 LIVE 获取绑定 GitHub 委托评论与本机绝对路径

`continuous_call_policy.load_delegation(online=True)` 实时读取 GitHub issue comment；policy 里 `budget_root` 是 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`，累计上限 `[240, 240, 80]`（provider/paid/SEC）。这是开发期治理装置，不是生产取数接口。外网取数机器要么复制这套约束（需要 GitHub token、同一绝对路径、共享预算），要么给"公司来源根"定义一条新的、可移植的获取政策。这是 owner 决策，不是工程细节。

### 3.4 获取根整体复制 484 MB 基线

`continuous_sec_acquisition.initialize_source_inputs` 把 `config/normal_candidate_sources_v1.json` 绑定的 1256 个文件（484 MB，含 fixture 与二次存储）全部复制进每个获取根。安装到 data_root 的那一步已经是"只复制引用文件"，所以**计算侧已经是单公司最小集合，获取侧不是**。做单公司包必须把基线也按公司切，或者让基线检查只针对引用文件。

### 3.5 AI 供应商主机固定

`ai_adapter.py` 把主机固定为 `api.deepseek.com`，密钥来自环境变量 `DEEPSEEK_API_KEY`；Decision Register 的 `S-PROVIDER-TRANSPORT.endpoint_host` 绑定同一值。内网 Databricks 若走公司代理，`urllib` 默认 opener 会读 `HTTPS_PROXY`，主机不变即可；若内网是另一个模型网关，就是一次 Requirement 修订，而且所有"同请求字节可复用"的历史信用都不再适用。

### 3.6 代码字节身份

Requirement 的 `execution_authority` 绑定模块文件的 SHA-256，例如获取模块启动时自检自身文件哈希。部署到 Databricks 的代码必须逐字节等于受审 checkout；Issue #28 证据里已经出现过"冷读因 Python 写入 `__pycache__` 而退出 1"的案例。Databricks 的 Repo / wheel 部署都会碰这个。

## 4. 建议方案（最小改造，前向兼容）

### 4.1 定义一个共享的「公司来源根」契约

同时服务本需求与 Issue #47 §4.2 要求的"代码 checkout 之外、可验证、追加式账本"。一个公司来源根 = 一个目录：

```text
<company_source_root>/
├── package_manifest.json          # 包 ID、company_id、全部 CIK 角色、生成时间、代码身份、上一版包 ID
├── config/company_registry.csv    # 该公司（含 successor/predecessor）子集或全量，需决策
├── config/ordinary_source_checkpoint.json
├── evidence/requests_log.csv      # 该公司自己的账本，仅追加
├── evidence/requests_log_manifest.json
├── evidence/request_attempts/...  # 内容寻址原件 + headers
└── evidence/{submissions,companyfacts,accession_materials}/...   # 若消费者仍需固定路径视图
```

规则：

1. 包 v(n+1) 的账本必须以 v(n) 的账本为字节前缀（复用 `_prefix` 检查），否则拒绝导入。
2. 每行账本给出 `request_attempt_id`，后续 Run 引用该 ID；ID 在包内命名空间派生，与全局账本无关。
3. `package_manifest.json` 的字段直接复用 2026-07 交接文档里的 manifest（observation_key、sha256、company_id、cik、accession、document_name），只增加 `request_attempt_id` 与包级哈希。
4. 信任方式二选一：传输信道信任（内网只校验哈希与前缀），或外网生成时附加分离签名（代码里目前没有签名，需新增）。

### 4.2 外网侧：一条公司级 refresh 命令

复用 PR43 的发现 + 获取会话，改两处：获取根即公司来源根，journal 与 checkpoint 写到包内而不是 `.git`；基线复制只复制该公司引用的文件。输出即可传输的包目录。

### 4.3 内网侧：一个 Databricks job 消费包

`导入校验（哈希、前缀、registry 子集） → install_normal_inputs(source_root=包) → 逐指标 create_normal_run → render_ordinary_run → 公司候选目录`。除模型调用外零网络。然后 `ordinary_release_preparation.prepare` 把该公司的 Run 合并进完整版本。发布仍是一个 active pointer。

### 4.4 明确不做的事

- 不重分现有全局账本，不重签历史 Run。
- 不做 per-company active pointer。
- 不在 legacy 00–12 上加公司过滤。
- 不新建第二套获取、审批或发布平台；只加薄的包契约与两个入口。

### 4.5 需要补的负例测试

包导入：篡改一个原件字节、篡改 manifest、账本非前缀扩展、缺 headers、registry 子集不含 predecessor CIK（Paramount）、JPM 12 片 submissions 缺片；安装：无 `.git` 的代码根 + 只读 Volume 路径；重复导入同包幂等；同包重复计算零新增调用。

## 5. 盲点、替代解释与反例

1. **"将来会很大"不成立。** 实测千家公司一年 15–50 GB。真正会先撞墙的是时间与调用：一个 lodging 表格请求约 16 万 prompt token，一次私有发布演练测试 4679 秒，SEC 通道零重试且累计上限由委托评论决定。拆公司不解决这些，只是不再重跑别的公司。
2. **单公司快速更新的瓶颈不在传输。** PR43 已有 `NO_SOURCE_CONTENT_CHANGE` 幂等：来源不变就不新建 Run。慢的是发现→获取→逐指标 Run→合并→发布这条链的治理开销，以及 D03 这类 38 组请求的模型时间。
3. **白名单问题可能有更便宜的解。** 需要放行的只是 `www.sec.gov`、`data.sec.gov` 两个主机，外加 `api.deepseek.com`。如果 SEC 都放不了，`api.deepseek.com` 大概率也放不了，那"内网做 AI"的前提就不成立，AI 只能一起放到外网，跨边界传的就变成"原件 + 模型响应"。这个前提必须先核实。
4. **公司 ≠ CIK。** Paramount 两个 CIK、JPM 12 片 submissions 历史、8-K 窗口和上年 10-K 横跨两个财年。包的边界应是"公司 + 目标期间 + 已声明依赖"，这恰好是现有来源发现的输出，不要自己定义"一公司一年一个目录"。
5. **包级信任是新问题。** 现在的信任链靠 git blob 基线和创建者进程写 `.git` journal。改成包之后，内网只能信任"包说自己是真的"。代码不能替你回答"谁签的包"，这是 owner 必须先定的政策。
6. **仓库里 2026-07 的三份 Databricks 文档已过时。** 它们围绕 legacy 管线离线重放、六张 Raw 表，数量是 218 MB / 859 条，且不知道 Requirement 绑定执行权限这回事。新需求应替代它们的"生产闭环"部分，只保留 Raw 表与 manifest 的字段设计。
7. **必须叠在 PR43 之上。** `main` 没有通用的 ordinary 路径；在 `main` 上做等于重写 36 条路线。可行做法与 PR52 相同：从 PR43 固定 head 开分支，共享改动按 Issue #28 §6 标记登记，不动 #28 的预算和账本。代价是随 PR43 合并方式（merge 或 squash）而定的同步成本。
8. **反例：如果只想要"每公司一份 CSV"。** 那不需要任何上述改造，`vnext_normal_candidate.py --company X` 已经按公司输出候选行；`docs/metrics_csv_delivery_design.md` 也已有按业务域拆 CSV 的方案。请先确认需求是"传输与执行单元按公司"，而不是"输出文件按公司"。

## 6. 需要 owner 先回答的三个问题

1. 内网能否访问 `api.deepseek.com`（或指定内网模型网关）？决定 AI 在哪一侧。
2. 包的信任方式：信道信任还是签名？决定要不要加签名工具。
3. 是否接受在 PR43 之上开分支并等待其合并方式？决定排期。
