# Marriott 旧 LIVE D04 接收、基线补件与基础集成核对

接班会话（2026-10-04，云端容器，root UID，`/home/user/work`）。不是原 Codex Linux UID1000 工作区，也不是 OpenShift。本轮新增真实 SEC/provider/paid 调用 **0/0/0**；此前 31/120 保留为原授权历史，不重置、不消费。产品代码零改动。

## 结论

| 项 | 结果 |
|---|---|
| A 原 live 现场 | **本容器不可见，未取得备份**；缺失项与接收核对清单见 [site-handover.json](site-handover.json)。未用重新取数掩盖。 |
| B D04 基线接收 | **通过（基线来源段）**：处理包 f252a7a4 在 Linux 重建并认证；按基线补齐工作镜像后，公司来源导出与固定完整基线根导出 `checkpoint_id` 相同；原 V14 程序重新得到原 Result `e523b7a9…`，另进程重入无新候选，独立冷导出行字节一致。 |
| B 与 LIVE FY2025 当前来源的等价 | **未执行**：需要原现场的 company-state/handoffs（A 缺失）。不宣称等价、不自动放行。 |
| C 基础 7ed952bb + PR55 增量 | 运行目录 601 文件逐 blob 等同 83；两类安装运行树逐文件相同；PR55 全增量 3-way 应用仅 5 份治理文档冲突；67 项公司测试两侧 OK。 |

## B：按基线补件，不是恢复最早账本行正文

1. 原脚本 `materialize-d04-handoff.py`（7ed952bb）在新目录重建四个分离根，2.48 秒：processing `sha256:f252a7a4…`、652 程序成员、8 SEC/proof 成员全部字节核对（[log](materialize.log)）。
2. 固定 83 `export` 在未改的 `legacy-source-input` 上复现 `COMPANY_SOURCE_DECLARED_LOCATOR_NOT_CARRIED:evidence/submissions/CIK0001048286.json`（[log](repro-export.stderr.tail.log)）。
3. 原因：`_validate_admission_bytes` 要求目标 URL 每一行声明的 `repo_relative_path` 都被携带。第 6 行（legacy，元数据 147610/`c42b3356`）声明的是基线**工作路径**；固定 83 `config/normal_candidate_sources_v1.json` 把该路径绑定为 147990 字节、blob `304773ba`（正文 `9112ca35…`），headers blob `367dd771`。缺的是这份基线镜像，不是第 6 行原正文。
4. **纠正交接范围**：同一机制不只影响 submissions。逐个补件依次暴露 companyfacts、10-K accession 路径；全量统计 Marriott 行缺失声明定位 134 个（78 个唯一路径），**全部**由基线登记、0 个未登记。导出范围按来源发现 + `accession_materials/*.hdr.sgml` 普查决定，所以 8 成员传输天然不够。
5. [prepare-baseline-mirrors.py](prepare-baseline-mirrors.py) 复制 `legacy-source-input` 到新准备根（原目录不动），只写入基线配置登记路径，字节取自登记的 git blob 并核对大小/blob ID，拒绝覆盖已有成员；不写账本、manifest、checkpoint 或 trust。添加清单见 [prepare-v3-added.json](prepare-v3-added.json)。
6. 导出通过（6.414 秒）。对照直接以固定 83 checkout 作完整基线根导出：两者 `checkpoint_id` 均为 `sha256:1b436ef0…`，73 文件、29 URL、账本 `709b97c9`、`files` 完全相同（[comparison](source-export-comparison.json)）。基线路径携带 147990/`9112ca35`；D04 原输入 147714/`e3eeefe3` 仍在其不可变定位，未被镜像替换。147610/`c42b3356` 没有进入任何路径。

补件只证明材料完整；与原判断等价由下一步原程序验证。

## 认证、公司 D04、重入与冷导出

| 步骤 | 结果 | 秒 |
|---|---|---:|
| install-runtime local（issue_54_v4） | authority `792b5095…`，与基础方 Mac 安装相同 | 4.958 |
| install-runtime ordinary（issue_54_v1） | authority `0d595956…` | 4.757 |
| authenticate_processing（local 运行树） | PASS：LIVE、输入 `bcab858f`、源 `dfe61c69`、闭包 `0f724fa7` | 0.117 |
| 篡改处理字节 / 错公司 | 拒绝：`BOUND_FILE_CHANGED:processing-source.json` / `WRONG_COMPANY_OR_AUTHORITY` | — |
| install 到 local 运行树 | 拒绝 `COMPANY_SOURCE_BASELINE_OR_MODE_CHANGED`：local 只收空历史任务基线，已保存基线归 ordinary；符合设计 | 0.3 |
| install（ordinary） | INSTALLED，`1b436ef0…` | 0.821 |
| compute D04 首次 | `PROCESSING_INPUT_REJECTED`：未装离线 tokenizer（`TOKENIZER_DEPENDENCY_UNAVAILABLE`），失败记录保留 | 17.764 |
| 按文档 hash 安装 tokenizers 0.22.2 后 compute | **CANDIDATE_READY**，Result `sha256:e523b7a9b36b787596d7de5100746a3c23b44ca336b4791d64c7df9ef7555371`（=#28 原 Result），Run `3f8360f2…`，WITHHELD/TEXT_QUAL，`native_assessment_completed=true` | 296.137 |
| 另进程重入 | NO_SOURCE_CONTENT_CHANGE，同 attempt `835499fc`，无新候选 | 123.353 |
| export-results 首次 | 我漏传创建者运行树，ordinary 树被当作处理程序而被重叠守卫拒绝；保留为操作失败，不是产品缺陷（[记录](result-export/first-attempt-missing-creator-runtime.json)） | 0.840 |
| export-results（`--runtime-root processing-runtime --runtime-root ordinary`） | EXPORTED，`REPLAY_VERIFIED_CONTENT_NOT_ACCEPTED`；冷复放行 `7dc88ba4`/`22863cf2` 与计算行逐字节相同 | 124.120 |

