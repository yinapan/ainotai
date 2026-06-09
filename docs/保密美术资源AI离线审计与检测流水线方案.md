# 保密美术资源 AI 离线审计与检测流水线方案

> 核心原则：不使用任何在线检测 API；不上传资源；不调用云端模型；审核机运行时禁止联网；所有检测、推理、报告和审计均在本地或内网完成。

## 1. 目标与边界

本方案用于对保密美术资源进行离线 AI 生成风险检测，适用于游戏、影视、广告、产品视觉等内部资产入库审核。

目标：

- 检测图片、贴图、3D 模型、设计文件中的 AI 生成风险
- 形成可追溯的证据链和风险分级
- 支持本地 CLI、内网 CI、人工复核流程
- 联动代码审计，防止工具、脚本、依赖泄密
- 保证资源不出本机或内网

非目标：

- 不承诺 100% 判断 AI / 非 AI
- 不使用任何在线平台做检测
- 不将报告、缩略图、原始资源上传到外部系统
- 不在审核机运行任何自动下载、自动更新、远程模型加载逻辑

## 2. 安全架构

当前阶段采用单机试点部署，正式环境升级为下载机和审核机双机分离。

单机试点不是放松安全要求，而是把“联网准备”和“断网审核”拆成同一台机器上的两个阶段：

```text
阶段 1：联网准备阶段
  - 只下载源码、模型、依赖、工具
  - 不处理真实保密资源
  - 生成 hash 清单
  - 生成离线安装包
  - 完成后关闭外网访问

阶段 2：断网审核阶段
  - 处理真实保密资源
  - 加载本地模型
  - 生成本地报告
  - 禁止自动下载和外部访问
  - Docker 使用 --network none
```

正式环境采用双机分离：

```text
下载机：
  - 可联网
  - 只用于下载源码、模型、依赖、工具
  - 生成 hash 清单
  - 生成离线安装包

审核机：
  - 不联网
  - 处理真实保密资源
  - 加载本地模型
  - 生成本地报告
  - 禁止自动下载和外部访问
```

断网审核阶段或正式审核机必须满足：

- 操作系统防火墙禁止检测程序、Python、Blender、ffmpeg 出站
- Docker 运行时使用 `--network none`
- 输入目录只读
- 模型、工具、配置目录只读
- 报告目录可写
- 日志脱敏
- 启动前执行断网检查

离线环境变量：

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export NO_PROXY=*
```

Windows PowerShell：

```powershell
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
$env:HF_DATASETS_OFFLINE="1"
$env:NO_PROXY="*"
```

## 3. 支持资源格式

| 类型 | 第一阶段 | 第二阶段 |
|---|---|---|
| 图片 | jpg, jpeg, png, webp, bmp, tga, tif, tiff | heic, avif |
| 3D 模型 | fbx, obj, glb, gltf, blend | usd, usdz, dae, stl |
| 设计/矢量 | svg, pdf | psd, psb, ai, eps |
| 模型权重 | pth, pt, safetensors, onnx, Hugging Face 本地缓存 | TensorRT, OpenVINO |

## 4. 总体流水线

```text
输入资源目录
  ↓
安全预扫描
  - 路径规范化
  - 禁止软链接逃逸
  - 格式白名单
  - 文件大小限制
  - SHA256 记录
  ↓
元数据与证据链扫描
  - aicheck
  - ExifTool
  - c2patool
  - PNG/XMP/IPTC 自定义解析
  ↓
资源类型分流
  - 图片：像素取证 + 模型推理
  - 3D：贴图提取 + 网格分析 + 多角度渲染
  - SVG/PDF：元数据解析 + 本地渲染成图片
  ↓
本地模型推理
  - Community-Forensics
  - NPR
  - UniversalFakeDetect
  - Organika/sdxl-detector
  - 第二阶段：RA-Det / SPAI / HEDGE
  ↓
风险融合与分级
  ↓
代码审计联动
  ↓
输出 JSON / CSV / Markdown / HTML 离线报告
  ↓
