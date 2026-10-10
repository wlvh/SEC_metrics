# E01 保存来源到历史公司未决结果

本批main6e51f416短分支承接已有E01原件/八候选/EX99与6f4后处理，不新模型实验或调用器。现有selected event source、Item正文读取、V1请求和V2 incorporated准备/机械检查/完整汇总均复用；只提取纯合同函数，不搬旧注册/授权/调用/Run封存系统。历史actor只选实际issuer/FY，公共E01显式factory门和呈现由#28维护。

## 实际Paramount FY2024输入

source root用原EX99已执行账本的source-inputs，保存材料完整，不再GET。原FY24 amended filing仅按已经交付_event_amendment_checks判断来源影响，不能看到amendment就拒全部事件。重建八个完整候选，原V1 request3831616f…同；V2 incorporated完整对象逐字段等既有2aa878ef…，八items、50proofs、全文/HTML/已保存EX99都同，request-parity.json证明没有换合同/裁来源。实际纯准备22.644s；没有读取旧回答或创建Native Run。

该V2没有与请求对应的真实目标模型回答。case的Result/null、E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST和input-assessments保八item IDs、request id/contract、具体attachment状态、partial_count_exported=false、old_answer_reused=false；原完整请求准备由同普通input-assessments保存，供后继共享model链消费。不是只造另一个孤立准备helper。尚待公共显式E01 gate后同公司CLI/save/results/CSV实际终态，不能先宣称接线完成。

首次准备曾把所有amendment一概扣留，改为复用现有源影响检查；首次V2只带event45+attachment1proof，model文本相同但requestID不同，补入本次真实annual/preparation原四proof后完全等原50proof/V2对象。这些开发失败/摘要保本地，不重取源、不改原请求/回答/额度。

52源合同/完整汇总/历史consumer控制.166s零skip，combined.log；旧纯合同函数AST相同，既有未决一项仍全countNone，跨item假引用/错字段/缺答拒。新case构造明确控制：无对应响应和附件缺件均null、旧答不借；successor不能借其他事件宽窗；源异常不叫无候选；只有完整源/正文walk确无候选可沿原Calculator给0。构造0不冒充真实财报结论。

其他年份、模型内容业务、来源缺件与共享模型执行接缝仍待。新SEC/provider/paid0，无新许可/Run/接受/Ready/merge/active。只维护本主要记录，已有96/105/108/110候选接收优先，C04未提交准备停止扩展。

## 原普通writer的真实未决记录

实际接main0b（eaf16e55）及公共102/c3固定reporter源码，不覆盖controller/runner；61源合同/主体/历史控制.162s零skip。原prepared case经同save_calculated_case/read_saved_result纯保存/冷读，null/WITHHELD/CIK813828、FY2024全年，8item IDs及完整原2aa V2请求已进入普通input-assessments。ordinary-reporter-withheld.json给可读CSV和保存位置。此前未接102时直接输出今日CIK2041610，只新增呈现版本、不改原ResultID/源；这就是本批必要公共依赖。公司CLI有限E01门尚待公共方，直接writer成功不代替用户入口已交付，也不在本阶段新建PR称成功。

后继把已完成的annual amendment来源影响检查保存在e01_content评估内，避免用户只看到结果而看不到为何接受该修订来源。31相关纯合同/consumer控制.017s零skip；不改变既有V2 request对象或计数结论。待同CLI实际终态一次验证，不为这字段重跑历史全部原件。

## 已提交来源的取得顺序

若已有本批真实后继source-inputs根，直接只读复用。首次恢复时，在保留历史代码分支运行原 `tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <不存在的新目录>`，记录它返回的data_root。这个基础版本的log SHA是61252ac5，尚无EX99；不能把附件增量单独当成完整公司根。

在这个**刚恢复、尚未用于任务结果的新来源目录**中导入已提交最小增量，旧运行根不要原地覆盖：只取增量中的source-inputs/config/company_registry.csv、源CSV/manifest以及EX99原件和headers。逐成员SHA按ex99-increment-index.json验证；registry须与基础相同，旧CSV完整字节须为新CSV前缀，新增行只有指定EX99，保留原行次序。不要解包calls、claims到任何执行账本。该操作只恢复已经消费的材料，不创建新的可执行额度或许可。

本轮已核该归档所有成员及五个源成员的实际SHA，increment-source-check.json。源CSV SHA9cb8adec对应原一次GET后的2532行；EX99原件0baae3b3/18964字节。导入后用现有ordinary source verifier或该E01 case只读重建八项/V2 request，预期request2aa878ef；无需再次GET、start/resume或模型请求。完整首次基础restore是已有材料取得流程，尚未统一到公司在线发现/补齐入口，不将这份恢复说明当作该责任已取消或已完成。


