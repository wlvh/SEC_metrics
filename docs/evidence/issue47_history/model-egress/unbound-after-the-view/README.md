# 重封停在第一道门：调用路径加载了 6 个没被绑定的模块

零调用。

## 发生了什么

2026-10-02 在 `51250475`（打上注册补丁与出口补丁、重新铸造快照）上重封离线验证。`verify.py` 先跑整套用例，套件不全过就不做任何注错（一个已经失败的套件"抓到"注错不说明任何事）。这次 153 例里 19 例失败，几乎都是同一个拒绝：

`ISSUE_47_MODEL_UNBOUND_CODE_LOADED:scripts/vnext/capacity_program_roles.py,...`

这是调用路径在打开连接前的检查（`historical_model_calls.loaded_code_holds`，独立复审 N3/N4 的修复）：发请求的进程里，每个从检出加载的模块都必须在授权绑定的文件表里。它按设计拒绝了。

## 是哪 6 个、谁加载的

错误信息只列前 8 个且被截断。`measure_unbound.py` 在封存树里跑其中 6 个实时用例，把这道检查包一层，记下它本来会列出的完整清单再交给原检查（检查本身不改）。完整清单是 6 个，都是 #28 的模块：

- `scripts/vnext/capacity_program_roles.py`
- `scripts/vnext/capacity_quantity_roles.py`
- `scripts/vnext/capacity_reference_contract.py`
- `scripts/vnext/r6_regulatory_semantics.py`
- `scripts/vnext/r6_semantic_verification.py`
- `scripts/vnext/regulatory_statement_facts.py`

`who_imports2.py` 打出每个模块第一次被加载时的调用栈（`first-load-stacks.txt`）：全部来自本方自己的 `historical_dei.release_aware`。`historical_semantic_results.py` 在模块层写了 `release_aware(reconstruct_requests)`；视图要判断一个冻结函数会不会走到 DEI 问题，就沿着函数体里的导入语句去读那些模块的代码（`_imported`），而读的方式是导入。#28 的 `reconstruct_requests` 按指标分派，在函数体里点名了 D03 与 B13 分支的模块，于是这些模块的模块级代码在每个导入 `historical_semantic_results` 的进程里都会执行——模型调用的执行器也是。D04、E01、D02 的调用从不走这些分支，也从不调用它们。

## 为什么 09-28 那次封存通过了

那次封存在 `8c1fcf18`。当时 `continuous_semantic_calls.py` 里已经有同样 14 处函数级导入，但 `historical_dei._imported` 还不存在——它是 09-29 读旧版 DEI 分类标准时（`9423a3a6`）加的。所以原因是本方的视图，不是 #28 新加了导入。

## 怎么改

把这 6 个模块写进 `tools/vnext_mint_historical_requirement.py` 的 `AUTHORITY_ADDITIONS`（理由写在旁边），重新铸造：本世代执行授权 484 → 490 个文件。这是最小也最如实的改法：它们确实在进程里加载，就应该被绑定。

**代价**：#28 改这 6 个文件中的任何一个，本世代的 closure 都会移动，已封存的收据与按它生成的批准都会失效。#28 正在做 D03 与 B13，这几个文件会改；而 `continuous_semantic_calls.py`（同一家族）本来就已绑定，所以耦合是增加了，不是新出现。

**没选的另一条路**：让视图的可达性分析只读代码、不执行模块（例如从源码编译出代码对象再找函数），这样这些模块就不会被加载、也不必绑定。那要改一个很多路线都在用、有完整注错的规则文件，需要单独的审阅，这次不做；如果以后 #28 对这几个文件的修改频繁让收据失效，再考虑。

改后两个补丁都还能应用（出口补丁对铸造工具的那段偏移 78 行），快照、字面量与模型调用三组用例 67 例通过。然后在新提交上重建封存树、重新封存。
