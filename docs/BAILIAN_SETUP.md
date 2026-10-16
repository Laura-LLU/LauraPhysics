# 阿里云百炼配置

## 准备账户

登录[百炼控制台](https://bailian.console.aliyun.com/)，开通模型服务，在华北2（北京）对应业务空间创建API Key，确认文字和视觉模型权限。

[API Key教程](https://help.aliyun.com/zh/model-studio/get-api-key) · [地域与接入域名](https://help.aliyun.com/zh/model-studio/regions) · [模型列表](https://help.aliyun.com/zh/model-studio/models)

## 模型设置

| 项目 | 填写内容 |
|---|---|
| 接口地址 | 程序默认`https://dashscope.aliyuncs.com/compatible-mode/v1`，也可填写自己控制台提供的业务空间兼容接口 |
| 文字/组卷模型 | 默认`qwen3.8-flash`，填写自己账户可调用的精确模型ID |
| 视觉/批改模型 | 默认`qwen3.7-plus`，选择支持图像输入的模型 |
| API Key | macOS在页面保存，Windows / Linux用环境变量传入 |

业务空间专属地址格式为`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`，将`{WorkspaceId}`替换为控制台中的空间ID。接口、Key、地域与业务空间应匹配，地址填写到`/v1`。

本教程使用按量计费兼容接口；账户可用模型、权限和费用以自己的控制台为准。[兼容接口说明](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) · [图像理解](https://help.aliyun.com/zh/model-studio/vision)

## 保存与连接测试

macOS：启动网页→“模型设置”→填写接口、模型与Key→保存→文字和图片连接测试。Key存于系统钥匙串。

Windows PowerShell：在启动服务的终端设置自己的Key，再启动：

```powershell
$env:LAURAPHYSICS_OPEN_API_KEY = '在本机填写自己的密钥'
.venv\Scripts\python.exe scripts/run_web.py --open
```

Linux：

```bash
export LAURAPHYSICS_OPEN_API_KEY='在本机填写自己的密钥'
.venv/bin/python scripts/run_web.py --open
```

Windows / Linux在页面保存接口和模型名称，Key输入框留空。环境变量作用于当前终端启动的服务。

## 试运行

1. 在“AI组卷”输入主题和题数，生成预览并导出。
2. 在“AI批改”上传[完整自写试卷](../examples/full-papers/README.md)，核对题号后确认发送。
3. 逐题复核模型结果、修改得分点、确认并导出。调用使用自己账户的额度，密钥保留在本机。

## 故障定位

| 现象 | 检查项 |
|---|---|
| 401 | Key、地域、业务空间和复制完整性 |
| 403 | 模型权限与账户服务状态 |
| 404 | 接口地址、模型ID与路径 |
| 429 | 额度、配额和限流提示 |
| 文字通过、图片失败 | 视觉模型的图像输入能力、权限和请求错误 |
| 保存后未配置 | 环境变量是否设置在启动服务的同一终端；设置后重新启动服务 |
