# macOS 部署

## 环境

推荐Python 3.12，支持3.10–3.14；至少4 GB本地空间，首次安装需要联网。Python可从[官网下载](https://www.python.org/downloads/macos/)。

[下载源码包](https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.47)并解压，或用Git克隆。在源码目录执行以下步骤。

## 安装与启动

```bash
export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/cert.pem}"
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/run_web.py --open
```

安装器下载题图，校验ZIP与逐文件SHA-256，创建`.venv`并安装依赖。检查应显示`ok:true`、`questionCount:900`和`missingAssets:[]`。

浏览器访问 http://127.0.0.1:8895/ ，按`Control+C`停止服务；其他端口可使用`--port 8896 --open`。

## 组卷与批改

“OPBP组卷”可直接筛选、预览、导出；“AI组卷”和“AI批改”按[百炼教程](BAILIAN_SETUP.md)配置账户。macOS在“模型设置”填写Key并保存到系统钥匙串。

完整答卷与操作见[评委指南](JUDGE_QUICKSTART.md)。

## 自动化测试

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
.venv/bin/python scripts/run_tests.py --install --output test-results
```

前者检查3份整卷，后者输出JSON、JUnit、日志、截图和导出文件。成功时`test-result.json`中`ok:true`且失败、错误、跳过均为0。

## 独立数据目录

可在启动前指定本项目的数据和导出位置：

```bash
export LAURAPHYSICS_OPEN_DATA="$PWD/.local/state"
export LAURAPHYSICS_OPEN_OUTPUT="$PWD/.local/exports"
export LAURAPHYSICS_DISABLE_LEGACY_CONFIG=1
.venv/bin/python scripts/run_web.py --open
```

## 题图下载

安装器自动取得题图资源。也可在[资源下载页](https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.41)取得`opbp-assets-v0.7.41.zip`，再安装：

```bash
python3 scripts/bootstrap_assets.py --archive "$HOME/Downloads/opbp-assets-v0.7.41.zip"
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/bootstrap_assets.py --verify
```

## 原生窗口

完成环境安装后，在源码目录运行：

```bash
zsh scripts/build_macos.sh
```

输出为`build/OPBP Bank.app`，打开后使用本机Python环境与题库。模型设置、导出和测试流程与网页相同。

证书、依赖和端口问题见[故障排查](安装与故障排查.md)。
