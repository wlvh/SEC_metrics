# H4：在现有历史分支接收 PR67 公司记录与读取

接收公共负责人PR67的abf6d3bc普通保存记录、0cd4c3ea共享XBRL解析和b7d6787c共用公司读取。公共模块原字节接收，历史方只适配既有CLI/分派和旧更新器参数，保留本方历史期间与修订选项。必要依赖将确定性catalog和CSV格式器从旧发布核心导入中提取出来，没有整体合入PR43、公共AGENTS/CI或另造公司pipeline。当前main核对为8588ccbb，这些增量及本方历史模式仍未入main。

`run --period latest-complete-fy --source-root <保存来源>`选择公共普通记录路径；历史`fiscal-years`先分派到已有范围实现，仍要求事先准备来源，不自动获取缺件。保留没有source-root的旧获取/固定任务路径。`results`通过同一company_result_view识别普通company-task.json和旧native状态；普通记录可显式使用历史缺陷登记，旧状态仍按原运行版本和身份读取。初接时普通results只能读JSON，本方将--output-root明确报不支持；公共后继e6b4a98f已解决这个缺口，本方接收同一公共读口的CSV/evidence/JSON输出，保留旧native日常CSV分派，没有竞争读口。公共32条已知缺陷始终检查，外加本方登记不能遮掉公共缺陷。

实际结果在validation.json及原CLI输出：

- Marriott FY2025 B01/B02真实来源通过同一CLI首跑3.401秒，得到26186000000 USD与0.04326693227091633466135458167 ratio；实际期间2025-01-01至2025-12-31，出处CSV保留官方链接。
- 同目录复跑0.320秒，两个指标均NO_SOURCE_CONTENT_CHANGE、calculation_performed=False，结果指针不变。独立进程results读取0.118秒，无来源解析或更新。
- 接b7d6787c后只重入B02，0.249秒未计算；再经公共results指定本方历史缺陷登记读取0.126秒，B01仍可读且requested_in_latest_execution=False，B02=True。没有为了读口变更重算首跑。
- 接e6b4a98f后同一普通任务results --output-root实际0.158秒输出CSV/出处/JSON，两个数值及请求角色保留，原任务31个文件全部字节相同。37个受影响小例0.123秒通过；未重入计算，来源及程序版本检查改动另由公共负责人按指标范围接入。
- 56个定向小例0.161秒通过，覆盖当前/历史分派、主体/期间、字节变化、解析缓存退出与恢复、同目录不重算、单项失败不污染其他成功、缺件与原记录、并发写锁以及已知错误扣留。3个共用真实来源准备/复跑/读取例3.516秒通过。另6个原确定性router例0.035秒通过，已包括在最终56例中，不重复计数。

首轮44例出现漏接current_records参数和macOS临时路径/键别名问题，日志保留；补上公开接口并对夹具根resolve，未放宽生产路径/期间/计算断言。后续49例及最终56例通过。实际CLI还发现原历史参数检查挡住当期source-root，已仅去掉对source-root的排斥，财年范围参数仍须历史模式。

新的普通当期记录不安装计算树、不复制来源树、不生成旧Run，不重复回放发布/资格事务。共享解析仅在一次公司操作中缓存最多16份原件SHA/size键，保存不可变解析对象，业务消费者仍各自核期间/主体；独立操作恢复默认解析。既有Macy两年B01数值、重入/缺年与16个旧Run/行/收据/指针验证直接复用前次记录，本项未重算、重取或修改旧任务。

仍待H4：把指定历史期间接到新普通保存记录/共享来源与结果视图，以及历史发现/缺件报告/具体许可补齐接入同一run。目前只有保存来源后的旧范围计算成立，不能写成完整五年自动获取到CSV。当前普通保存分支的未接AI指标明确PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED，E01旧item-code计数也不作新的内容确认并购结果。新普通记录不代表业务正式接受。

本项新增DeepSeek/paid/SEC为0，没有改变原35次模型批次、EX-99原许可/账本、冻结失败、旧Run、发布或active。未全量重跑，不取消业务进程。公共CI仍由#28按实际依赖集成，以上定向通过不代表所有旧必过集合或main全部通过。

保留的旧检查结果：mint --check仍在父代载入时报Normal candidate rule bytes differ: normal_annual_input.py，未进入本项业务代码；这是此前已登记的旧祖先绑定问题，未重签快照。能力合同检查提交前指出唯一未提交的历史说明与HEAD不同，代码提交15cca8d5后通过；它只证明结构对齐，不证明所有业务语义。两项检查器副产物已按检查前字节恢复，完整输出在本目录。这些旧流程检查不作为新可信内部运行的额外批准前置。

