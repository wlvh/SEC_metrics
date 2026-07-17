# CIK和Ticker会在什么情况下改变？
先纠正一个概念：**CIK 不会因为公司简单更名而改变。**

## 1. CIK 和 ticker 分别什么时候变化

### CIK

SEC 明确说明，CIK 是 filer 的永久标识，不能修改、不会过期、不会回收；同一个 CIK 可以因为公司更名而对应多个历史名称。[SEC 对 CIK 的官方说明](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/understand-utilize-edgar-cik-cik-confirmation-code-ccc)，[SEC EDGAR 数据说明](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)。

因此严格来说不存在“CIK 更名”，只有两种情况：

1. 公司名称变了，但 filer 没变：CIK 不变。
2. 项目所跟踪的逻辑公司开始由另一个 filer 申报：`primary_cik` 从旧 CIK 切换到新 CIK。

第二种情况可能发生在：

- 新控股公司重组；
- 合并或反向合并；
- SPAC 交易；
- reincorporation；
- 破产重组后由 successor 申报；
- 分拆形成新的上市申报主体；
- 原主体终止申报，由新主体承接报告义务。

但法律主体变化和 CIK 变化并不是一一对应的。Rule 12g-3 succession 中，有时 successor 使用新 CIK；有时 successor 承接 predecessor 的申报属性甚至继续使用旧 CIK。因此：

```text
CIK 不变 ≠ 一定经济连续
CIK 改变 ≠ 一定完全不连续
```

