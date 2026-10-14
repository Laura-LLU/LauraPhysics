# 新 Mac 从 GitHub 部署与验收

适用 v0.7.41。接收者独立安装，不复制原 Mac 的运行环境、钥匙串、历史、学生原卷，也不要只复制 `.app`。先验收网页版，与 App 使用同一后端。

## 1. 前提

Python 3.10–3.14，推荐 3.12；检查 `python3 --version`。系统 3.9 不够，可从 https://www.python.org/downloads/macos/ 安装 3.12；有 Homebrew 也可安装 `python@3.12`。Git 用 `git --version` 检查，按 macOS 提示安装开发工具即可，也可用 GitHub 的 Download ZIP。

需要网络，建议至少 4 GB 空间。首次下载题图约 636 MB，解压约 690 MB，依赖与测试浏览器还需空间。源码放本地硬盘，不放 iCloud/网络同步目录。

## 2. 克隆与独立安装

```bash
mkdir -p "$HOME/Applications/LauraPhysics-Source"
cd "$HOME/Applications/LauraPhysics-Source"
git clone https://github.com/Laura-LLU/LauraPhysics.git
cd LauraPhysics
# 若没有另行设置证书，当前终端使用 Mac 自带的可信 CA；不关闭 HTTPS 验证。
export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/cert.pem}"
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
```

若目标目录已存在，先检查自己的旧工作，不删除覆盖。安装会下载锁定 Release 题图、校验 ZIP/逐图片 SHA-256，创建本项目 `.venv`、安装锁定依赖并检查完整题库；不修改系统 Python。

`--check` 应有 `ok:true`、`questionCount:900`、`missingAssets:[]`、`bundledWheelEnabled:false`，无需密钥。

## 3. 启动与人工操作

```bash
.venv/bin/python scripts/run_web.py --open
```

访问 http://127.0.0.1:8895/ ，保持终端运行，退出用 `Control+C`。端口被其他程序占用时用 `--port 8896 --open`，不要改成公网监听。

无模型也可检查：OPBP组卷→搜 P402/P403-1/P478→加入作业→预览→导出学生/教师卷。检查图片、中文、英文间距与 PDF 下载。

若要与目标 Mac 上已有 LauraPhysics 数据完全隔离，在启动前设置：

```bash
export LAURAPHYSICS_OPEN_DATA="$PWD/.local/state"
export LAURAPHYSICS_OPEN_OUTPUT="$PWD/.local/exports"
export LAURAPHYSICS_DISABLE_LEGACY_CONFIG=1
.venv/bin/python scripts/run_web.py --open
```

只影响当前终端，不移动或删除旧数据；`.local` 不上传 GitHub。

## 4. 自动化测试

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

测试自行选端口、启动隔离服务，无需密钥，不调用付费模型。首次下载测试依赖/Chromium需网络，后续可不带 `--install`。

`test-results/test-result.json` 应为 `ok:true`、失败/错误/跳过均0。发布新增测试后总数会变，不只比较旧115。查看 JUnit、日志、覆盖率页面和 `evidence/` 截图、PDF/ZIP。模拟模型的流程成功不等于真实手写准确率。

## 5. 真实 AI 单独验收

用自己的账户在网页模型设置填写兼容接口、文字/视觉模型及 Key，Mac 保存到系统钥匙串；不写仓库、不出现在截图/反馈。

默认百炼 `qwen3.8-flash` 组卷、`qwen3.7-plus` 批改，先确认账户可用和额度。文字/图片连接测试只证明联通。

首次打开已自动填入百炼接口及模型名，只需填写自己的百炼 API Key。无需安装本地 Qwen / Ollama，界面不再提供 DeepSeek 或本地 Qwen 快捷入口。仓库不附带作者密钥或免费额度；已有显式保存配置保留，不会自动覆盖。

使用有权发送的匿名自写样例：自然语言组卷→导出→写明显对/错/空白答案→上传保留印刷 P 题号的 PDF→本机匹配确认→AI批改→教师复核→单份确认→批量导出。四份卷检查最多三并发、暂停切页、继续、自动下一份。原卷标注、评分栏、总分与总结应一致。

调用可能计费；不要上传未授权学生原卷。扫描 PNG/JPG 自动题号识别有限制，不把失败误认为安装失败。

## 6. 下载失败与资源核验

在 [v0.7.41 Release](https://github.com/Laura-LLU/LauraPhysics/releases/tag/v0.7.41) 手动下载 `opbp-assets-v0.7.41.zip`：

```bash
python3 scripts/bootstrap_assets.py --archive "$HOME/Downloads/opbp-assets-v0.7.41.zip"
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/bootstrap_assets.py --verify
```

校验错误时重下完整文件，不关闭校验。安装器不会覆盖已自行修改的图片。

## 7. 排查与回传

| 问题 | 操作 |
|---|---|
| Git拉取长时间卡住/HTTP2报错 | 在新的目标目录使用 `git -c http.version=HTTP/1.1 clone https://github.com/Laura-LLU/LauraPhysics.git`，或GitHub Download ZIP；不覆盖自己的旧目录 |
| Python 太旧 | 安装3.12并重建本项目独立环境 |
| CERTIFICATE_VERIFY_FAILED | 官方Python安装包可能未安装CA证书；运行其 `Install Certificates.command`，或按上方步骤在当前终端设置 `SSL_CERT_FILE=/etc/ssl/cert.pem` 后重试。不要关闭TLS校验；换新终端需重新设置，模型请求也需要可信证书 |
| ModuleNotFoundError | 使用 `.venv/bin/python`，重新安装，不借用作者 vendor |
| Chromium 未就绪 | `.venv/bin/python -m playwright install chromium` |
| 页面打不开 | 检查终端、端口和错误日志 |
| 模型404/额度不足 | 核对自己模型与账户，重装不能解决权限 |
| 扫描件失败 | 优先用可提取印刷题号的 PDF，见已知限制 |
| 排版不对 | 提供合法匿名 PDF 和具体页号 |

回传 macOS 版本、Apple Silicon/Intel、Python版本、`git rev-parse HEAD`、`test-result.json` 和失败日志。只提供匿名可公开输出，不回传密钥、真实原卷、`.local` 或整个测试状态目录。只有第二台实体 Mac 的真实结果才能完成异机验收。