D04 行：FY2025、10-K `0001048286-26-000007`、TEXT_QUAL「未披露持续经营疑虑」，证据为原 10-K `c372495a`。这是原判断在原基线来源上的复现与独立冷读，**不是业务接受**，也不改变 #28 原 WITHHELD 状态。

负例（[negatives.json](negatives.json)）：把 e3eeefe3 原输入放到基线路径冒充镜像，导出以 `TRUSTED_SAVED_BASELINE_BYTES_CHANGED` 拒绝；篡改包副本中实际绑定的 e3eeefe3 headers，安装以 `COMPANY_SOURCE_BYTES_CHANGED` 拒绝且未导入。缺源检查、最新失败规则、行号、legacy 行元数据都未改。

## 未完成：与 LIVE 当前来源的等价

本地 `run` 的 D04 需要 `processing.json` 同时给出原 SEC 版本（上面的 ordinary 基线导出/信任即可充当）与当前 acquired 来源；后者是原现场 `company-state` 中的 FY2025 LIVE 版本（来源 `671a25cd…`/`7050dd9e…`）。原现场不可见，所以 `current → original` 的 `source_equivalence` 未执行。取得现场后只需：原 SEC 版本 = 本目录导出包＋`source-trust`，`source_runtime` = ordinary 运行树，再跑一次 D04；不需重新获取或重跑其他 38 项。若不等价，如实报告。

## C：相对固定基础的差异核对

[integration-delta-check.json](integration-delta-check.json)：`7ed952bb` 叠加 PR55 18 个运行路径后，`scripts/tools/catalog/config/requirements` 601 文件与 83 逐 blob 相同，`evidence/` 和 frozen-parent-v10 差异 0；在该组合树上安装 ordinary/local 运行树，authority 与 83 相同，安装树 749/753 文件逐字节相同。因此本目录 D04 接收、原 Marriott 首跑/复跑所用运行程序按真实差异直接适用，不重跑财报链。

PR55 全部 312 路径 3-way 应用到 `7ed952bb`：307 干净，`AGENTS.md`、`TESTING.md`、`capability_contract.json`、`docs/business_user_guide.md`、`interact.md` 冲突（main 保留自身治理文档）。这些要在基础进入 main、PR55 改目标后的实际集成中合并；本次未改 PR55 目标、未推送集成结果。临时取 main 侧文档后，6 个公司测试模块 67 项两侧均 OK（[83](company-tests-83.log)、[组合](company-tests-composed.log)）。基础方的发布扫描/旧 fixture 阻塞与 main CI 仍由基础集成负责，不由此代替。

## 复现

```sh
# 交接材料（需 fetch task/issue28-foundation-main-candidate 与 task/b06-new-source）
python3 docs/evidence/issue28_foundation_integration_20261004/materialize-d04-handoff.py --repository "$PWD" --output-root /abs/d04-handoff
# 基线补件（在固定 83 checkout）
python3 docs/evidence/issue54_company/d04-handoff-intake/prepare-baseline-mirrors.py --repository "$PWD" --program-root "$PWD" \
  --legacy-source /abs/d04-handoff/legacy-source-input --output-root /abs/prepared $(sed 's/^/--path /' <(python3 -c "import json;[print(a['path']) for a in json.load(open('docs/evidence/issue54_company/d04-handoff-intake/prepare-v3-added.json'))['added']]"))
python3 tools/vnext_company.py export --source-root /abs/prepared --output-root /abs/export --trust-root /abs/source-trust --company marriott_international --metric D04
python3 tools/vnext_company.py install-runtime --kind ordinary --output-root /abs/rt
python3 -m pip install --no-deps --require-hashes --target /abs/deps -r requirements-continuous-context.txt   # PYTHONPATH=/abs/deps
python3 /abs/rt/tools/vnext_company.py install --package-root /abs/export --state-root /abs/state --trust-root /abs/source-trust --company marriott_international
python3 /abs/rt/tools/vnext_company.py compute --state-root /abs/state --trust-root /abs/source-trust --company marriott_international --metric D04 \
  --processing-package /abs/d04-handoff/processing --processing-runtime /abs/d04-handoff/processing-runtime --processing-trust-root /abs/d04-handoff/processing-trust
python3 /abs/rt/tools/vnext_company.py export-results --state-root /abs/state --output-root /abs/out --trust-root /abs/source-trust --company marriott_international \
  --runtime-root /abs/d04-handoff/processing-runtime --runtime-root /abs/rt --processing-trust-root /abs/d04-handoff/processing-trust
```

本容器中的 state/Run 是可在约 10 分钟内由上述 Git 对象确定性重建的回归现场（Result ID 已证明可复现），未另建备份平台。