SEC 也要求 successor 就 succession 交易提交 8-K，并可能生成新的文件编号。[SEC Rule 12g-3 解释](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/exchange-act-rules)。实际 SEC 文件中既有 successor 承接旧 CIK 的案例，也有 predecessor 保留旧 CIK、successor 使用新 CIK 的案例：[承接旧 CIK 的 8-K](https://www.sec.gov/Archives/edgar/data/809248/000121390019007896/f8k12b043019_carrolsrestaur.htm)，[successor 使用不同 CIK 的 8-K](https://www.sec.gov/Archives/edgar/data/1981792/000110465923090466/tm2323105d1_8k12b.htm)。

### Ticker

Ticker 是证券和交易所层面的标识，不是公司身份主键。它可能因为以下原因变化：

- 公司改名或品牌重塑；
- 合并、重组、SPAC 交易；
- 转板或更换交易所；
- 上市证券类别变化；
- 破产重组、重新上市；
- 公司主动申请更符合新业务的交易代码。

名称变化时，ticker 既可能变化，也可能不变。一个 CIK 还可能对应多个证券类别、多个 ticker，甚至没有 ticker。SEC 自己也说明 ticker/CIK/exchange 文件只是关联数据，不保证准确性或覆盖范围。[SEC EDGAR 数据说明](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)。

所以 ticker 只能当作可变属性，不能用于拼接公司历史。

---

## 2. 简单更名应该怎么处理

如果只是：

```text
Old Company Name
→ New Company Name
CIK 不变
法律主体不变
财务报告口径没有重大变化
```

那么应当：

- 保留同一个 `company_id`；
- 保留同一个 `primary_cik`；
- 更新 `display_name`；
- 更新 ticker；
- 把旧名称保存在 `former_names` 历史中；
- 连续使用这个 CIK 的全部 Company Facts。

SEC submissions API 本身就提供 current name、former names、ticker 和 exchange 元数据；Company Facts 也是按 CIK 提供事实。[SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)。

这种情况下没有所谓“旧公司财务数据”。它只是同一个 filer 在旧名称期间提交的历史财务数据，当然应该进入连续时间序列。

---

## 3. 新 CIK 情况下是否应该合并旧财报

默认不应该。

最合理的原则是：

| 层面 | 旧 CIK 数据如何处理 |
|---|---|
| 原始数据留存 | 保留 |
| 审计和证据追溯 | 保留 |
| 8-K succession 事件研究 | 可以读取 |
| 当前年度财务指标 | 默认不用 |
| 跨 CIK YoY | 默认禁止 |
| 合并为一条历史曲线 | 必须经过明确连续性审核 |

例如新 CIK 代表：

- 反向并购后的新申报主体；
- SPAC 交易完成后的上市主体；
- 不同资产、资本结构或会计基础的新公司；
- predecessor 只覆盖旧业务，successor 只覆盖新业务。

这时把旧 CIK 的收入直接拿来算新 CIK 的 YoY，通常就是错误的，因为分子和分母可能根本不是同一个经济范围。

正确结果应该是：

```text
B02 Revenue YoY = NOT_MEANINGFUL
```

而不是为了得到一个数，强行从 predecessor CIK 补上一年。

---

## 4. 只从新 CIK 的 Company Facts 取数据是否更简洁

对“标准数值指标计算”而言，我赞成，而且这是更安全的默认规则。

建议固定为：

```text
标准财务指标：只使用当前 primary/successor CIK
同比比较：只允许相同 CIK
事件扫描：可以扫描完整 role chain
旧 CIK 数据：单独归档，不进入当前指标计算
```

当前项目其实已经基本这样做：

- 目标 10-K 优先选择 `primary/successor`：[sec_pipeline.py:1985](/Users/lyuhongwang/Documents/SEC_metrics/scripts/sec_pipeline.py:1985)
- prior 10-K 必须与目标 CIK 相同：[sec_pipeline.py:2015](/Users/lyuhongwang/Documents/SEC_metrics/scripts/sec_pipeline.py:2015)
- `successor_predecessor`、stub period、major reorg 或跨 CIK 都会阻止 YoY：[sec_pipeline.py:3323](/Users/lyuhongwang/Documents/SEC_metrics/scripts/sec_pipeline.py:3323)
- 标准指标只围绕选中的 target CIK 计算：[sec_pipeline.py:4245](/Users/lyuhongwang/Documents/SEC_metrics/scripts/sec_pipeline.py:4245)

所以当前项目并没有直接把两个 CIK 的收入、净利润加在一起。现在多做的事情主要是：

- 为所有 role CIK 建立 filing inventory；
- 下载所有 role CIK 的 Company Facts；
- 在事件、治理、风险文本等环节读取 predecessor 材料。

真正可以简化的是：

> 不再默认下载 predecessor 的 Company Facts；只有当前计算 CIK 获取 Company Facts，predecessor 只保留 filing/8-K/身份关系材料，必要时再按需下载。

---

## 5. 一个重要例外

如果 successor 的新 CIK 所提交的当前 10-K 本身重新列报了可比的历史期间，那么这些比较期事实可能已经出现在新 CIK 的 Company Facts 中。

这种情况可以使用，因为依据是：

```text
同一个当前 CIK
+ 当前申报主体正式提交
+ 明确的 accession
+ 相同会计列报基础
+ 完整年度期间
```

而不是因为我们从旧 CIK 把一个同名 concept 拼了过来。

因此建议：

```text
能从当前 CIK 的正式列报中得到比较期 → 使用
只能从 predecessor CIK 得到比较期 → 默认不跨接
```

取不到 prior year 时，宁愿输出 `NOT_AVAILABLE_SEC` 或 `NOT_MEANINGFUL`。

---

## 6. 我建议项目采用的最终边界

不需要大改表结构，也不需要删除 predecessor 信息。用现有字段就能形成清晰规则：

```text
primary_cik / successor role
    → 标准 Company Facts 和当前财务指标

predecessor role
    → 历史存档、8-K succession、审计证据

entity_continuity_status
    → 判断是否允许同比

ticker / display_name
    → 只作为可变展示属性
```

输出上则明确分开：

- `metrics_matrix.csv`：只放当前计算 CIK 的标准财务指标；
- `events.csv`：允许包含多个 role CIK，但逐条保留 `source_cik`；
- 可选 `predecessor_history.csv`：保存旧 CIK 指标，仅供历史参考，不与当前序列混算。

最精炼的原则是：

> 简单更名不会换 CIK，直接延续历史；真正出现新 CIK 时，保留旧数据但默认断开计算。标准财务指标只使用当前 CIK，跨 CIK 只服务于身份、事件和审计，不服务于自动同比。

还有一个不能删除的保护：即使只取当前 CIK，也仍需保留 `entity_continuity_status`，因为 successor 有可能承接旧 CIK，CIK 没变但经济主体或报告口径已经发生重大变化。


# 如果CIK变化的话，company_id，name，role是否需要分配新的？
CIK 是主身份，名称只是可变属性。SEC submissions 中的 `current name/former names` 主要用于解释和校验名称历史。[SEC API 说明](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)。

## 四种情况的处理

| 情况 | `company_id` | `display_name` | `primary_cik` | `roles` | 财务数据 |
|---|---|---|---|---|---|
| 同 CIK，简单更名 | 不变 | 更新为当前名称 | 不变 | 保持 `primary` | 连续处理 |
| 新 CIK，明确 successor/predecessor | 通常不变 | 更新为当前名称 | 改为新 CIK | 新 CIK=`successor`，旧 CIK=`predecessor` | 只用新 CIK 计算 |
| 新 CIK，实际上是不同公司/业务 | 新建 | 新公司名称 | 新 CIK | 两家公司各自 `primary` | 完全分开 |
| CIK 不变，但重大重组/反向并购 | 未必能简单沿用 | 当前名称 | 不变 | 可能仍是 `primary` | 仍应中断可比性 |

## 1. 同 CIK、仅名称变化

例如：

```text
CIK 123456
Old Name → New Name
```

推荐处理：

```text
company_id   = 保持不变
primary_cik  = 123456
display_name = New Name
role         = primary
former_name  = Old Name
```

财务指标按同一家公司连续计算。实际上 pipeline 已经知道 CIK，不应该再依靠名称匹配去连接 Company Facts。

正确身份匹配顺序是：

```text
CIK
→ SEC submissions.current name / former names 校验
→ ticker 仅作辅助显示
```

不能反过来用 former name 作为主键，因为不同公司可能使用过相同或相近名称。

## 2. CIK 变化，但存在明确继任关系

例如：

```text
旧 CIK 813828
新 CIK 2041610
SEC 文件证明 successor/predecessor
```

按照当前项目“逻辑公司”的定义，可以继续使用同一个 `company_id`：

```text
company_id  = paramount_skydance_paramount_global
display_name = 当前公司名称
primary_cik = 2041610
roles       = successor:2041610;predecessor:813828
entity_continuity_status = successor_predecessor
```

这里，同一个 `company_id` 只表示：

> 两个 CIK 属于同一条经过确认的公司继任链。

它不表示：

> 两个 CIK 的财务数据可以直接合并或计算同比。

标准财务计算仍然应该：

```text
当前指标      → 新 CIK
prior year   → 只能找新 CIK 自己披露的比较期
旧 CIK 财报   → 历史存档
跨 CIK YoY   → NOT_MEANINGFUL
8-K 事件      → 可以扫描两个 CIK，但保留 source_cik
```

## 3. CIK 变化，而且实际上是不同公司

以下情况通常应该创建新的 `company_id`：

- 被收购公司与收购方；
- 分拆后独立上市的新公司；
- 反向并购后业务实质完全替换；
- SPAC 壳主体和交易后完全不同的运营企业；
- 旧主体仍然存在并继续独立申报；
- 没有明确 SEC succession 证据，只是名称或 ticker 相似。

例如：

```text
old_company_id, Old Company, old_cik, primary
new_company_id, New Company, new_cik, primary
```

两家公司之间可以保存：

```text
acquired_by
spun_off_from
merged_into
```

但不要错误地使用 `predecessor/successor` 把它们拼成一条财务时间序列。

## 4. `role` 应该属于 CIK 关系，而不是公司名称

如果 CIK 变化，真正需要新建的是一条 CIK-role 关系：

```csv
company_id,cik,role,is_current,valid_from,valid_to,evidence_accession
company_a,2041610,successor,true,2025-08-08,,000...
company_a,813828,predecessor,false,,2025-08-07,000...
```

因此：

- `company_id`：是否新建，取决于逻辑公司是否连续；
- `display_name`：更新为当前名称，旧名称进入名称历史；
- `role`：新 CIK 必须新增 role，旧 CIK 的 role 变成 predecessor；
- `primary_cik`：指向当前用于指标计算的 CIK。

当前 [company_registry.csv:10](/Users/lyuhongwang/Documents/SEC_metrics/config/company_registry.csv:10) 把这些关系压缩在一个 `roles` 字符串里，还没有 `valid_from/valid_to/evidence_accession`。

## 最重要的三个判断不要混在一起

```text
SEC filer 身份
→ 由 CIK 判断

是否属于同一公司继任链
→ 由 company_id + role + succession 证据判断

财务数据是否可比
→ 由 CIK、报告期间、会计口径和 continuity status 判断
```

因此最终规则是：

> 同 CIK 更名：同一 `company_id`、同一财务序列。  
> 新 CIK 且确认继任：可以保留同一 `company_id`，但新增 role，并默认中断财务可比性。  
> 新 CIK 且不是同一逻辑公司：创建新的 `company_id`，财务数据完全分开。