恢复来源目录的历史财年准备确实存在程序依赖缺口：原件在，但旧ordinary admission要求trusted journal。旧选择器会把所有ValueError遮成SOURCE_UNAVAILABLE；现行历史入口保留逐候选底层错误及分类，旧journal依赖归IMPLEMENTATION_GAP，错主体/期间完整性及真实缺源分别保留。5个短例0.002秒通过；实际相同恢复目录1.625秒仍拒绝选择并给出两个候选的具体journal原因，未自动取源。已有Salesforce发行人财年定义/邻年缺源反例3.558秒通过，缺源仍拒绝且不由期末日期推算标签。旧Run/失败不改，本项不修旧journal或建立新trust；来源读取简化由公共负责人接入。

后继接收公共PR68代码399e35e1的request_bindings/company_registry/saved_source_checks及原接口兼容导出，不带公共AGENTS/CI。当前普通来源校验直接核已有CSVmanifest、指定attempt、body/header、官方URL/最新GET失败，不再要求旧journal或祖先前缀。用户指定accession与URL accession分别核对，原链式比较漏拒的公共修正同接；异常导出对象身份保留，不据此认定所有旧结果有错。

37个保存来源、错件/最新失败及历史期间/公司消费者例0.764秒通过。上述完全同一个恢复source-inputs目录再次经实际FY2024选择/准备、历史B11 case与公共纯保存通过，总7.153秒（case2.697/save0.692），128.23 USD和2024区间保持。原ledger全部字节不变，没有制造journal或重新恢复整树；原失败保留为前驱。新校验标签SAVED_SOURCE_BYTES_AND_REQUESTS_CHECKED、real_sec_credit=False，只代表保存原件/请求关系已核，不重置或借用1771累计与来源调用信用。见restored-source-historical-case-after-r4.json。

此处旧journal准备缺口已由公共接口解除；实际来源自动发现/补齐、已选历史期间进入公共普通状态及范围调度仍待。本方提供现有fiscal-years选择/组装及历史case，公共updater/reader索引由#28维护，避免另一套历史状态或公司pipeline。旧固定版本/Run和旧checkpoint显式接口保留，不反签历史。

接收PR67公共325d65b7的明确fiscal_year/case_factory及多期间reader接口；公共默认当期布局不变，指定期间由公共updater保存到periods/FY<year>。34个受影响更新/读取例3.002秒通过。历史方在现有lodging模块增加prepare_historical_lodging_year_case，只接既有财年选择和同一计算case，不建立状态/存储。实际公司范围入口尚待公共run_saved_company增加范围参数后接入，以上不能作CLI完整接线结果。未重跑旧两年B01。

公共72394740的run_saved_company范围参数已接到现有company_local._run_history：新B10/B11任务走同一公共updater/store/reader，历史方只提供既有year选择→case，已有native任务仍原分派。真实同一CLI FY2024/FY2025四坐标首跑22.564秒，CSV分别69.8 percent/128.23 USD与69.3 percent/128.8 USD；实际日期2024和2025各Jan1–Dec31。复跑3.074秒，显式禁止历史case计算仍全NO_SOURCE_CONTENT_CHANGE，所有结果文件/指针bytes保持；另进程读0.964秒。相同任务当期模式7.328秒仍得FY2025原值，没有重做旧Macy两年B01。6份小记录共184197bytes，两年度各一共享grid合计7123654bytes，无程序/来源树复制、Run或调用。

FY2025–2026缺年请求1.826秒，已有FY2025不计算，2026无源按原错误报失败和空值/空日期，所有旧记录及指针保持。随后读0.961秒保留2024未请求、2025已请求和两个失败条目，但实际发现公共reader未将失败的请求FY2026带入JSON/CSV，不能称读口完全交付；原错误JSON保留，已交公共负责人修复，后续仅重读同任务。44定向更新/范围/读取例3.000秒通过，新增分派+旧任务隔离后的10范围例0.145秒过（与前44有重叠，不相加成54）。

版本配置另有明确开发缺口：公共factory目前只登记其所在文件，历史期间/DEI/修订/财年政策的实际依赖需同配置计入，已直接对齐公共接口，不扩成递归证明或整树。此接线只完成保存来源上的B10/B11范围更新/CSV及受影响当期行为，尚未main，发现/补齐仍待，不替代五年业务。原1771累计的同本claims SHA不变，禁止socket的实际子进程无新业务调用；旧EX99阻断许可保留。
