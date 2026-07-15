# SEC_metrics Raw Data 后端交接说明

---

## 1. Raw Data

当前 raw evidence 约 218 MB，主要包括：

| 类别 | 例子 | 格式 |
|---|---|---|
| 公司申报索引 | `submissions/CIK0001048286.json` | JSON |
| 标准事实聚合 | `companyfacts/CIK0001048286.json` | JSON |
| Filing 目录 | `accession_materials/.../index.json` | JSON |
| Filing 主文档 | `*.htm` | HTML / Inline XBRL |
| XBRL instance | `*_htm.xml` | XML |
| Filing summary | `FilingSummary.xml` | XML |
| 8-K header | `*.hdr.sgml` | SGML/text |
| Taxonomy/附件 | `.xsd`、linkbase XML、exhibit、图片、ZIP | 多种 |
| HTTP 侧车 | `<文件名>.headers.json` | JSON |
| 请求日志 | `requests_log.csv` | CSV |

每个抓取文件通常有一个 `.headers.json` 侧车。它和 `requests_log.csv` 是回灌请求元数据的来源；导入完成后，不要求将每个侧车再次作为 SEC RawAsset 保存，可以整体归档交付包。`requests_log.csv` 当前字段为：

```text
timestamp_utc
method
url
status_code
purpose
local_path
headers_path
content_length
sha256
user_agent
retry_attempt
error
```

交付时会额外提供 manifest，避免你从目录名猜字段。

### 2.1 交付 manifest

每个文件/请求 attempt 会有一行 manifest，最低字段：

```text
observation_key
run_id
method
requested_url
observed_at_utc
http_status
purpose
retry_attempt
error
relative_file_path       无 body 时为空
content_length           无 body 时为 0
sha256                   无 body 时为空
accession                可空
document_name            可空
company_id               可空
cik                      可空
```

`observation_key` 用于幂等导入。后端不得通过文件夹名称反向推断 accession、CIK 或公司。

---

## 3. 两个最重要的对象

### 3.1 RawAsset：文件内容本身

同一组 exact bytes 只保存一次。

建议字段：

```text
raw_asset_id          SHA-256；主键
content_length        字节数
storage_uri           对象存储或共享存储 URI
first_seen_at_utc     首次入库时间
media_type_hint       可空
```

规则：

```text
raw_asset_id = sha256(exact bytes)
```

数据库或上传服务应重新计算 SHA-256，并与 manifest 对账。

### 3.2 SourceObservation：一次请求记录

同一文件可以在不同 URL 或不同时间被请求多次；每次都保存一条 SourceObservation。

建议字段：

```text
source_observation_id       可由后端生成
observation_key             交付 manifest 中的幂等键；唯一
run_id
method
requested_url
observed_at_utc
http_status
response_headers_json
content_type
purpose
retry_attempt
user_agent              可空
error
raw_asset_id          可空
company_id            可空
cik                    可空
accession              可空
document_name         可空
```

例子：

```text
同一 bytes 从两个 URL 获得
→ 1 条 raw_asset + 2 条 source_observation

同一 URL 后来返回不同 bytes
→ 2 条 raw_asset + 2 条 source_observation

网络连接失败且没有 body
→ source_observation.raw_asset_id = null

HTTP 403 但返回了 body
→ body 仍可保存为 raw_asset
```

---

## 4. 最小六张表

请按以下逻辑对象建库；具体字段类型、索引名称和 ORM 由你决定。

### 4.1 `pipeline_run`

一行代表一次采集或回灌运行。

最低字段：

```text
run_id
started_at_utc
finished_at_utc nullable
status              RUNNING | SUCCEEDED | PARTIAL | FAILED
source_manifest_version
notes nullable
```

### 4.2 `company`

一行代表一个逻辑分析公司。

最低字段：

```text
company_id
company_name
ticker nullable
```

### 4.3 `company_cik_role`

支持一个逻辑公司对应多个 SEC CIK，例如 successor/predecessor。

最低字段：

```text
company_id
cik
role                PRIMARY | SUCCESSOR | PREDECESSOR | RELATED
valid_from nullable
valid_to nullable
```

唯一约束建议：

```text
(company_id, cik, role, valid_from)
```

### 4.4 `filing`

一行代表一个 SEC accession。

最低字段：

```text
accession            主键
company_id nullable
cik
form
filed_date nullable
report_date nullable
primary_document nullable
```

### 4.5 `raw_asset`

按 §3.1。

### 4.6 `source_observation`

按 §3.2。

`raw_asset_id`、`run_id`、`company_id`、`accession` 应设置相应外键；允许为空的字段按上述定义执行。

---

## 5. 必须实现的写入规则

1. **对象存储保存原始 bytes，数据库保存 URI 和元数据。**
2. **SHA-256 相同的 bytes 只保存一份 RawAsset。**
3. **每次请求单独保存 SourceObservation。**
4. **重复导入同一批数据不得产生重复记录。**
5. **同一 ID/唯一键出现不同内容时必须拒绝或进入冲突队列，不得覆盖。**
6. **RawAsset 和 SourceObservation 采用 append-only；普通应用账号不得 UPDATE/DELETE。**
7. **`local_path` 不能作为权威地址。** `/Users/...` 等路径必须转换为后端控制的 `storage_uri`。
8. **请求失败不等于没有记录。** 失败、重试和错误 body 都需要审计。
9. **只做结构校验。** 后端不判断文件里的财务内容是否正确。

---

## 6. 后端负责的校验

需要做：

```text
必填字段
字段类型
SHA-256 与实际 bytes 一致
content_length 与实际 bytes 一致
外键存在
枚举合法
唯一键不冲突
重复导入幂等
```

不需要做：

```text
XBRL concept 是否正确
期间是否正确
数值是否合理
财务公式是否正确
某个指标是否应当发布
```

---

## 7. 最低查询能力

Raw 层完成后，至少应支持：

1. 按 `raw_asset_id/SHA-256` 取得文件元数据和下载 URI；
2. 按 URL 查看全部请求历史；
3. 按 CIK 和 accession 查看相关文件；
4. 按 run_id 查看一次导入的成功、失败和重试；
5. 按时间范围查询新增 RawAsset；
6. 从 SourceObservation 定位到 RawAsset；
7. 从 filing 定位其所有来源文件。

不需要提供财务指标查询 API。

---

## 8. 联调样本

首次联调我们会提供：

1. submissions JSON + headers；
2. Company Facts JSON + headers；
3. 一套完整 10-K accession 文件；
4. 一套 8-K hdr.sgml + HTML；
5. 一次成功请求；
6. 一次重试后成功；
7. 一次 HTTP 错误但有 body；
8. 一次 transport failure、无 body；
9. 一组相同 bytes 的重复导入；
10. 一个 successor/predecessor 公司映射。

---

## 9. 验收清单

以下全部通过，即可认为 Raw 层完成：

- [ ] 同一文件导入两次，`raw_asset` 仍只有一条；
- [ ] 两次不同 URL 请求可以引用同一个 RawAsset；
- [ ] 同一 URL 返回不同 bytes 时不会覆盖旧 RawAsset；
- [ ] HTTP 错误 body 可以保存并追溯；
- [ ] 无 body 的失败请求允许 `raw_asset_id` 为空；
- [ ] 重复导入同一 manifest 不增加重复行；
- [ ] SHA-256 和 content length 与对象存储实际内容一致；
- [ ] 可以按 CIK/accession 找到全部相关文件；
- [ ] 普通应用账号不能修改或删除 RawAsset/SourceObservation；
- [ ] 数据库代码中没有任何财务指标或 XBRL 业务判断。

---
