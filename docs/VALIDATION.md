# 公开发布验收记录

## 2026-10-13，v0.7.41

公开仓库：https://github.com/Laura-LLU/LauraPhysics 。代码 AGPL-3.0-only，题库素材独立许可；原私有 App、钥匙串、学生答卷与历史没有上传或修改。

提交 `ffd9b0ebd3f9574fc31e8174876feb6b07a8e0a3` 的 [GitHub Actions 实际执行](https://github.com/Laura-LLU/LauraPhysics/actions/runs/38420783474)：macOS ARM64、Windows x64、Linux x64 的 Python3.12 从干净环境下载校验资源、安装依赖与 Chromium，129项测试各全部通过，零失败、错误、跳过；可下载各平台 acceptance 附件中的 JSON、JUnit、覆盖率和匿名截图/PDF。最初一次 CI 在资源 Release 尚为草稿时下载失败，公开资源后重新执行通过；没有跳过失败测试。

本地独立 Python3.12.8 ARM64 环境亦为129/129通过。覆盖规则、HTTP、浏览器交互、模拟文字/视觉模型协议、三并发与暂停、教师确认、PDF/ZIP导出。模拟接口不调用真实付费模型，不证明真人手写识别准确率。覆盖率仅统计当前进程，不含 HTTP 子进程。

资源单独发布于 [v0.7.41 Release](https://github.com/Laura-LLU/LauraPhysics/releases/tag/v0.7.41)：6,420张题库/排版图片，667,101,189字节 ZIP，SHA-256 `ca9d308bfc7d0b21c37c903e87db45b6274e97b2350573796de4690c054c7281`，与公开清单及GitHub上传摘要一致。

安装排障实测：本地 Git HTTP/2 曾停滞，HTTP/1.1 新克隆成功；官方 Python 缺CA证书导致首次 HTTPS 下载失败，Mac系统可信CA能建立验证通过的HTTPS连接。指南包含这些操作，不通过禁用TLS校验规避。

第二台实体 Mac、Intel Mac 与真实模型/真人笔迹准确率仍待验收；PNG/JPG扫描件题号识别仍有限制。云端三平台成功不是比赛审核通过，不把已知功能缺口说成已解决。
