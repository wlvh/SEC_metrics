# PR67默认新任务：与main成对检查及兼容回修

服务器起点：main8588ccbbb1c91d81e0fb1a89dff3575214282549；PR61/86e63816已包含在PR67/29c9c9e2（main base）。PR67另外包含60/63/64/68与所选59；58/62独立，不全批顺序合并。PR83是独立后继，不用于本回修。原测试与已成功的未变材料复用。

三入口：

1. 新轻量保存来源：`python3 tools/vnext_company.py run --company marriott_international --source-root <合法保存完整来源> --work-dir <独立新state> --output-dir <独立output> --metric B01 --metric B02`；随后同命令复跑，`python3 tools/vnext_company.py results --company marriott_international --state-root <同work-dir>`。普通state-root就是work-dir，不是company-state。已有主要README的实源/禁工厂/冷读证据复用；28项相关例通过。
2. 保留旧任务：原native树及其源/trust/处理依赖不改；当前CLI读取需要`results --state-root <旧company-state> --company <原公司> --trust-root <原trust/company> --runtime-root <创建树>`。已有JPM D01 0.637s实际读取/Southwest journal 0.322s的限定证据复用，不说成新任务。完整原Marriott任务可按#54 live2已归档恢复材料原方式取回，固定程序随包保留；业务内容未接受。日常读不是默认cold-export。
3. 不带source-root新任务：下面脚本实际从两个独立空目录执行，所有prepare_program/安装/发现/计算/实际子进程都真实；只给native session必需的RECORDED_TEST_ONLY回复模式及URL对应HTTP原字节，所有子进程socket/DNS禁网，无密钥/原真实账本。原main166.358s return0，29c9原候选1.837s return2在HTTP前失败：Normal candidate rule bytes differ: normal_source_authority.py。不是CLI参数错误/文档风格/账本用完。源码回修保原CLI与main支持范围：新native默认任务自动从固定main8588的程序/规则装配保留local runtime，当前saved-source生产者不变，原已有program-root优先保留。不是恢复新轻量路线的信任平台；这份保留版本承担过渡旧原生入口，后续轻量在线替换另审。程序不安装SEC原件，不修改旧运行。166.358与165.199仅同场景观察，不宣传提速。

修后同HTTP/公司/指标/环境的新空目录完整return0；main与修后B01=26186000000 USD、B02=0.04326693227091633466135458167 ratio、FY2025/2025-01-01..2025-12-31/statusOK一致。原失败和成对阶段/行摘要保留。实际状态有29个隔离录制槽、0真实SEC/provider/paid。不是39业务通过、新真实SEC验收、合并或生产信用。

## 可运行成对命令

源码需完整Git对象（保留main8588和历史规则对象），Python3.12的标准库足够本次B01/B02；更广保存AI输入另按原requirements-continuous-context.txt固定tokenizers依赖，不提供业务密钥。原件从http-fixture-manifest所列原Git/已有#54归档取得；不编造缺URL。不要把处理答案放入HTTP源目录。检验输出使用全新目录、来源只读。

```sh
export PYTHONPATH="<本目录绝对路径>"
export SEC_REVIEW_HTTP_ROOT="<含原evidence/requests_log.csv及对应HTTP原件的只读目录>"
python3.12 -B <main8588>/tools/vnext_company.py run --company marriott_international \
  --period latest-complete-fy --work-dir <独立空main-work> --output-dir <独立main-output> \
  --metric B01 --metric B02 --max-sec-requests 120 --sec-allowance 120
python3.12 -B <修后PR67>/tools/vnext_company.py run --company marriott_international \
  --period latest-complete-fy --work-dir <独立空candidate-work> --output-dir <独立candidate-output> \
  --metric B01 --metric B02 --max-sec-requests 120 --sec-allowance 120
```

这里120只隔离录制上限，不是真实调用批准。sitecustomize在实际安装子进程导入自己的acquisition模块时注入HTTP回复，不能把整个_invoke返回或installer/选择器mock成功；缺URL明确REVIEW_SAVED_HTTP_REPLY_MISSING。两个正式run仍能独立执行acquire/计算，观察各stages原stdout/stderr。普通真实在线另核已有适用用途/累计账本，不用这个测试初始化真实额度。

现回修工作树证据不能写成已提交SHA；提交后核对源差异与被测树。保存来源/旧读取不受影响的责任复用，必要默认入口回修限定复核及新headCI尚待。原在线全族业务缺口、39指标、模型和生产责任不因兼容结案解除。
