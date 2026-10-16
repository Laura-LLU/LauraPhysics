# 评委部署与测试指南

## 1. 准备

- 系统：Windows、macOS或Linux；Python推荐3.12，支持3.10–3.14。
- 网络与空间：首次安装下载约636 MB题图和依赖，至少4 GB空间，运行完整测试建议8 GB。
- [下载v0.7.47源码包](https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.47)，解压后进入`OPBP-Bank`目录。

也可用Git取得源码：

```bash
git clone --branch v0.7.47 --depth 1 https://github.com/Laura-LLU/OPBP-Bank.git
cd OPBP-Bank
```

## 2. 安装并启动

macOS / Linux：

```bash
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/run_web.py --open
```

Windows PowerShell：

```powershell
py -3.12 scripts/setup_environment.py --venv .venv
.venv\Scripts\python.exe scripts/run_web.py --check
.venv\Scripts\python.exe scripts/run_web.py --open
```

环境检查应显示`ok:true`、`questionCount:900`、`missingAssets:[]`。打开 http://127.0.0.1:8895/ ，页面标题为“OPBP物理题库-AI组卷和批改工具”。保持终端运行，按`Control+C`停止；端口占用时启动命令追加`--port 8896`。

## 3. 无模型操作

1. 切换到“OPBP组卷”，搜索P402，加入作业。
2. 查看原题和参考答案，调整选题篮顺序，预览整卷。
3. 导出学生卷与教师答案卷，打开两份PDF检查题图、题号和分值。
4. 在“我的作业”打开导出的试卷。

## 4. 配置百炼

按[百炼配置教程](BAILIAN_SETUP.md)填写自己的接口、文字模型、视觉模型和Key，完成文字/图片连接测试。默认组卷模型`qwen3.8-flash`，批改模型`qwen3.7-plus`，使用自己账户中可调用的模型ID。

macOS在页面保存Key；Windows / Linux将Key配置到启动服务的终端环境变量`LAURAPHYSICS_OPEN_API_KEY`，页面保存接口和模型名称。模型调用使用自己账户的额度。

## 5. 完整试卷测试

`examples/full-papers/`包含`Student-Paper 2.pdf`、`Student-Paper 3.pdf`、`Student-Paper 4.pdf`，均为维护者自写答卷，每份7页、6题、满分12分。

先检查文件和题号识别：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

Windows使用`.venv\Scripts\python.exe`。预期3份通过，每份依次匹配P402、P403-1、P478、P087、P352、P456。

再打开“AI批改”：上传三份PDF→识别题号→确认发送模型→查看评分与作答证据→逐题复核→确认本份→导出批改PDF、班级总结和ZIP。核对选择题作答差异、计算过程、毫秒换算及2或3位有效数字。

整卷得分在运行后逐题记录，原始模型结果和教师修正结果分别保存。[整卷说明与来源](../examples/full-papers/README.md)

## 6. 单页规则小样

`examples/marking-demo/`包含三个独立用例：AB多选预期1/1；1.86 m计算预期3/3；正确C与错误B的组合预期1/2。其[人工预期](../examples/marking-demo/EXPECTED_RESULTS.md)供逐点对照。

```bash
.venv/bin/python scripts/verify_demo_samples.py
```

## 7. 自动化验收

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

Windows使用`.venv\Scripts\python.exe`。测试安装工具与Chromium，使用隔离状态和模拟模型。通过标准为`test-result.json`中`ok:true`，失败、错误、跳过均为0。报告提供版本、提交、系统、Python版本和逐项结果。[测试范围](TESTING.md) · [持续验收](VALIDATION.md)

发布包内`release-manifest.json`提供逐文件SHA-256，Release附件`SHA256SUMS.txt`提供ZIP摘要，可据此核对下载内容。

## 8. 人工操作记录

使用[检查表](MANUAL_ACCEPTANCE.csv)记录操作、实际结果、模型版本与截图。部署、资源下载、证书、端口及模型错误按[故障排查](安装与故障排查.md)处理。