人工复核
```

## 5. 工具与模型选型

### 5.1 必选工具

| 工具 | 用途 | 联网需求 |
|---|---|---|
| aicheck | 元数据、水印、来源标记扫描 | 不联网 |
| ExifTool | EXIF/XMP/IPTC/ICC 元数据提取 | 不联网 |
| c2patool | C2PA 内容凭证验证 | 不联网 |
| Pillow/OpenCV | 图片解码、预处理、像素取证 | 不联网 |
| Blender headless | FBX/OBJ/GLB 渲染和 3D 分析 | 不联网 |
| Trimesh/Open3D | 3D 网格拓扑和质量分析 | 不联网 |
| ripgrep/Bandit/Semgrep | 代码审计 | 不联网或离线规则 |

### 5.2 模型组合

第一阶段：

| 模型 | 定位 |
|---|---|
| Community-Forensics 384 | 主检测模型，通用 AI 图片检测 |
| NPR | 快速预筛，相邻像素关系检测 |
| UniversalFakeDetect | CLIP 特征辅助交叉验证 |
| Organika/sdxl-detector | SD/SDXL/CivitAI/LoRA 专项复核 |

第二阶段：

| 模型 | 定位 |
|---|---|
| RA-Det | 未知生成器泛化复核 |
| SPAI | 频谱鲁棒检测，适合压缩/转码图 |
| HEDGE | 高精度离线复核，适合重型 ensemble |
| CNNDetection/Nahrawy | baseline 对照，不作为主判定 |

注意：

- `Organika/sdxl-detector` 需要确认许可证。若用于商业内部审核，应由法务确认 Hugging Face 模型卡许可证和使用边界。
- ELA、FFT、噪声分析只能作为辅助证据，不能单独判定 `Confirmed AI`。
- 所有 Hugging Face 模型必须提前下载到本地，断网审核阶段或正式审核机推理时使用 `local_files_only=True`。

## 6. 三层检测策略

### 6.1 第一层：元数据与证据链

检测内容：

- EXIF `Software`
- XMP `CreatorTool`
- PNG `tEXt/iTXt/zTXt`
- IPTC 字段
- C2PA manifest
- AI 生成参数
- prompt / negative prompt
- seed / sampler / cfg / steps / model hash
- ComfyUI / AUTOMATIC1111 / Midjourney / Firefly / DALL-E 等工具痕迹

命中明确 AI 元数据时，可以直接标记为 `Confirmed AI`，但仍保留原始证据。

签名规则建议维护在：

```text
config/signatures.yaml
```

示例规则：

```yaml
ai_software:
  - stable diffusion
  - automatic1111
  - comfyui
  - invokeai
  - midjourney
  - dall-e
  - adobe firefly
  - novelai
  - liblib
  - 即梦
  - 通义万相
  - 文心一格

ai_parameter_patterns:
  - "steps:\\s*\\d+"
  - "sampler:\\s*\\w+"
  - "cfg[\\s_]scale:\\s*[\\d.]+"
  - "seed:\\s*\\d+"
  - "model[\\s_]hash:\\s*[a-f0-9]+"
  - "negative[\\s_]prompt:"
  - "lora:"
  - "controlnet"
```

### 6.2 第二层：像素取证

用于辅助判断，不单独定罪。

| 方法 | 作用 | 风险 |
|---|---|---|
| ELA | 检查 JPEG 重压缩误差分布 | 二次编辑图容易误判 |
| FFT/DCT | 检查频域异常和周期伪影 | UI/纹理图容易异常 |
| 噪声一致性 | 检查噪声是否过度均匀 | 降噪图、渲染图容易误判 |
| 色彩统计 | 检查色彩分布平滑性 | 插画风格影响大 |
| JPEG 量化表 | 判断是否接近相机或软件导出 | 只能辅助 |

像素取证输出应进入 `Suspicious` 或模型融合，不应直接输出 `Confirmed AI`。

### 6.3 第三层：本地模型推理

第一阶段推荐权重：

```text
Community-Forensics      0.45
UniversalFakeDetect      0.25
NPR                      0.15
Organika/sdxl-detector   0.15
```

第二阶段完整权重：

```text
Community-Forensics      0.35
RA-Det                   0.25
SPAI / HEDGE             0.20
Organika/sdxl-detector   0.15
NPR / UniversalFakeDetect 0.05
```

若元数据明确 AI：

```text
直接 Confirmed AI
无需依赖模型分数
```

## 7. 3D / FBX 检测方案

FBX、OBJ、GLB、GLTF、BLEND 不能直接用图片 AI 模型判断，需要拆解为：

```text
3D 文件
  ↓
