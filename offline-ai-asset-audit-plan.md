# 离线 AI 美术资源检测流水线与部署方案

## 1. 核心原则

本方案面向保密美术资源审核，第一优先级是防泄密。

必须满足：

- 不使用任何在线检测 API
- 不上传资源到第三方平台
- 不调用云端模型
- 不让工具运行时联网
- 所有模型、依赖、报告、日志均在本机或内网保存
- 输入资源默认只读，检测过程不得覆盖原始文件

## 2. 检测目标

覆盖资源类型：

| 类型 | 格式 |
|---|---|
| 图片资源 | jpg, jpeg, png, webp, bmp, tga, tif, tiff |
| 3D 模型 | fbx, obj, glb, gltf, blend |
| 设计/矢量 | svg, pdf |
| 后续扩展 | psd, psb, ai, eps, heic, avif |

输出结果：

- JSON 报告
- CSV 汇总
- HTML 离线报告
- 风险等级
- 证据链记录
- 人工复核清单
- 代码审计结果

## 3. 总体流水线

```text
输入目录
  ↓
文件识别与哈希
  ↓
安全预扫描
  - 禁止软链接逃逸
  - 文件大小限制
  - 格式白名单
  - SHA256 记录
  ↓
元数据/证据链扫描
  - aicheck
  - ExifTool
  - c2patool
  ↓
资源类型分流
  - 图片：直接模型检测
  - 3D：提取贴图 + Blender 多角度渲染
  - SVG/PDF：元数据解析 + 本地渲染成图片
  ↓
本地模型推理
  - Community-Forensics：主检测
  - Organika/sdxl-detector：SD/SDXL 专项
  - RA-Det：泛化复核，第二阶段接入
  - SPAI/HEDGE：抗压缩补充，第二阶段接入
  ↓
风险融合
  ↓
代码审计联动
  ↓
输出离线报告
  ↓
人工复核
```

## 4. 推荐模型与工具组合

### 第一阶段

优先部署：

```text
aicheck
ExifTool
c2patool
Community-Forensics 384
Organika/sdxl-detector
Blender headless
```

### 第二阶段

增强鲁棒性：

```text
RA-Det
SPAI
HEDGE
CNNDetection / Nahrawy 作为 baseline
```

### 模块定位

| 模块 | 定位 |
|---|---|
| aicheck | 元数据、水印、来源标记扫描 |
| ExifTool | EXIF/XMP/IPTC/软件痕迹 |
| c2patool | C2PA 内容凭证验证 |
| Community-Forensics | 通用 AI 图片检测主模型 |
| Organika/sdxl-detector | SD/SDXL/CivitAI/LoRA 专项复核 |
| RA-Det | 未知生成器泛化检测 |
| SPAI/HEDGE | 压缩、裁剪、转码后鲁棒检测 |
| Blender | FBX/OBJ/GLB 渲染成多角度图片 |

## 5. 风险等级

不要只输出 `AI / 非 AI`，建议使用分级结论：

| 等级 | 含义 |
|---|---|
| Confirmed AI | 明确 AI 元数据、C2PA 标记，或多模型极高置信一致 |
| Likely AI | 主模型高风险，并且至少一个专项模型或鲁棒模型支持 |
| Suspicious | 单模型高风险、元数据异常、图像质量可疑，进入人工复核 |
| Likely Human | 多模型低风险，且无 AI 元数据证据 |
| Inconclusive | 文件损坏、过度压缩、模型分歧大、信息不足 |

### 融合权重建议

完整模型接入后：

```text
元数据明确 AI：直接 Confirmed AI

否则：
Community-Forensics      0.35
RA-Det                   0.25
SPAI / HEDGE             0.20
Organika/sdxl-detector   0.15
CNNDetection/Nahrawy     0.05
```

第一阶段临时权重：

```text
Community-Forensics      0.65
Organika/sdxl-detector   0.25
元数据异常               0.10
```

## 6. 离线部署步骤

### 6.1 机器划分

准备两类机器：

```text
下载机：
可联网，只用于下载源码、模型、依赖包。

审核机：
内网或单机，禁止访问外网，真正处理保密资源。
```

### 6.2 下载机准备目录