以下命令在基础restore之后执行。`HISTORY_CHECKOUT`指可取得的原历史分支checkout，`SOURCE_ROOT`指**新恢复且尚未用于任务的data_root**；现有完整根无需运行。没有执行账本导入，也不会GET。示例中的导入操作按先原件、后完整CSV/manifest保存，要求目录此时没有读写任务。

```bash
export HISTORY_CHECKOUT=/path/to/retained-history-checkout
export SOURCE_ROOT=/path/to/new-restore/source-inputs
python3 - "$SOURCE_ROOT" \
  "$HISTORY_CHECKOUT/docs/evidence/issue47_history/acquisition-wiring/ordinary-public-receiving-20261009/ex99-increment.tar.gz" \
  "$HISTORY_CHECKOUT/docs/evidence/issue47_history/acquisition-wiring/ordinary-public-receiving-20261009/ex99-increment-index.json" <<'PY_SOURCE_ONLY'
import hashlib,json,os,sys,tarfile,tempfile
from pathlib import Path
root=Path(sys.argv[1]); archive=Path(sys.argv[2]); index=json.loads(Path(sys.argv[3]).read_text())
def sha(value):return hashlib.sha256(value).hexdigest()
with tarfile.open(archive,'r:gz') as tar:
    contents={name:tar.extractfile(name).read() for name in index['member_sha256'] if name.startswith('source-inputs/')}
for name,raw in contents.items():
    if sha(raw)!=index['member_sha256'][name]:raise ValueError('SOURCE_INCREMENT_MEMBER_CHANGED: '+name)
log=root/'evidence/requests_log.csv'; old=log.read_bytes(); new=contents['source-inputs/evidence/requests_log.csv']
if sha(old)==index['source_log_sha256']:
    for name,raw in contents.items():
        if (root/name.removeprefix('source-inputs/')).read_bytes()!=raw:raise ValueError('EXISTING_INCREMENT_SOURCE_CHANGED')
    print(json.dumps({'status':'ALREADY_PRESENT','new_calls':[0,0,0]}));sys.exit(0)
if sha(old)!=index['previous_source_log_sha256'] or not new.startswith(old):raise ValueError('BASE_SOURCE_LOG_NOT_EXPECTED')
if (root/'config/company_registry.csv').read_bytes()!=contents['source-inputs/config/company_registry.csv']:raise ValueError('REGISTRY_CHANGED')
# Only use this on a newly restored, unused source directory. All checks precede writes.
for name,raw in contents.items():
    if '/request_attempts/' in name:
        path=root/name.removeprefix('source-inputs/')
        if path.exists() and path.read_bytes()!=raw:raise ValueError('EXISTING_ATTACHMENT_CHANGED')
# Put the immutable body/headers first; publish the complete log and its matching manifest last.
names=sorted(contents,key=lambda n:('requests_log' in n,n.endswith('_manifest.json')))
for name in names:
    path=root/name.removeprefix('source-inputs/');raw=contents[name]
    if path.exists() and path.read_bytes()==raw:continue
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.restore-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
print(json.dumps({'status':'RESTORED_SAVED_SOURCE_ONLY','source_log_sha256':sha(log.read_bytes()),'new_calls':[0,0,0],'execution_ledger_imported':False}))
PY_SOURCE_ONLY
```

命令已在小型构造恢复目录实际执行：仅放同一registry及原完整源CSV，首次只加入指定EX99源成员，第二次`ALREADY_PRESENT`；现有`saved_source`及`verify_ordinary_source_proofs`以.113s读取18964字节并核原attempt。increment-source-import-control.json明确这是小型恢复控制，不能冒充完整公司来源重建或公司CLI验证。没有复制755份HTML、没有修改实际来源根、没有导入calls/claims、没有新增调用。

后继消费者依赖修补：E01实际调用现有event walk和_event_amendment_checks，却只列其入口文件而漏其修订政策/检查与来源walk依赖。现直接并入已交付事件族的有限PROCESSING_FILES并去重，保相关规则变化触发处理；不写递归依赖平台、不改公共controller、不改变请求/Spec/旧结果。15本消费者及原事件例.027s零skip；dependency-controls.log。真实首次CLI尚未运行，依赖变动复用验证随公共门接收一起完成，不为声明修补重建八项原件。

依赖修补的状态行为另用原SelectedHistoryResultStateTest的小型状态控制验证：传入本E01真实PROCESSING_FILES，初次构造扣留后同输入PREVIOUS_INPUT_WITHHELD；仅在内存改变实际修订政策hash后处理一次，再同输入又复用。总factory2、.020s，无文件规则变更/真实来源复制。declared-dependency-state.json明确构造控制，不冒充Marriott财报结论或公司CLI接收；只是证明该声明经同公共run_once产生所需失效行为。

