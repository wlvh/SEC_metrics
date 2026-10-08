# 计算端实测：只读代码、没有 HOME、只有最小 git 索引（2026-10-02）

为 #54 的 OpenShift 程序边界实测本方计算端实际依赖什么。记录见 `probe.json`。没有调用 SEC，也没有调用模型。

## 做法

- **来源根**：用 `evidence/issue47_acquired/` 恢复出的数据根（1547 行，账本 sha256 `61252ac5…`，检查点 `sha256:8fd47964…`）。
- **代码**：复制批次运行树（索引在 `fc73df2d`，工作文件同步到 `815c7820`，并打了注册补丁），不带 `.git`。
- **环境**：计算用 `env -i PATH=… HOME=/nonexistent TMPDIR=<scratch> PYTHONPYCACHEPREFIX=<scratch>`。
- **跑法**：用 `period-batch/period_runs.py` 跑 Marriott FY2023 的 B01、B04、D01。

1. **没有 `.git`**：三个指标都停在安装，错误是 `git ls-files catalog config … exit status 128`。调用链为 `normal_run_v3._install_case_inputs` → `annual_runtime._authority_files`；这个安装函数是 #28 普通路线与本方历史路线共用的冻结代码。
2. **补一个最小 `.git`**：`git init`；对象用 alternates 指向运行树的对象库；`git read-tree fc73df2d…`；`git update-ref HEAD fc73df2d…`。共 9.3 MB，`git ls-files catalog config` 与运行树相同。再把来源准备端登记的那一条信任日志（`.git/ordinary-source-authority/acquired/<账本 sha256>.json`）复制进来。**这一步只是实测捷径**：复制别处的登记，等于复制私有日志冒充授权，正式交接不能这样做。正式做法见 `../README.md` 5.2 第 3 条。

   补完后，三个指标都出了公共行：B01 23,713,000,000，B04 3,083,000,000，D01 为风险因素标题。另一进程冷读三个 Run 都是 FROZEN，run 与 result 和创建时一致；B04 在关闭推导缓存时又冷读一次，结果相同。前后各取一次代码树清单比对，14213 个文件（含 `.git`）的路径、大小和修改时间都没有变化。
3. **对照**：在完整检出的运行树上用同一来源根跑同样三个指标。run_id、result_id、公共行哈希、冷读状态全部一致，三个行收据文件逐字节相同。

## 结论与边界

- 本方计算路径不读 HOME，也不写代码目录；读写位置见 `../README.md` 5.3。
- 计算端现在离不开 git 索引，而且 `.git` 必须是目录。这来自 #28 的冻结共用安装，不是历史路线自己加的要求。
- 一个期间的数据根有 684 MB，其中 650 MB 是整本账本所有成功行的获取原件（3098 个文件）。原因是冻结安装和冻结校验都按整本账本处理，见 `../README.md` 5.2 第 1 条。
- 本次只测了一个期间、三个指标，没有测前身 CIK、历史分片驻留期间或事件窗口指标，也没有测 #54 的公司交接物。这些在拿到 #54 的固定实现后，在本方已支持的入口上再验证。