元数据分析
  - 导出软件
  - 创建工具
  - 外部引用
  - 材质命名
  ↓
贴图提取
  - basecolor
  - albedo
  - diffuse
  - normal
  - roughness
  - metallic
  - emissive
  ↓
贴图进入图片检测流水线
  ↓
Blender headless 渲染 6-12 视角
  ↓
渲染图进入图片检测流水线
  ↓
网格/拓扑分析
  - mesh 数量
  - vertex/face 数
  - 非流形比例
  - UV 异常
  - 材质重复
  ↓
输出 3D 资产风险报告
```

3D 资源结论应谨慎。更推荐输出：

```text
Likely AI-assisted
Suspicious
Inconclusive
Likely Human
```

## 8. 风险分级

| 等级 | 条件 |
|---|---|
| Confirmed AI | 明确 AI 元数据/C2PA，或多个模型极高置信一致并经人工确认 |
| Likely AI | 主模型高风险，且至少一个辅助模型或专项模型支持 |
| Suspicious | 单模型高风险、像素取证异常、元数据可疑 |
| Likely Human | 多模型低风险，且无 AI 元数据证据 |
| Inconclusive | 文件损坏、过度压缩、模型分歧大、信息不足 |

建议阈值：

```text
>= 0.85  Likely AI / Confirmed AI 候选
0.65-0.85 Likely AI
0.45-0.65 Suspicious
0.25-0.45 Likely Human
< 0.25 Low AI evidence
```

`Confirmed AI` 不建议完全自动化，应满足：

- 元数据明确 AI；或
- 多模型强一致 + 人工复核确认。

## 9. 项目结构

```text
ai-asset-audit/
  src/
    scanner/
      file_scanner.py
      format_detector.py
    metadata/
      exif_analyzer.py
      png_chunks.py
      c2pa_checker.py
      xmp_parser.py
      signatures.py
      aicheck_runner.py
    forensics/
      ela.py
      frequency.py
      noise.py
      color_stats.py
      jpeg_forensics.py
    models/
      base.py
      community_forensics.py
      universal_fake.py
      npr_detect.py
      sdxl_detector.py
      ensemble.py
    threed/
      blender_render.py
      texture_extractor.py
      mesh_analysis.py
      topology.py
    pipeline/
      pipeline.py
      scorer.py
      offline_guard.py
    report/
      json_report.py
      csv_report.py
      markdown_report.py
      html_report.py
      evidence.py
    audit/
      code_audit.py
      dependency_audit.py
      log_redaction.py
  config/
    config.yaml
    signatures.yaml
    thresholds.yaml
    audit_rules.yaml
  models/
    community-forensics/
    universal-fake-detect/
    npr/
    sdxl-detector/
  tools/
    exiftool/
    c2patool/
    aicheck/
    blender/
  scripts/
    prepare_offline_bundle.sh
    verify_hashes.sh
    run_offline_scan.sh
  docs/
  tests/
  cli.py
  pyproject.toml
  Dockerfile
```

## 10. 配置文件

```yaml
security:
  offline_required: true
  fail_if_network_reachable: true
  allow_remote_urls: false
  input_readonly_required: true
  redact_logs: true
  save_original_assets: false
  save_thumbnails: false