```text
ai_asset_audit_bundle/
  packages/
  wheels/
  models/
  tools/
  source/
  checksums/
  docker/
```

### 6.3 下载工具

需要提前下载：

```text
ExifTool
c2patool
aicheck
Blender LTS
ffmpeg
ImageMagick 或 OpenImageIO，可选
Python 依赖 wheel 包
模型源码与权重
```

### 6.4 下载模型权重

目录建议：

```text
models/
  community-forensics/
  organika-sdxl-detector/
  cnn-detection/
  spai/
  ra-det/
  hedge/
```

Hugging Face 模型必须提前缓存。审核机运行时不允许联网。

### 6.5 生成校验文件

Linux:

```bash
sha256sum models/**/* > checksums/models.sha256
sha256sum tools/**/* > checksums/tools.sha256
sha256sum wheels/**/* > checksums/wheels.sha256
```

Windows PowerShell:

```powershell
Get-ChildItem .\models -Recurse -File | Get-FileHash -Algorithm SHA256
Get-ChildItem .\tools -Recurse -File | Get-FileHash -Algorithm SHA256
Get-ChildItem .\wheels -Recurse -File | Get-FileHash -Algorithm SHA256
```

### 6.6 拷贝离线包

将 `ai_asset_audit_bundle/` 拷贝到审核机，并在审核机上校验 hash。

### 6.7 设置离线环境变量

Linux:

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export NO_PROXY=*
```

Windows PowerShell:

```powershell
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
$env:HF_DATASETS_OFFLINE="1"
$env:NO_PROXY="*"
```

### 6.8 阻断联网

建议三层控制：

```text
操作系统防火墙：禁止 Python、Blender、ffmpeg、检测程序出站
容器网络：Docker 使用 --network none
程序层：禁用 requests/httpx/aiohttp 的外部访问
```

Docker 示例：

```bash
docker run --rm --network none \
  -v /secure/input:/app/input:ro \
  -v /secure/reports:/app/reports \
  -v /secure/models:/app/models:ro \
  ai-asset-audit:offline
```

### 6.9 执行检测

示例命令：

```bash
asset-audit scan \
  --input /secure/input \
  --output /secure/reports \
  --models /secure/models \
  --offline \
  --no-upload \
  --render-3d \
  --report html,json,csv
```

## 7. FBX / 3D 检测流程

FBX 不能直接丢给图片 AI 检测模型，应采用贴图检测 + 渲染图检测 + 元数据分析。

```text
fbx
  ↓
读取文件哈希、大小、创建时间
  ↓
Blender headless 导入
  ↓
提取：
  - mesh 数量
  - vertex/face 数
  - 材质数量
  - 贴图路径
  - 外部引用
  - 导出软件信息
  ↓
收集贴图：
  - basecolor
  - albedo
  - diffuse
  - normal
  - roughness
  - metallic
  - emissive
  ↓
贴图进入图片检测模型
  ↓
自动渲染 6-12 张视角图
  ↓
渲染图进入图片检测模型
  ↓
输出 3D 资产风险报告
```

3D 资源有效证据：

```text
贴图检测结果
渲染图检测结果
模型元数据
导出软件信息
材质和贴图路径异常
人工复核意见
```

## 8. 代码审计联动

代码审计的目标是确认检测工具、脚本、依赖、插件不会泄密。

### 8.1 联网行为审计

扫描关键调用：

```text
requests
httpx
aiohttp
urllib
socket
websocket
grpc
boto3
google cloud
azure
openai
huggingface_hub 在线下载
subprocess 调 curl/wget/powershell Invoke-WebRequest
```

命令：

```bash
rg -n "requests\.|httpx\.|aiohttp|urllib|socket|websocket|grpc|boto3|openai|huggingface_hub|snapshot_download|from_pretrained|curl|wget|Invoke-WebRequest|Invoke-RestMethod" .
```

要求：

```text
允许 from_pretrained(local_path)
禁止 from_pretrained("远程 repo", 未设置 local_files_only=True)
禁止 snapshot_download 在审核机运行
禁止任何上传接口
```

### 8.2 文件外传审计

扫描：

```text
upload
post
put
multipart
form-data
S3
OSS
COS
FTP
SFTP
SMTP
```

命令：

```bash
rg -n "upload|multipart|form-data|\.post\(|\.put\(|s3|oss|cos|ftp|sftp|smtp|sendmail" .
```

### 8.3 日志泄密审计

重点检查日志是否写入：

```text
原图路径
绝对路径
用户名
项目名
完整 EXIF
完整图片 base64
高分辨率缩略图
模型输入中间图
```

日志只允许：

```text
sha256
相对路径或脱敏路径
文件类型
分辨率
模型分数
风险等级
错误码
```

### 8.4 依赖供应链审计

建议执行：

```bash
pip-audit
safety check
npm audit
trivy fs .
semgrep
bandit -r .
```

离线环境可以在下载机生成依赖审计报告，再随包带入内网。

## 9. 运行时防泄密配置

检测程序启动前必须检查：

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_DATASETS_OFFLINE=1
网络不可达
模型路径为本地路径
输入目录只读
输出目录在允许范围内
报告不包含原图副本
```

