# 阿里云百炼配置教程

适用OPBP Bank v0.7.45；2026-10-16核对官方资料。这里配置外部模型，不需要安装Ollama或本地模型。

## 1. 准备自己的账号和API Key

1. 打开[获取API Key官方教程](https://help.aliyun.com/zh/model-studio/get-api-key)，按控制台提示登录、开通模型服务并确认计费。
2. 本项目默认使用华北2（北京）。在相同地域及业务空间创建Key，确认该空间可调用文字和图像模型。
3. Key只在部署者本机保存；仓库、发布包及公开样例均不含维护者Key或免费额度。

## 2. 在OPBP Bank填写哪些值

| 界面项 | 说明 |
|---|---|
| 接口地址 | 优先使用自己控制台的业务空间专属域名，末尾为`/compatible-mode/v1`，不要额外加`/chat/completions` |
| 文字/组卷模型 | 程序预填`qwen3.8-flash`；必须以自己空间可调用的精确模型ID为准 |
| 视觉/批改模型 | 程序预填`qwen3.7-plus`；必须支持图像输入且有调用权限 |
| API Key | Mac在网页填写；Windows/Linux按下方环境变量方式配置，网页Key框留空 |

北京专属域名格式：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。用真实业务空间ID替换占位符，或复制控制台实际提供的地址。程序默认`https://dashscope.aliyuncs.com/compatible-mode/v1`仍属于兼容接入；[官方接入域名说明](https://help.aliyun.com/zh/model-studio/regions)目前推荐业务空间专属域名。两种接入均须匹配自己的Key、地域、空间和模型权限。

这是按量计费接口教程；Coding Plan/Token Plan的专属Key和地址不能与按量接口随意混用。模型列表与图像能力见[模型大全](https://help.aliyun.com/zh/model-studio/models)和[视觉理解](https://help.aliyun.com/zh/model-studio/vision)。账户是否可用及价格以控制台为准。

## 3. 保存和测试

Mac：启动网页→模型设置→填写地址、模型名和自己的Key→保存并做文字/图片连接测试。Key存于系统钥匙串。

Windows PowerShell：若服务已启动，先Control+C停止，在启动服务的同一窗口配置：

```powershell
$env:LAURAPHYSICS_OPEN_API_KEY = '仅在本机替换为自己的密钥'
.venv\Scripts\python.exe scripts/run_web.py --open
```

Linux/macOS终端也支持环境变量（示例仅为占位文本，不是可用Key）：

```bash
export LAURAPHYSICS_OPEN_API_KEY='仅在本机替换为自己的密钥'
.venv/bin/python scripts/run_web.py --open
```

Windows/Linux的网页Key输入框留空，再保存接口与模型名称。本项目读取`LAURAPHYSICS_OPEN_API_KEY`；只设置官方SDK示例中的`DASHSCOPE_API_KEY`不会自动配置本项目。不要把真实Key放在提交材料、代码、截图或录屏里。

## 4. 真实批改演示

按[评委指南](JUDGE_QUICKSTART.md)上传`examples/marking-demo/`中的PDF。先检查本机匹配出的题号，再确认发送模型。先试1份，联通后再批量3份；调用可能产生费用。

连接成功只证明联通；人工预期见[EXPECTED_RESULTS.md](../examples/marking-demo/EXPECTED_RESULTS.md)。记录模型原始结果、错误和教师修正，不把复核后的分数冒充AI准确率。

## 5. 故障定位

| 现象 | 优先核对 |
|---|---|
| 401 | Key是否属于相同地域和空间，复制是否完整 |
| 403 | 当前业务空间的模型授权、账号服务状态 |
| 404 | Base URL与精确模型ID；不要多加接口路径 |
| 429 | 限流、配额及账户额度，按服务端提示重试 |
| 文字联通但图片失败 | 批改模型是否支持图像、权限是否一致、图片请求错误 |
| 保存后仍未配置 | 使用同一进程/终端启动服务；Windows/Linux检查项目环境变量后重启 |

依据：[API Key](https://help.aliyun.com/zh/model-studio/get-api-key)、[地域与域名](https://help.aliyun.com/zh/model-studio/regions)、[OpenAI兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)。不需要评委安装OpenAI SDK，项目已通过自己的兼容HTTP调用实现。
