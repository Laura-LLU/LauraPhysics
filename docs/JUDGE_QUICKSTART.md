# OPBP Bank：评委从安装到演示

核对日期：2026-10-16。运行版本：v0.7.45；代码提交以本版本标签为准；release-manifest.json提供逐文件SHA-256校验。

## 1. 官方要求与本项目交付标准

官网 https://www.oschina.net/os2026/ 的通用提交项是：完整可运行代码仓库链接、作品介绍（推荐PDF）、展示核心功能和流程的视频链接。场景落地评分包括“可部署、可运行、可测试”。未在通用指南发现统一的Docker、操作系统、GPU或工程目录规定；企业命题的指定工具应按任务书执行。具体报名确认邮件的附加要求由参赛者按收到的通知核对。

可从Release下载便携源码包并解压，先打开根目录START_HERE.md；也可按下面命令克隆。下载包已解压时，直接进入OPBP-Bank目录执行安装步骤，不必重复克隆。

下文是本项目为便于复现提供的部署步骤，不是组委会统一工程规范。本项目为本地浏览器界面+Python服务；macOS另有原生窗口。运行云端模型不需要本地GPU。没有对Docker安装、无网络安装或公网多人服务作承诺。

## 2. 先安装并验证无模型模式

推荐Python 3.12；支持范围3.10-3.14。准备Git、可联网浏览器及本地硬盘空间，至少4GB，完整测试建议留8GB。首次需要下载约636MB题图与依赖；模型不是离线运行。不要复制作者的运行环境或私人配置。

公开仓库：https://github.com/Laura-LLU/OPBP-Bank
固定版本：https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.45
详细Mac指南：https://github.com/Laura-LLU/OPBP-Bank/blob/v0.7.45/docs/MAC_DEPLOYMENT.md

Mac/Linux终端，在自己选定的新本地目录运行：

```bash
git clone --branch v0.7.45 --depth 1 https://github.com/Laura-LLU/OPBP-Bank.git
cd OPBP-Bank
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/run_web.py --open
```

Mac若遇证书错误，按仓库Mac指南配置可信CA；不要关闭HTTPS校验。

Windows PowerShell，在新本地目录运行：

```powershell
git clone --branch v0.7.45 --depth 1 https://github.com/Laura-LLU/OPBP-Bank.git
cd OPBP-Bank
py -3.12 scripts/setup_environment.py --venv .venv
.venv\Scripts\python.exe scripts/run_web.py --check
.venv\Scripts\python.exe scripts/run_web.py --open
```

成功标志：环境检查ok为true、题数900、missingAssets为空；浏览器打开 http://127.0.0.1:8895/ ，页面显示OPBP Bank。终端保持运行；结束按Control+C。端口已占用可追加--port 8896。所有服务仅监听本机。

无密钥先切到OPBP组卷，搜索P650-1或P160，加入选题篮，预览并导出学生卷和教师卷。检查题图完整、PDF可打开、两种工作区切换有选中状态。这一步不依赖AI账户。

## 3. 百炼配置教程：按量计费接口

独立教程与本机配置方式也见[BAILIAN_SETUP.md](BAILIAN_SETUP.md)。

官方资料（2026-10-16核对）：

- 获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
- 地域和接入域名：https://help.aliyun.com/zh/model-studio/regions
- OpenAI兼容接口：https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
- 模型列表：https://help.aliyun.com/zh/model-studio/models
- 图像理解：https://help.aliyun.com/zh/model-studio/vision

操作顺序：登录自己的百炼账号→选择华北2（北京）→按控制台提示开通模型服务并确认计费→创建属于相应业务空间的API Key→查看该空间可调用的文字与图像模型→在OPBP Bank“模型设置”填写并保存测试。

程序预填：接口 https://dashscope.aliyuncs.com/compatible-mode/v1 ，文字模型qwen3.8-flash，视觉批改qwen3.7-plus。预填不保证每个账户都有权限；模型名称必须与自己控制台一致，批改模型必须支持图像输入。

阿里云目前推荐业务空间专属域名：https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 。将{WorkspaceId}替换为自己控制台真实ID，或直接使用控制台提供的API Host并按官方兼容接口说明填写。DashScope域名仍用于兼容既有接入；不将它描述成唯一可用地址。API Key、地域和业务空间/接入地址要匹配。

本教程针对按量计费模型接口。Coding Plan、Token Plan专属密钥/接入地址有独立规则，不能凭密钥外观或有订阅就假定适用于此地址与图片调用。实际权限和费用以账户控制台为准。

Mac：在网页填写Key并保存，程序使用系统钥匙串。Windows/Linux：Key通过LAURAPHYSICS_OPEN_API_KEY环境变量传给启动服务的进程，网页Key输入留空，再保存接口与模型名称。该兼容环境变量不是阿里云官方SDK的DASHSCOPE_API_KEY；不能只设置后者。

