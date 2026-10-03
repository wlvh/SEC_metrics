# 注错脚本的字节码隔离与既有注错结论的重跑（2026-09-29）

**发生了什么**：清除 #47 业务字面量那一轮（`../semantic-literals/`）的注错跑完之后，一条普通测试失败——恢复后的 C02 读取器跑的却是注错里的正则。注错脚本把源文件改了又按字节写回，而 Python 判断缓存的编译结果是否可用，只看源文件大小与整秒修改时间；那个注错改动恰好与原文同样大小、又在同一秒内写回，于是 `__pycache__` 里注错版本的字节码被当成恢复后源码的编译结果继续运行。实测：缓存头记录的时间与大小与恢复后的源文件完全相同，字节码里带着注错的字面量。**按字节恢复文件，不等于恢复了实际运行的东西。**

**修法**：仓库里 10 个就地改文件的注错脚本，每次注错的子进程都用一个新建的 `PYTHONPYCACHEPREFIX` 目录，不读也不写检出里的 `__pycache__`；检出里现有的缓存已删除。`verify.py` 与 `preflight.py` 早就给每个进程独立的字节码目录，不受影响。

**为什么要重跑旧结论**：同一次运行里，第 k 个注错留下的字节码可能让第 k+1 个注错的测试同时带着两个故障跑，于是"被抓到"可能是前一个注错的功劳。所以把 9 个旧脚本在提交 `6923b19e` 的一份新克隆里逐个重跑，按注错比对结果与抓到它的用例（`compare_reruns.py`；它拒绝把"脚本没跑到写出那一步"读成"结论相同"——第一轮 batch 脚本在预检处停下，就是被它按名标出来的）。

| 脚本 | 注错 | 重跑 | 结论相同 | 抓到它的用例相同 |
|---|---|---|---|---|
| `model-egress/model_start_injections.py` | 9 | 9 | 9 | 9 |
| `acquisition-wiring/vm_start_injections.py` | 21 | 21 | 21 | 21 |
| `acquisition-wiring/batch_injections.py`（3 个改指当前代码） | 14 | 14 | 14 | 14 |
| `e01-item-text/visibility_injections.py` | 9 | 9 | 9 | 9 |
| `e01-item-text/fault_injections.py` | 9 | 5 | 5 | 3 |
| `block-resident-filings/fault_injections.py` | 8 | 8 | 8 | 8 |
| `part-iii-statement-review/fault_injections.py` | 8 | 8 | 8 | 8 |
| `b03-depreciation-scope/fault_injections.py` | 8 | 8 | 8 | 8 |
| `b03-depreciation-scope/route_fault_injections.py` | 7 | 7 | 7 | 7 |
| **合计** | **93** | **89** | **89** | **87** |

- **batch 的 3 个注错改指当前代码**：它们编辑的文本已被后来的修复改写（批准比较与解析从 3e8598bf 起用 `posted_text`；重开账本在复审 M1 残余之后要同时丢掉根目录旁的两个文件）。含义不变，改的是被编辑的那一行。`batch-injections.json` 现在是这次重跑的原始结果；SEC 接线收据绑定的 `fault-injections.json` 保留原始行，这次重跑复现了其中每一行的结论与抓到它的用例。
- **E01 条目正文的 4 个注错无法重跑**：它们的目标是 629f1ed8 用内容确认替换掉的关键词分支，被编辑的文本已不存在；原记录保留原义，描述的是当时的代码。其余 5 个重跑（`../e01-item-text/fault-injections-rerun-2026-09-29.json`）全部被抓到；其中 2 个抓到它的用例集合不同，原因是那个测试文件在 629f1ed8、9c8c28a9、5f75a937 里改过：不再出现的两个用例在 629f1ed8 里改了名，新出现的用例在原运行时都还不存在。

**结论**：可重跑的 89 个注错全部得到原来的结论，没有发现被前一个注错的残留字节码"代为抓到"的情况。这不证明原运行时从未发生过污染，只说明在隔离之后同样的注错仍被同样的机制抓到。零 SEC、零模型调用。

**复现**：`git clone --shared <仓库> <克隆>`，检出要核对的提交，然后 `bash rerun_first_pass.sh <克隆>`、`bash rerun_second_pass.sh <克隆>`、`python3 compare_reruns.py <克隆>`。
