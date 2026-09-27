# `8a45c46d` 定向独立审阅

**结论：PASS_WITH_BOUNDS。** 现有材料足以支持：当前普通更新入口在隔离状态根为 Enphase FY2025 D04 创建一个新 Run，得到与原完成收据相同的 Result ID；独立进程从安装副本重读通过；相同输入再次触发只增加一次尝试记录，不新建候选 Run。它不单独证明新 Run 逐条消费了 173—178 的原响应字节，也不证明原调用目录及旧私有 Run 的所有文件逐字未变。后两句如需作为严格结论，应补只读身份/字节对账或收窄措辞。

审阅范围为提交 `8a45c46d61b4b02bbb6189341e029e26b055b9d8` 相对 `b868ac424a1580db1439503b541ed7135d6361e4` 新增的本目录 21 个文件；只读对照原 `finish-summary.json`、`cold-summary.json`，并核对当前 `ordinary_update_cycle.py`、`normal_run_v3.py` 的相关分支。提交没有修改这些源码或原摘要。运行了一次短命令 `python3 .../reconcile.py`，返回 `PASS_ORIGINAL_REAL_RESULT_REUSED_BY_CURRENT_NORMAL_UPDATE`；另以只读检查确认四个保存的退出码依次为 `0/1/0/0`、原摘要 SHA 与 `reconciliation.json` 一致。本审阅没有重跑 1150/158/430 秒作业，也没有发请求。

可确认的事实：

- `run.log`、`result.json` 与新 Run manifest 的短对账一致：`UPDATES_READY / CANDIDATE_READY`，原 Run ID `128f6cca...`、当前 Run ID `396c3125...`，Result ID 同为 `sha256:7bf9ea83...`，当前需求闭包为 `sha256:6372c5db...`。原完成与冷读摘要确实登记 173—178 和这一 Result ID；原摘要自身的 129/129/49 是较早时点，不能与本次 143/143/52 相减归到本次更新。
- 本次运行前后总账计数均为 provider/paid/SEC `143/143/52`，行数均为 195；调用目录名称和五个指定哨兵文件哈希不变。预期网络入口受到脚本拦截且拦截记录为空。由此支持**本次无新增已登记真实调用**；`new_real_calls: [0,0,0]` 字段本身是脚本常量，不应单独当成计数证据。
- 最终 `cold-read.py` 先把安装副本放入导入路径，并断言 `normal.ROOT` 为该路径；它重验候选及生成的两份行文件。最终 `cold.exit=0`、`cold-result.json` 显示 Result ID、需求闭包和矩阵行哈希一致，私有历史 930 个当时已有文件前后哈希相同、变化 0。第一次 `cold-initial.exit=1`、历史字节不变断言失败，被 README 保留且明确排除；但其 JSON 中仍错误写着 `PASS_INDEPENDENT_INSTALLED_RUNTIME_COLD_READ`，因此必须同时读取退出码和 `history_bytes_unchanged=false`。首次新增文件的具体路径未记录，归因为 Python 字节码缓存与修后禁用写缓存相符，但本包不能单独证明每个新增文件的类型。
- 重复执行的 `repeat.exit=0`，新尝试 ID 为 `aa07a23b...`，成功指针仍为首次的 `5a5d4e4b...`，`new_candidate_created=false`，原成功包哈希不变。当前源码在输入描述与前次相同时走 `NO_SOURCE_CONTENT_CHANGE`，跳过 `create_normal_run`，所以“无新 Run”与代码及保存终态一致。
- 对账实际读取矩阵行，核对 Enphase Energy、D04、`TEXT_QUAL`、空数值和 `2025-01-01` 至 `2025-12-31`；Result 保持 `WITHHELD / D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`。这是**规定来源范围未见持续经营疑虑披露**的文字结论，不能转述为公司财务健康保证。它不增加十家公司已完成候选数，也不授予正式采纳、生产切换、跨财年在线自动更新或 390 坐标验收。

**需要维持的证据边界。** `run-existing-real.py:95` 的 173—178 是预填常量，`reconcile.py:36-40` 只把原摘要的序号与各次 Result ID 对齐；本包未将当前安装 Run 的来源/评估输入身份与原摘要中的 `source_id`、`assessment_input_id` 逐项比较。`run-existing-real.py:31-36,58-61,83-107` 比较的是计数、行数、调用目录名和选定哨兵，未对 173—178 调用原件或旧私有 Run 做整树前后哈希。因此可说“同一 Result 身份由当前入口重建”“所列哨兵及计数不变”，不宜把这些观察扩写成“每份原响应/旧 Run 原件已证实逐字未变”。如要升级这一结论，只需对现有记录做一次只读的身份与哈希核对，无需重发请求或重跑长任务。