Windows需要环境变量时，可先Control+C停止服务，再在同一PowerShell窗口设置（此处占位符不是可用密钥）：

```powershell
$env:LAURAPHYSICS_OPEN_API_KEY = '替换为自己的密钥'
.venv\Scripts\python.exe scripts/run_web.py --open
```

Linux同理，在本机终端设置LAURAPHYSICS_OPEN_API_KEY后重启服务。不要将真实密钥写入提交文件、截图、录屏或公开日志。只在本机设置；本包不提供作者密钥，也不替评委开通/付费。

先做文字和图片连接测试。连接成功只说明请求联通，不表示批改准确率已经验证。401优先检查Key/地域/空间；403查模型授权；404查模型ID与接口；429查额度/限流。按控制台实际错误处理，不把云账户问题当成本地安装失败。

## 4. 三份自写演示答卷怎么跑

源码examples/marking-demo目录有3份单页PDF，均取自用户自写答卷，未携带姓名页。原始文件未修改；新副本清除元数据、链接并固化可见笔迹。先在不配置Key的情况下运行`.venv/bin/python scripts/verify_demo_samples.py`（Windows用`.venv\Scripts\python.exe`），应报告3份样例题号匹配通过，然后再进行真实AI体验。题目来源和CC许可见该目录SOURCES.md。

顺序：AI批改→上传1份或3份演示PDF→检查识别题号→确认发送模型→查看原始评分→按人工预期结果逐点核对→如有误判由教师修改→确认本份→全部完成后导出批改PDF、班级总结和ZIP。

人工预期：Demo01为P650-1的AB多选1/1；Demo02为P160的1.86m计算3/3；Demo03为P402正确C得1分、P403-1误答B得0分，合计1/2。三份合计预期5/6。教师复核后的分数与模型原始结果要分开记录。不要把教师改分后的正确率当作AI正确率。

自然语言组卷另可输入“围绕电路出2道选择题和1道计算题，以中等难度为主”，检查本地题库是否能满足；数量不足应有明确提示。不要在演示前假定任意题池都存在指定组合。

这些样例验证清晰题号和有限笔迹的演示流程，不代表模糊照片、纯扫描件或真实全班作答准确率。维护者已明确授权这些选页随项目公开；各PDF内容许可、署名与修改说明见examples/marking-demo/SOURCES.md。

## 5. 自动化测试与人工演示是两套检查

自动化用例已随源码tests/提供，无需再从零写一套。Mac/Linux：

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

Windows：

```powershell
.venv\Scripts\python.exe scripts/run_tests.py --install --output test-results
```

首次会下载测试依赖和Chromium。成功标志：test-results/test-result.json中ok为true，passed与本版实际报告一致，failures/errors/skipped为0。确认版本0.7.45；Git克隆部署可将报告gitCommit与本版本标签核对。源码ZIP不含.git，gitCommit可能为空，此时以发布包SHA-256及release-manifest.json逐文件校验为准。结果数会随新版本用例变化。无需Key，不调用真实付费模型；有模拟模型协议测试，不替代上述真实AI演示。

公开验收见本次Release关联的Actions与仓库[验收记录](VALIDATION.md)。本版结果以对应提交的报告为准，不把其他版本结果当作本次证据。工程验收不代表真实手写识别准确率。

人工10项操作与通过标准见docs/MANUAL_ACCEPTANCE.csv。逐条记录通过/失败、耗时、版本、模型名和截图位置；失败保留，不事后删掉样例。没有本轮真实AI重跑结果时，留空实测列，不填“已通过”。

## 6. 工程交付统一检查表（本项目建议）

- 有固定版本/代码提交，代码完整，依赖可安装，题图下载和校验可复现。
- 有系统/Python/磁盘/联网前提、安装/启动/停止指令、端口和成功标志。
- 有无模型人工运行路径；真实AI需说明账号、Key、模型、地域、费用与外发数据。
- 有合法演示输入、人工预期结果、复现步骤；原始模型输出和教师修改分开。
- 自动化测试可一条命令运行，报告可看，失败和限制有记录。
- 代码许可、内容许可、依赖许可分别清楚；不携带作者运行环境、密钥、学生身份或私人历史。
- 常见错误有处理办法，有README/维护联系方式与已知限制。

官网未公布的Docker等要求不当作硬性门槛。先让评委按这条已验证的本地Python/网页路径跑通，再考虑容器化，避免提交日新增未验收的部署链。

## 7. 今天提交时放什么

代码仓库链接（或官方要求的源码附件）、最新作品介绍PDF、演示视频链接；新Release的推荐源码包已经包含本说明及演示样例，下载解压即可按文档运行。三份自写小样足够演示，无需把所有试卷和整个历史目录打包。若报名确认信有特定附件名称/入口/企业题目要求，以该指引为准。

源码包未替用户提交比赛、未替评委创建云账户，工程测试不执行真实模型批改。操作指南和人工预期已准备；真实效果仍以评委自己的运行与教师逐点核对为准。
