# 继承 CI 分层差异独立审阅

本次限定独审通过，未发现阻断问题。精确候选将原119个测试入口完整地分到95项短测试和24项来源材料测试，每个入口恰好出现一次；继续使用既有执行函数和30/240秒单项限制，没有引入v2新增的业务测试集合。结论为 **PASS_FOR_INHERITED_CI_PARTITION_ONLY_NOT_FULL_ACCEPTANCE**，不构成main全验收、实际远端CI通过、合并或生产批准。

## 身份、范围和计数

- 精确候选：`8f6640bcdfddbbaa5fca42619f1bbb69ec7a50b9`；增量基线：`d71546054fa1037f8c4c4880ec61a83b5e2c43de`。
- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics`。HEAD及四项被审文件的当前字节均与候选Git对象一致。
- 只审 `tools/run_foundation_ci.py`、`.github/workflows/vnext-fast.yml` 的95/24分层及结构测试接线、`tests/test_foundation_ci.py`、`TESTING.md:270`。两份既有runner只用于确认不变字节、分类和执行函数，不重审业务实现。
- 首次读取 `2026-10-04T15:39:20+00:00`；结束写入 `2026-10-04T15:43:53.796544+00:00`；至写入耗时 **273.797秒**。最终回读在随后数秒完成。
- 保守工具量含写入及随后最终回读共 **30次**：7次functions.exec、22次内部exec_command、1次内部clock。普通消息2条（开工说明、最终报告），问题0条；未触及80工具/90分钟上限。
- 只写本报告、同名日志及execution-state.json中本子任务的终态。没有源码/快照/其他工作树修改、commit/push、spawn、HTTP/SEC/model调用、119项或长测试重跑，也没有干预父执行者的持久后台验证。

## 保留的测试范围

独立从基线和候选的Git对象解析 `run_fast_tests.py` 中FAST_TESTS：两者相同，均为119个唯一入口。新adapter的 `partition()` 仅从这个旧集合取成员，再使用现有v2.SOURCE_PREFIXES分类；不消费v2.FAST_TESTS或v2.SOURCE_TESTS，因此不会带入v2的VAR替换、调查/持续经营/普通来源等新增入口。定位：`tools/run_foundation_ci.py:17`、`:18`、`:21`。

两次实际 `--list` 输出分别为95和24，精确匹配独立分类；并集等于原119、交集为空，且各自保留原相对顺序。重复入口会由 `:21`–`:24` 拒绝；新增测试 `tests/test_foundation_ci.py:16` 验证完整并集/唯一性，`:25` 验证重复输入不能悄悄通过。日志保留两份完整输出和静态核对结果。

相对基线的全部变更路径只包含上述CI/测试/文档及本证据目录，没有业务源码或Requirement绑定差异。两份既有runner整个文件在基线、候选和当前工作树三者逐字节一致，而不仅是函数签名相同：

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| tools/run_fast_tests.py | 17477 | b2870b7cf825b77cf08c20a69acb660e43bd3a74aabe2e1818a33721a373716e |
| tools/run_fast_tests_v2.py | 18385 | 7112e167d56431866c1effae7fd0e3158b5f48025cef1dcfaa9c47c39507db5a |

## 执行限制和失败传播

`tools/run_foundation_ci.py:43` 以原来的关键字参数 `test_name=name` 调用 inherited._run_case，材料分支以原来的位置参数调用v2._run_source_case。前者在 `tools/run_fast_tests.py:184` 使用原30秒常量；后者在 `tools/run_fast_tests_v2.py:202` 使用原240秒常量及既有override表。独立确认本次24个材料入口均未命中override，实际单项限制全部为240秒。

需要准确理解这个调整：原单一job把119项全部送入30秒短测试函数；新材料job按既有v2分类，把24项送入原240秒材料函数。这是采用已存在的分层执行限制，不是宣称这24项在旧job中原本就有240秒。两个旧runner及其CLI本身未修改。

原执行函数的每项return_code原样留在汇总中；adapter在 `:48`、`:52` 只在全部为0时返回成功。实际独立结构测试在两个suite分支分别mock原worker返回124，证明JSON保留124、状态为FAILED、adapter退出码为1，且不会串用另一个worker；定位 `tests/test_foundation_ci.py:31`–`:51`。这证明失败传播和调用方式，不声称本次真实等待了30/240秒超时。

| CI job | 入口数 | 并发 | job时限 | 每项时限 |
|---|---:|---:|---:|---:|
| fast | 95 | 4 | 5分钟 | 30秒 |
| inherited-source-material | 24 | 2 | 15分钟 | 240秒 |

workflow的fast时限仍在 `.github/workflows/vnext-fast.yml:13`，`:28` 选择新短测试分支；材料job的15分钟、2并发分别在 `:33`、`:47`。现有main-foundation job保留原main审计/历史模块/三个工具，在 `:68` 额外加入本次3项结构测试。没有if/continue-on-error或删除原业务入口来制造通过。

## 本审阅者实际独立执行

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_foundation_ci -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_foundation_ci.py --suite fast --list
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_foundation_ci.py --suite source-material --list
```

unittest退出0，**3项通过，unittest记录0.001秒，完整进程0.070277秒**；两次列表命令退出0，分别列95/24项，完整进程0.036162/0.035930秒。这些是本审阅者新执行的证据，日志名 `independent-foundation-ci-partition.log`。未执行119项业务测试或父正在执行的分层材料验证。

## 继承和未覆盖边界

先读README的Remote timeout段（`:92`起）及三份旧限定审阅：`independent-main-boundary-review.md`、`independent-main-audit-increment.md`、`independent-main-audit-alias-fix.md`。固定基础/历史/alias的未变结论按原范围继承；原d164的P2及其9a限定关闭证据保留，没有在此重审或把它扩成全PR批准。

README和任务输入关于d715远端运行37211664413、main审计/历史成功、原fast在5分钟取消且无assertion输出的说明，是此次分层的既有背景。本次禁止HTTP，未重新认证远端终态，也不从取消推断语义断言失败或通过。新的15分钟job是否在实际GitHub环境足够，仍须由对应精确head的真实CI终态回答，静态分层通过不能代替它。

本次未覆盖303运行模块、所有39业务指标、源码/绑定/原D04长材料复核、实际分层119项终态、Linux/GitHub执行性能、实时Issue权限、全main验收、发布或active切换。父执行者的实际分层运行由其自己的日志单独收尾，本报告没有替它判PASS。记忆只用于提醒取消与语义失败应分别表达，未使用任何旧记忆中的交付事实作为当前证据。