scan:
  extensions:
    image: [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga", ".tif", ".tiff"]
    threed: [".fbx", ".obj", ".glb", ".gltf", ".blend"]
    vector: [".svg", ".pdf"]
  max_file_size_mb: 500
  parallel_workers: 4

metadata:
  enabled: true
  exiftool_path: "./tools/exiftool/exiftool"
  c2patool_path: "./tools/c2patool/c2patool"
  aicheck_path: "./tools/aicheck/aicheck"
  signatures_file: "./config/signatures.yaml"

forensics:
  enabled: true
  ela:
    enabled: true
    quality: 90
  frequency:
    enabled: true
    method: "fft"
  noise:
    enabled: true
  color_stats:
    enabled: true

models:
  enabled: true
  device: "cuda"
  local_files_only: true
  batch_size: 8
  community_forensics:
    enabled: true
    weight: 0.45
    path: "./models/community-forensics"
  universal_fake_detect:
    enabled: true
    weight: 0.25
    path: "./models/universal-fake-detect"
  npr:
    enabled: true
    weight: 0.15
    path: "./models/npr"
  sdxl_detector:
    enabled: false
    weight: 0.15
    path: "./models/sdxl-detector"

threed:
  enabled: true
  blender_path: "./tools/blender/blender"
  render_views: 8
  render_resolution: 512
  extract_textures: true

report:
  formats: ["json", "csv", "markdown", "html"]
  output_dir: "./reports"
  include_original_assets: false
  include_highres_preview: false
  include_lowres_thumbnail: false

thresholds:
  likely_ai: 0.65
  suspicious: 0.45
  likely_human: 0.25
```

## 11. CLI 设计

```bash
# 环境检查，必须验证断网和本地模型
python cli.py doctor --offline

# 扫描目录
python cli.py scan ./assets --config ./config/config.yaml --offline

# 扫描文件列表
python cli.py scan --mode file-list --input changed_files.txt --offline

# 内网 CI 模式
python cli.py scan --ci --mode git-diff --base origin/main --offline

# 仅元数据
python cli.py scan ./assets --layer metadata --offline

# 元数据 + 像素取证
python cli.py scan ./assets --layer forensics --offline

# 完整检测
python cli.py scan ./assets --layer full --offline

# 扫描 3D 资源
python cli.py scan-3d ./assets/models --offline

# 代码审计
python cli.py audit-code ./src --offline

# 模型状态
python cli.py model status --offline
```

退出码：

```text
0 = 无异常
1 = 存在 Suspicious
2 = 存在 Likely AI / Confirmed AI
3 = 检测错误
4 = 离线安全检查失败
```

## 12. 报告格式

单文件 JSON 示例：

```json
{
  "file_id": "sha256:xxxx",
  "relative_path": "characters/hero/body.png",
  "type": "image",
  "size_bytes": 1234567,
  "dimensions": "2048x2048",
  "metadata": {
    "aicheck_ai_marker": false,
    "exif_detected": true,
    "c2pa_detected": false,
    "software": "unknown",
    "signals": []
  },
  "forensics": {
    "ela_uniformity": 0.82,
    "frequency_anomaly": 0.65,
    "noise_consistency": 0.71,
    "combined_score": 0.68
  },
  "models": {
    "community_forensics": 0.91,
    "universal_fake_detect": 0.72,
    "npr": 0.61,
    "organika_sdxl": null
  },
  "final_label": "Likely AI",
  "confidence": 0.82,
  "review_required": true,
  "evidence": [
    "Main detector high confidence",
    "Pixel forensics abnormal",
    "No authoritative C2PA manifest"
  ]
}
```

报告安全要求：

- 默认不保存原图副本
- 默认不保存高清预览
- 缩略图默认关闭
- 日志中不写绝对路径、用户名、项目敏感名、完整 EXIF、图片 base64
- HTML 报告仅在内网打开

## 13. 离线部署步骤

### 13.1 当前阶段：单机试点部署

单机试点分为两个阶段：先联网准备，后断网审核。真实保密资源只允许在断网审核阶段进入输入目录。

#### 阶段 1：联网准备

准备目录：

```text
ai_asset_audit_bundle/
  source/
  wheels/
  models/
  tools/
  config/
  checksums/
  docker/
```

联网准备阶段执行：

```bash
python -m pip download -r requirements.txt -d wheels/
git clone <approved-repo-url> source/
# 下载 ExifTool / c2patool / aicheck / Blender 离线包
# 下载模型权重到 models/
```

生成 hash：

```bash
find source wheels models tools config -type f -print0 | xargs -0 sha256sum > checksums/all.sha256
```

准备完成后：

```text
关闭外网连接
启用防火墙出站阻断
设置离线环境变量
确认真实保密资源尚未进入扫描目录
```

#### 阶段 2：断网审核

断网后安装和运行：

```bash
sha256sum -c checksums/all.sha256
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links wheels -r source/requirements.txt
python source/cli.py doctor --offline
```

确认 `doctor --offline` 通过后，再把保密资源放入只读输入目录并执行扫描。

```bash
docker run --rm --network none \
  -v /secure/input:/app/input:ro \
  -v /secure/models:/app/models:ro \
  -v /secure/tools:/app/tools:ro \
  -v /secure/reports:/app/reports \
  ai-asset-audit:offline \
  python cli.py scan /app/input --offline --output /app/reports
```

单机试点禁止：

```text
在真实保密资源进入机器后重新联网
扫描过程中自动下载模型
扫描过程中访问外部 URL
把报告、缩略图、原始资源上传到外部系统
```

### 13.2 正式环境：双机隔离部署

正式环境中，下载机只负责准备离线包，审核机只允许使用离线包。

下载机执行：

```bash
python -m pip download -r requirements.txt -d wheels/
git clone <approved-repo-url> source/
# 下载 ExifTool / c2patool / aicheck / Blender 离线包
# 下载模型权重到 models/
find source wheels models tools config -type f -print0 | xargs -0 sha256sum > checksums/all.sha256
```

审核机只允许使用离线包：

```bash
sha256sum -c checksums/all.sha256
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links wheels -r source/requirements.txt
```

禁止在单机断网审核阶段或正式审核机执行：

```text
curl
wget
git clone 外网地址
pip install 在线源
conda install 在线源
snapshot_download
from_pretrained("远程 repo")
任何自动更新脚本
```

正式审核机的 Docker 运行方式与单机断网审核阶段一致，必须使用 `--network none`。

## 14. 代码审计联动

### 14.1 联网行为审计

```bash
rg -n "requests\.|httpx\.|aiohttp|urllib|socket|websocket|grpc|boto3|openai|huggingface_hub|snapshot_download|from_pretrained|curl|wget|Invoke-WebRequest|Invoke-RestMethod" .
```

要求：

- 允许 `from_pretrained(local_path, local_files_only=True)`
- 禁止远程 repo 自动加载
- 禁止单机断网审核阶段或正式审核机下载模型
- 禁止上传接口

### 14.2 文件外传审计

```bash
rg -n "upload|multipart|form-data|\.post\(|\.put\(|s3|oss|cos|ftp|sftp|smtp|sendmail" .
```

### 14.3 日志泄密审计

检查是否写入：

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

允许写入：

```text
sha256
脱敏相对路径
文件类型
分辨率
模型分数
风险等级
错误码
```

### 14.4 供应链审计

下载机或离线规则下执行：

```bash
bandit -r src
semgrep --config rules/semgrep .
pip-audit --path .venv
trivy fs .
```

## 15. 内网 CI 集成

允许：

- 内网 GitLab Runner
- 自建 Jenkins
- 本地 pre-commit / pre-push hook
- 内网裸机或内网 Docker Runner

禁止：

- GitHub Hosted Runner
- GitLab.com Shared Runner
- 任何云端 CI
- 任何需要上传资源的扫描平台

pre-commit 示例：

```bash
#!/usr/bin/env bash
set -e

git diff --cached --name-only > /tmp/changed_assets.txt
python cli.py scan \
  --mode file-list \
  --input /tmp/changed_assets.txt \
  --offline \
  --ci
```

内网 GitLab CI 示例：

```yaml
ai_asset_audit:
  stage: test
  tags:
    - internal-offline-runner
  script:
    - export HF_HUB_OFFLINE=1
    - export TRANSFORMERS_OFFLINE=1
    - export HF_DATASETS_OFFLINE=1
    - python cli.py doctor --offline
    - python cli.py scan --ci --mode git-diff --base origin/main --offline
  artifacts:
    when: always
    paths:
      - reports/report.json
      - reports/report.md
    expire_in: 7 days
```

## 16. 性能与短路策略

建议短路：

```text
明确 AI 元数据命中：
  直接 Confirmed AI，不再跑重模型

小图标 / UI 小资源：
  元数据 + 轻量模型优先

高风险图：
  跑完整模型组合

3D 资源：
  优先贴图检测，再按需渲染多视角
```

粗略耗时：

| 阶段 | 单文件耗时 |
|---|---|
| 文件扫描/hash | 1-50ms |
| 元数据扫描 | 1-100ms |
| 像素取证 | 50-300ms |
| NPR | 50-200ms |
| Community-Forensics | 300ms-2s |
| UniversalFakeDetect | 200ms-1s |
| 3D 渲染 | 5s-60s |

## 17. 上线验收清单

上线前必须通过：

```text
断网运行成功
Docker 使用 --network none 成功运行
模型不会自动下载
单机断网审核阶段或正式审核机无法访问公网
报告不包含原始资源
日志不包含敏感路径和完整 EXIF
FBX 渲染不访问外部贴图 URL
代码审计无上传/外联逻辑
依赖包 hash 校验通过
同一输入重复运行结果稳定
误报样本进入人工复核队列
Organika 等模型许可证完成确认
```

## 18. 分阶段落地

第一阶段，最小专业版：

```text
aicheck
ExifTool
c2patool
Community-Forensics
NPR
JSON/CSV/Markdown 报告
离线启动检查
基础代码审计
```

第二阶段，工程增强：

```text
UniversalFakeDetect
Organika/sdxl-detector
ELA/FFT/噪声分析
HTML 报告
内网 CI
```

第三阶段，3D 支持：

```text
FBX/OBJ/GLB/GLTF/BLEND
贴图提取
Blender 多角度渲染
Trimesh/Open3D 网格分析
```

第四阶段，鲁棒增强：

```text
RA-Det
SPAI
HEDGE
人工复核后台
误报样本库
阈值校准
```

## 19. 维护策略

每月维护：

- 更新 AI 工具签名库
- 汇总误报、漏报样本
- 调整阈值
- 校验模型 hash
- 复查依赖漏洞
- 复查联网/上传审计规则

每次模型更新必须：

- 单机试点：在联网准备阶段完成，且真实保密资源不得在场
- 正式环境：在下载机完成
- 记录来源、版本、hash、许可证
- 在测试集回归
- 经安全负责人确认后进入断网审核阶段或正式审核机

## 20. 最终建议

最终方案采用：

```text
方案 A 的安全底座
+ 方案 B 的工程实现
+ 修正后的模型策略
+ 强制离线部署
+ 代码审计防泄密
+ 3D 资源专项处理
```

第一版优先实现：

```text
aicheck + ExifTool + c2patool
+ Community-Forensics + NPR
+ 本地报告
+ 离线启动检查
+ 代码审计
```

资源保密场景下，宁可降低自动化便利性，也不能放松离线边界。当前单机试点必须严格区分联网准备阶段和断网审核阶段；后续正式环境升级为下载机和审核机双机隔离。所有工程实现必须先通过安全边界过滤：凡是联网下载、远程模型、云端 CI、上传接口、自动更新、外部 URL，均不得在断网审核阶段或正式审核机出现。
