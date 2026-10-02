# C02：本方接收外部审计师独立性修复

本批固定本方基线 `0bc24734736bb1e6cb34fbcf7ab9fece6951764e`、只读fetch的#47提交 `54eb39d47718dea25812ea05ceb5a085078ff611`，实际只接收共用源码提交 `72858e3c023bed0c90f3217f381aec5725e15fbc` 的 `_NOT_DIRECTOR_INDEPENDENCE` 修复（对方修复45）。`shared-patch.json`证明本方既有 `historical_board_composition_v2.py` 的该表达式与对方修前相同，新 `c02_board_composition_28_v3.py` 仅替换成对方修后表达式及本方版本说明；没有搬入对方整个历史选择器后续、运行根、快照或结果信用。既有两个选择器路径、旧Spec/Run/Result字节保留。

独立来源判断先于程序结论。`source-boundary-read.json`从本方已保存JPMorgan FY2025旧Run的来源引用回到代理原件 `sha256:bea52712…`，分别核对完整原件与3367／3409／3436原始跨度SHA。3367明确是董事会/审计委员会支持续聘PwC，独立性修饰外部审计师，符合本方此前已确认的误选；3409明确披露四名非管理层委员以及各成员独立、具备财务素养、为审计委员会财务专家，必须保留。3436是另一项尚未裁定的问题：全文分配管理层、PwC、内部审计与委员会的职责，末句说委员不从事会计/审计执业；本方读法偏向职责说明，但是否构成资格事实仍待按已有合同与共用负责人技术对齐，不因疑点追加确诊或给全结果信用。

本方专用后继 Spec `C02_board_disclosures_v4.md` 保留已批准“构成事实”范围、64项/64000字符、原始块可逆分组及TEXT_V1记录/审阅链，仅用显式 `COMPOSITION_GROUPED_V3` 固定修复后的选择器。新可选参数 `c02_auditor_revision=False` 保留共享函数旧默认；旧分组V2按原Spec/代码运行，重放按保存的策略选择对应版本。正常CLI明确调用本方新包装器 `ordinary_c02_auditor_update_v3.py`，新尝试使用独立 `metrics/C02-composition-auditor-v3`；其它指标沿既有当前包装器，D02 v1/v2停用门继续生效。未冻结V13/V14的新模块、Spec、配置、实际CLI及父子依赖按最终字节核验，修前闭包与修后闭包见`binding-before.json`、`binding-after.json`，三份既有接线收据验证有效。它们不授新业务调用。

必要验证：短测7/7通过，包含审计师短语排除、同句委员独立性/财务专家保留、错误显式参数和v4 Spec/策略错配拒绝；保存原件材料2/2通过，JPMorgan当前完整来源的原始选中集合只减少3367，3409保留，3367也未被分组上下文偷偷带回；Pfizer当期选中内容不变。旧默认与显式`False`返回相同，旧候选不能换绑到新证据。

`run.py`通过真实正常CLI、禁网及禁用116个旧语义导出，在新的外部私有根从保存原件创建一次JPMorgan FY2025 C02 Run：`CANDIDATE_READY`，新Result `sha256:53f2aa84b39a047212214660d9e17fd97b5de0c03077973fdd10a40b8de7f14a`，33个可逆分组、59个原始选中块，3367不在新文本而3409保留，Evidence `PASS`。原账本、active、旧C02 Run与390索引哈希均不变；耗时145.601秒。此处的33组/59块不能与旧默认Result的39个逐块摘录直接比较成完成率，当前分组V2到V3的源码选择差异只是一块。程序Run与来源字节通过**不证明**全部59块及漏选方向已按合同验收；新私有Result不进入可信390，原两份错误Result仍按精确身份扣留。

`cold-installed.py`由另一进程只从新Run的安装目录加载选择器和投影器，重验V13执行身份，43.924秒读出同Result及逐字节相同的公开行；`repeat-current.py`再由正常CLI处理同一输入，47.412秒返回`NO_SOURCE_CONTENT_CHANGE`、原成功尝试/Result保留、没有第二Run，成功包的文件及账本/active哈希不变。最终树fast选择器147/147（57.602秒）通过，未全量重跑未变的旧来源长链。创建、冷读、重复测试均在未提交工作树、已记录规则字节和闭包上执行；不能说当时已测未来提交SHA，后续以绑定字节与提交等价核对及精确补丁独审补足身份说明。限定独审仍待精确SHA增量。全部实验真实provider/paid/SEC调用0/0/0，不授生产采纳、Ready、合并、部署或active切换。

精确补丁 `df9feafac6f1a5ff88145e29b1785117ab067bd1` 的限定独审已完成，结论 `PASS_LIMITED_NO_NEW_P1_P2`，见 `independent-review-df9feaf/conclusion.md`。代理亲自核关键原件、受绑定字节、旧默认及短测7项；没有重跑材料/原生/冷读长链或验收全部内容。`tested-commit-equivalence.json`补证22个被测文件与提交及适用安装字节相等，原测试仍明确为提交前执行。3436的疑点、整份内容/漏选方向及可信390解除仍未通过。
