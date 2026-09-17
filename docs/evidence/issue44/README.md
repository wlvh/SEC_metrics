# Issue #44 / PR #45 验证记录

本目录是 PR #45 本地验证的精简、可从 PR 直接访问的记录；权威内容在
`verification_record.json`（两端提交、组合 tree、命令、Python/关键依赖版本、退出码、
日志路径）。它不是 pipeline 的 acceptance source，也不替代 GitHub Actions 结果。

两组证据必须分开读：

| 证据 | 对象 | 位置 |
|---|---|---|
| GitHub Actions（`vnext-fast.yml`、`metrics-reference.yml`） | `main` + PR #45 当前 head | PR #45 的 checks |
| 本地组合演练 | PR #43 固定远端提交 `8346c326…` + PR #45 修复提交 `69e5df03…` 的本地临时 merge commit `3599b196…`（tree `1e1bff93…`，未推送，worktree 已移除） | 本目录 `logs/r3_combo_*` |

已验证的代码提交是 `69e5df03fa5ad87535ea150603a387d1ff2e7a26`；添加本目录的证据提交只包含
`docs/evidence/issue44/`，代码、数据与生成表与 69e5df0 逐字节相同。

结果摘要（全部本人本地运行）：

- 参考表 `--check`：PASS；专项测试 49 项 OK；main fast suite 47 cases PASSED；能力契约对齐 PASS。
- 干净副本：`git archive HEAD` 导出到无 `.git`、无 PR #43 对象的目录，用 `no_network_driver.py`
  在 Python 进程内把 `socket.socket` / `create_connection` / `getaddrinfo`、`urllib.request.urlopen`
  与 `subprocess.Popen` 替换为抛错后运行 `--check` 与测试：check rc 0，49 tests，0 failures。
  这只是 Python 层的禁网/禁子进程边界，**不是操作系统级网络隔离**。
- 组合演练：自动合并 `AGENTS.md`、`TESTING.md`，无冲突；合并树上 `--check` PASS、49 测试 OK、
  能力契约（base = PR #43 提交）PASS、PR #43 的 `run_fast_tests_v2.py` 在安装其固定
  `tokenizers==0.22.2` 后 122/122 PASSED。
- 首轮（b1a7687）用系统 Python 跑 PR #43 fast suite v2 时仅两个模块因缺少 tokenizer 失败，
  并在纯 PR #43 临时 worktree 同条件复现；见 `logs/r1_combo_fast_suite_v2_system_python_summary.json`。

未覆盖：独立人工 / Codex / GPT 的 APPROVE（本目录只记录自审）；任何真实模型或 SEC 调用、发布、
active 切换或生产采纳。