实际接收main f6（金融公共与三历史族已合入）为192de8d4。公司分派保main六金融映射并加本E01；投影只合原公共c3 reporter与main的reported-average两个相邻函数，函数AST均逐字实现同源，不写第二renderer。42主体负例/季度期间/历史分派/E01控制9.186s零skip；main-receiving-conflict-controls.log及main-receiving-public-functions.json。未重新计算JPM/Paramount，真实E01门仍待公共下一固定补丁。

## 真实公司入口终态

公共PR113固定4791ef0b接为1dd408e0，main f6+c3 reporter+本producer在同树。33公共门/历史consumer/dispatch .083s零skip，随后ParamFY2024同公司run20.959s/CANDIDATE_WITHHELD/exit2，禁factory复3.444s/PREVIOUS_INPUT_WITHHELD/calculationfalse，独立results.638s/exit0；FY24全年/CIK813828、8结果pointer文件保持，完整V2 request2aa及八候选留input-assessments。没有matching V2目标答，原V1不借/null不补部分计数。company-cli-first.json/log。

驱动读取CSV时默认131072字段容量失败，实际三个CLI均正常；仅读现成输出核对发现本方完整修订scope对象嵌进daily selection造成2.55MB单格。现只在本producer展示scopeID/classification/明确窗口/来源引用，完整评估/原请求仍在input-assessments及绑定。9短例.008s零skip；已算case纯writer2.003s验证CSV字段7910字符/默认csv可读，完整assessment/ResultID同，不重读源。

这一真正展示代码变化只正常迁移原E01该一坐标22.861s，原旧版本保留，禁factory复3.371s/calculationfalse、独立results.603s；15旧新结果/pointer文件保持，全年/CIK/null/2aa完整请求及annual amendment原评估均在。company-cli-display-final.json/log。没有其他公司/年份重算，原大CSV保旧版本。正式用户入口现在能写出可读未决和具体来源依赖，但内容确认模型业务仍未交付；新SEC/provider/paid0，无NativeRun/接受/active。

公共方按885c固定tree提供最小CI patch，现PR114接收：只追加本consumer/完整附件合同/原MA合同三测试path及原Selected event步骤三模块，原source/projection/explicit门不丢、金融历史步骤不变。按同一实际步骤命令53方法.130s零skip，workflow-six-modules.json/log逐模块确认。此为小型纯合同/程序控制，真实ParamCLI复用上节，不以这些控制增加模型接受；新head远端执行单独核。

7f02实际公司workflow37979164089/job113984974948已SUCCESS，日志逐模块source8/projection5/explicit7/consumer9/incorporated11/MA13，共53方法.285s零skip；不是模块名只登记未加载。原保存源194/177.604s、三金融/历史分派状态60/.486s、event retention10/.107s、原账本兼容22/6.050s均执行通过。ci-7f02-company.log/summary记录本提交实际触发、作业及方法。两个基础作业当时仍在运行，整体终态另读；纯记录后继不改变该生产实现，也不重复财报或provider。

## 实际main c99后的同树接收

读取最新正文/交接/PR反馈后，原114/21b与main发生冲突；本方只合历史E01+RPO/六金融/旧族dispatcher和现有workflow步骤/path并集。公共#28原PR113返固定aa61081b，六公共文件逐字接收，ordinary_projection及reporter测试严格同actualmainc99，原旧102展示被已入main后继替代。D04/131/收入链/paired的main实现保，未引入PR138或第二controller/store。五历史处理模块同原21b，没有新方法/更换请求合同。

88公共门/历史consumer/附件MA/dispatch/state/reporter/季度/D04控制10.280s零skip；原七main工作流命令及历史三模块/path保留，不另runner。仅原ParamFY24一个相关配置正常迁移25.269s，仍WITHHELD/null/813828/实际全年/原333187ResultID；完整2aa878ef八项请求与原对象逐字段相同。禁止历史factory复3.649s/计算0，独立results .671s，原业务记录与迁移后保护文件不变（数量见main-c99-company.json）。来源只读/旧大CSV与旧失败保，matchingV2响应仍无、无部分count/旧答借用。实际执行准确记原21b+未提交合并/固定公共文件树，不倒签后继commit。

接收组合只解除代码冲突，非目标模型内容通过或完整年度计数交付；无新SEC/provider/paid/nativeRun/接受/Ready/merge/采纳/active。新head CI另核，旧21b全绿不盖本组合。主体/继任窗口和模型接缝仍未完成；源下载及EX99原一次调用不重复。

实际d82addec产品同树只读JPM原A13/average/scope三任务，.520/.531/.621秒，原30正确值和3代表混选值、单位、季度/全年/期末日期、原ResultID/申报保持；89/163/312全部state文件字节保持，run/network禁止。初驱动误猜不存在output_root/路径父级，未执行业务；改直接用已有实际输出基线，不手填财务值。公共同文件已接收后验证读口影响，不重算30个位置，纯证据分支不为日志再推产品CI。