如果检测到联网能力，程序应拒绝启动：

```text
ERROR: Offline mode violation. Network is reachable.
```

## 10. 报告格式

单个资源报告示例：

```json
{
  "file_id": "sha256:xxxx",
  "relative_path": "characters/hero/body.png",
  "type": "image",
  "size_bytes": 1234567,
  "dimensions": "2048x2048",
  "metadata": {
    "exif_detected": true,
    "c2pa_detected": false,
    "software": "unknown",
    "ai_marker": false
  },
  "models": {
    "community_forensics": 0.91,
    "organika_sdxl": 0.76,
    "spai": null,
    "ra_det": null
  },
  "final_label": "Likely AI",
  "confidence": 0.87,
  "review_required": true,
  "evidence": [
    "Main detector high confidence",
    "SDXL detector high confidence",
    "No authoritative C2PA manifest"
  ]
}
```

HTML 报告注意事项：

```text
默认不保存原图副本
缩略图默认关闭，或仅保存低分辨率、带水印、不可还原缩略图
若有内网 Web 页面，优先动态读取本地文件，不复制资产
```

## 11. 目录规范

应用目录：

```text
/opt/ai-asset-audit/
  app/
  models/
  tools/
  config/
  rules/
  reports/
  logs/
```

资源目录：

```text
/secure/input/
  project_a/
  project_b/

/secure/reports/
  2026-05-25-project-a/
    report.html
    report.json
    report.csv
    audit.log
```

权限建议：

```text
input：只读
models：只读
tools：只读
reports：可写
logs：可写但脱敏
```

## 12. 上线验收清单

上线前必须通过：

```text
断网运行成功
模型不会自动下载
检测程序无法访问公网
报告不包含原始资源
日志不包含敏感路径和 EXIF 全量
FBX 渲染不访问外部贴图 URL
代码审计无上传/外联逻辑
依赖包 hash 校验通过
同一输入重复运行结果稳定
误报样本进入人工复核队列
```

## 13. 推荐落地顺序

### 第一阶段

2-3 天内做出可用版：

```text
图片检测
元数据扫描
Community-Forensics
Organika/sdxl-detector
JSON/CSV/HTML 报告
离线启动检查
基础代码审计
```

### 第二阶段

```text
FBX/OBJ/GLB 支持
Blender 多角度渲染
贴图检测
人工复核列表
```

### 第三阶段

```text
RA-Det
SPAI/HEDGE
更完整代码审计
内网 Web 审核台
权限与审计日志
```

## 14. 最终推荐

推荐建设：

```text
离线资产审核系统
= 本地证据链扫描
+ 本地 AI 图片模型
+ 3D 资源贴图/渲染检测
+ 风险融合
+ 本地报告
+ 代码审计防泄密
+ 运行时强制断网
```

第一版核心组合：

```text
aicheck
ExifTool
c2patool
Community-Forensics
Organika/sdxl-detector
Blender headless
Semgrep/Bandit/rg 代码审计规则
```

重点不是模型数量最多，而是：

```text
资源绝不出内网
证据可追溯
检测结果可复核
工具本身经过防泄密审计
```
