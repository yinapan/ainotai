# 保密美术资源 AI 离线审计工具

当前仓库是单机试点最小可用版，重点先实现：

- 本地文件扫描和 SHA256 记录
- 元数据轻量 AI 签名检测
- 离线环境检查
- 代码审计规则扫描
- JSON / CSV / Markdown 报告

不会自动下载模型，不会调用在线 API，不会上传资源。

## 单机试点流程

联网准备阶段：

```powershell
# 只下载依赖、工具、模型；不要放入真实保密资源
```

断网审核阶段：

```powershell
.\scripts\run_doctor.ps1
.\scripts\run_scan.ps1 -InputPath .\input_assets -OutputPath .\reports
.\scripts\audit_code.ps1
```

`doctor --offline` 会要求以下环境变量为 `1`：

```text
HF_HUB_OFFLINE
TRANSFORMERS_OFFLINE
HF_DATASETS_OFFLINE
```

脚本会在当前 PowerShell 会话中设置它们。

## 当前限制

第一版尚未接入真实深度学习模型权重。`models/` 下已预留目录，后续把 Community-Forensics、NPR、UniversalFakeDetect、Organika 等本地权重放入后，再接入推理适配器。
