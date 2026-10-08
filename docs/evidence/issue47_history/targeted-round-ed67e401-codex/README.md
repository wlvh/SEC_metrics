# 11 个定向位置：同一 ed67e401 规则的重算与阅读

2026-10-03，程序树 `68025386` 加注册补丁，再重铸；Requirement `issue_47_v1`，闭包 `sha256:ed67e40130d5ade19f1720537cd7467de337b9169ddb33f3596c65e97855f90c`。开发分支随后只合并 #28 的 D03 证据并登记，不移动此规则身份。来源以 `tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out /workspace/work/issue47-saved-sources` 恢复，1,547 行；不恢复 SEC 花费权限。

`period-batch/frame_batch.py` 在恢复的根上运行下面 11 个位置，`--workers 3`；每期仍为 `--layout shared --block on --memo on --memo-off-read-back 1`。驱动与另进程阅读禁用网络，新增 provider/paid/SEC `[0,0,0]`。十个 Run 冻结并出公共行，十个都经另进程冷读、再关闭派生缓存冷读，Run/Result 相同。Lumen FY2021 是具名边界拒绝，没有 Run；不是 Python 故障。原数据目录只在这些条件全部成立后由既有驱动删除，保留 Run、公共行收据、两次重读与逐期记录。`rerun-results.json` 由既有 `targeted-round-cf166529/collect.py` 汇总。

| 位置 | 机械结果 | 内容结果 |
|---|---|---|
| JPMorgan C02 FY2022–FY2025 | 四个冻结/公共行/两次冷读一致 | 首次限定阅读已发现缺董事长姓名和两个常设委员会名称；继续撤回，不授信用 |
| Macy’s D02 FY2021（期末 2022-01-29） | 冻结/公共行/两次冷读一致 | 既有两向判读按块编号及文本 SHA 迁移到新选择，三条摘录 MATCH；只对新结果及此闭包释放 |
| Southwest D02 FY2023 | 冻结/公共行/两次冷读一致 | 同样迁移的两向判读，17 条摘录 MATCH；只对新结果及此闭包释放 |
| Lumen D02 FY2021 | `HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE:['UNRESOLVED_INCORPORATED_CAPTION_NOTE_18']` | 不把不确定的引用扩成整份 Note；无结果，撤回保持 |
| Pfizer D02 FY2021–FY2024 | 四个冻结/公共行/两次冷读一致 | v4 仍误收税务头寸段落；四个均 DIFFERS，撤回保持 |

## 阅读的准确范围

D02 的六份判读另存 `d02-older-years/carried-ed67e401/`，原已提交阅读字节不改。Macy’s/Southwest 和 Pfizer FY2022–FY2024 按原工具逐块迁移。Pfizer FY2021 有 24 个原 `COVERED_ELSEWHERE` 块被新路线取入，另有 Viatris 标题从漏达变为正文已达：执行者重读这 25 个变动及相邻原文，保存新决定；其余判定只在编号和文本 SHA 一致时复用。它仍误取 b2685；其它三年也因税务头寸段落不一致而拒绝。六个阅读通过 `tools/read_d02_excerpts.py` 对来源、候选、摘录顺序、完整值与实际 Result 身份的检查，结论写入 `content-acceptance/d02-read-round-ed67e401.json`。两份 MATCH 沿原关键词代理的已登记覆盖限制，未声称读完 Item 8 的其余所有块。

C02 的 `c02-limited-first-read.json` 保存两个方向的实际反例和原代理 URL、原件 SHA、块 SHA、候选及新 Run/Result：四年都取头衔而漏相邻 James Dimon 姓名；四年都漏明示的 Stock/Executive 委员会名称。FY2022 还取未来 CEO 交接分设政策，FY2024/FY2025 取董事持股政策。没有把它们写成新的完整两向判读：每份 2,123–2,409 个未选池块还没有逐块判完，不给完整误取/漏选数；这些已读反例足以拒绝整个集合。FY2021 留出、选择器和待对齐资格合同都未改。新增四条坐标缺陷，旧审计师/职责免责声明缺陷的规则修复已重算，但因其它缺陷不释放。

接受登记由 `tools/build_acceptance_register.py` 生成：899 → 901，只新增上述两份 D02；原 899 条逐条不变。已知缺陷 98 → 102。这里的公共行和本地验收不授生产、采纳、Ready 或合并权限。

## 重现

1. 在独立程序克隆检出 `68025386`，应用 `native-run-2026-09-18/0001-register-issue47-v1.patch`，mint 和 `--check`。
2. 通过上述 restore 恢复来源，不执行 acquire 或 resume。
3. 用每期记录中的 company/report_end/metric 生成 TSV（label、company、report_end、metrics 四列），运行 `SOURCE_ROOT=<恢复根>/source-inputs python3 docs/evidence/issue47_history/period-batch/frame_batch.py <计划> <新目录> --workers 3`。
4. D02 阅读用 `--reading-dir docs/evidence/issue47_history/d02-older-years/carried-ed67e401`、`--source-root`、本闭包及六个各自的平坦期目录 `--runs-root`，写新的 `--acceptance-output`。CLI 对四份 DIFFERS 以退出码 1 结束，这是阅读不一致，不是执行故障。可在既有 run_checks_replay_once / derived_once_per_state / xbrl_parsed_once 内完成同一只读调用；输入和判读不改变。

本轮不包含 B06 往年语法或 CI 提速；C02 完整池阅读仍未完成。模型固定包核验与 OS 权限阻断另见 `model-egress/runtime-uid1000/`。
