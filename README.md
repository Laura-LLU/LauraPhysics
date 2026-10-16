# OPBP物理题库-AI组卷和批改工具

[![CI](https://github.com/Laura-LLU/OPBP-Bank/actions/workflows/ci.yml/badge.svg)](https://github.com/Laura-LLU/OPBP-Bank/actions/workflows/ci.yml)
[![Code: AGPL-3.0](https://img.shields.io/badge/code-AGPL--3.0-blue.svg)](LICENSE)

面向物理教师的本地工作台，包含 **900 道 OPBP 题目**，支持 AI 组卷、人工选题、AI 批改、教师复核和 PDF 导出。

**[下载 v0.7.47](https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.47)** · [安装与运行](START_HERE.md) · [功能图解](docs/FEATURE_TOUR.md) · [百炼配置](docs/BAILIAN_SETUP.md) · [测试试卷](examples/full-papers/)

## 功能

| 功能 | 操作与结果 |
|---|---|
| AI 组卷 | 输入主题、题型、数量、难度或时间要求，从题库选题并生成预览 |
| OPBP 组卷 | 按题号、关键词、Topic、知识点、难度和题型筛选，调整题序并保留指定题目 |
| 试卷导出 | 预览整卷后导出学生卷和教师答案卷 |
| AI 批改 | 批量上传答卷，匹配题号后发送视觉模型，最多3份并发，支持暂停和继续 |
| 教师复核 | 对照原卷检查作答证据，修改得分点，逐题确认 |
| 批量导出 | 导出带题旁批注和评分准则的原卷 PDF、班级总结及 ZIP |
| 我的作业 | 查看已导出的学生卷、答案卷和文件位置 |

### 输入要求，生成试卷

![AI组卷：输入要求、检查题单和学生卷预览](docs/images/01-ai-compose.png)

### 对照原卷，逐题复核

![教师复核：评分点、作答证据和对应原卷](docs/images/06-teacher-review.png)

### 确认完成，批量导出

![批量导出：答卷结果、批改PDF和班级总结](docs/images/07-batch-export.png)

[查看完整操作图解](docs/FEATURE_TOUR.md)。图中使用演示答卷和模拟模型响应，截图来源与许可见[素材说明](docs/images/ATTRIBUTION.md)。

## 安装与启动

支持 macOS、Windows、Linux。推荐 **Python 3.12**，首次安装需要联网下载依赖及约636 MB题图，建议预留4 GB空间。

下载发布包并解压，在 `OPBP-Bank` 目录执行：

**macOS / Linux**

```bash
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/run_web.py --open
```

**Windows PowerShell**

```powershell
py -3.12 scripts/setup_environment.py --venv .venv
.venv\Scripts\python.exe scripts/run_web.py --check
.venv\Scripts\python.exe scripts/run_web.py --open
```

打开 http://127.0.0.1:8895/ ，保持终端运行，按 `Control+C` 停止。环境检查成功时显示 `ok:true`、`questionCount:900`、`missingAssets:[]`。

[完整部署指南](docs/JUDGE_QUICKSTART.md) · [Mac部署](docs/MAC_DEPLOYMENT.md) · [故障排查](docs/安装与故障排查.md)

## 模型配置

默认使用阿里云百炼北京区接口，组卷模型为 `qwen3.8-flash`，批改模型为 `qwen3.7-plus`。在“模型设置”填写接口、模型名称和自己的 API Key，并完成文字与图片连接测试。

macOS 将 Key 保存到系统钥匙串；Windows / Linux 通过 `LAURAPHYSICS_OPEN_API_KEY` 环境变量传入。模型权限和用量在自己的百炼账户管理，配置步骤见[百炼教程](docs/BAILIAN_SETUP.md)。

人工选题、预览、导出和样例识别可直接运行。AI 批改先匹配题号，由教师确认发送，再逐题复核评分并导出。

## 测试

[三份完整自写答卷](examples/full-papers/)每份7页、6题、满分12分，可用于整卷上传、批改、复核与导出。检查文件和题号识别：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

自动化验收：

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

Windows 将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。自动测试使用隔离数据和模拟模型，输出结果 JSON、JUnit、日志、截图及 PDF/ZIP。

[测试说明](docs/TESTING.md) · [验收结果](docs/VALIDATION.md) · [人工操作检查表](docs/MANUAL_ACCEPTANCE.csv) · [输入与运行条件](docs/KNOWN_LIMITATIONS.md)

## 许可证

程序代码采用 **AGPL-3.0-only**。题目、图示和演示试卷按各自内容许可使用：900道题中709道为CC BY-NC-SA 4.0，191道为CC BY 4.0，逐题附作者、来源与许可。

[代码许可](LICENSE) · [内容许可](CONTENT_LICENSES.md) · [第三方依赖](THIRD_PARTY_NOTICES.md) · [贡献指南](CONTRIBUTING.md) · [安全与隐私](SECURITY.md)
