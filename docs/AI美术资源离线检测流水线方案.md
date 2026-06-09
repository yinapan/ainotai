# AI 美术资源离线检测流水线方案

> **核心原则：全程离线运行，不调用任何在线 API，不上传资源，不联网。**

---

## 一、方案概述

### 1.1 目标

在游戏美术资源入库的 Git/CI 流水线中，自动检测图片/3D 资源是否为 AI 生成，标记可疑资源交由人工复审。

### 1.2 设计约束

| 约束 | 说明 |
|------|------|
| **完全离线** | 运行时断网，所有模型权重、工具预先部署到位 |
| **不调用云端** | 不使用 Hive AI / SightEngine / GPT-4V 等任何在线服务 |
| **不上传资源** | 资源不离开内网，不经过第三方 |
| **CI 友好** | 可作为 Git Hook / CI Job 运行，输出结构化报告 |
| **可审计** | 检测过程可追溯，报告保留证据链 |

### 1.3 检测流水线总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI 美术资源检测流水线                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐             │
│  │ 文件扫描  │───▶│  预处理/解码  │───▶│ 第一层:元数据  │             │
│  └──────────┘    └──────────────┘    └───────┬───────┘             │
│                                              │                      │
│                          命中 AI 签名 ◀──────┘──────▶ 未命中        │
│                              │                          │           │
│                              ▼                          ▼           │
│                     标记为"高置信AI"         ┌───────────────┐      │
│                                             │ 第二层:像素取证 │      │
│                                             └───────┬───────┘      │
│                                                     │               │
│                              异常 ◀─────────────────┘───▶ 正常     │
│                                │                           │        │
│                                ▼                           ▼        │
│                        标记为"疑似AI"           ┌──────────────┐    │
│                                                │ 第三层:模型推理 │    │
│                                                └──────┬───────┘    │
│                                                       │             │
│                                                       ▼             │
│                                              综合评分 → 报告        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、工具链选型与对比

### 2.1 最终选型

| 工具 | 职责 | 联网需求 | 语言 | 许可证 |
|------|------|----------|------|--------|
| **ExifTool** | EXIF/XMP/IPTC/ICC 元数据提取 | 不联网 | Perl (CLI) | GPL/Artistic |
| **c2patool** | C2PA 内容凭证验证 | 不联网 | Rust (CLI) | Apache-2.0 |
| **Pillow + OpenCV** | 图片解码、预处理、ELA 分析 | 不联网 | Python | PIL License / Apache |
| **Community-Forensics** | 主 AI 图片检测模型（泛化强） | 不联网 | Python/PyTorch | MIT |
| **UniversalFakeDetect** | CLIP 特征 AI 检测（泛化最强） | 不联网 | Python/PyTorch | MIT |
| **NPR** | 相邻像素关系检测（速度最快） | 不联网 | Python/PyTorch | Apache-2.0 |
| **Organika/sdxl-detector** | SD/SDXL 专项检测 | 不联网 | Python/transformers | Apache-2.0 |
| **PhotoHolmes** | 图像取证框架（ELA/噪声/频率） | 不联网 | Python | MIT |
| **Blender headless** | FBX/OBJ/GLB 渲染截图 + 网格分析 | 不联网 | Python API | GPL |
| **Trimesh + Open3D** | 3D 网格拓扑/质量分析 | 不联网 | Python | MIT / BSD |

### 2.2 模型对比（选型依据）

| 模型 | 泛化能力 | 推理速度 | 模型大小 | GAN 检测 | 扩散模型检测 | 适合场景 |
|------|----------|----------|----------|----------|-------------|----------|
| **Community-Forensics** | ★★★★★ | ★★★ | ~1GB | 高 | 高 | 主检测模型 |
| **UniversalFakeDetect** | ★★★★★ | ★★★★ | ~400MB | 高 | 高 | 辅助确认 |
| **NPR** | ★★★★ | ★★★★★ | ~50MB | 高 | 中-高 | 快速预筛 |
| **Organika/sdxl-detector** | ★★★ | ★★★★ | ~350MB | 低 | 高(SDXL) | SD 专项 |
| **DIRE** | ★★★ | ★ | ~2GB | 中 | 高 | 深度确认(慢) |
| **DRCT** | ★★★★ | ★★ | ~1.5GB | 中-高 | 高 | 备选 |

**最终选择：Community-Forensics (主) + UniversalFakeDetect (辅) + NPR (快筛)**

理由：
- Community-Forensics：2024 年最新，使用数千生成器训练，泛化最强
- UniversalFakeDetect：基于 CLIP，结构简单但检测能力强，适合交叉验证
- NPR：轻量极快，适合第一道模型快筛
- Organika/sdxl-detector：专门检测 SD/SDXL，作为补充

### 2.3 淘汰方案说明

| 方案 | 淘汰原因 |
|------|----------|
| DIRE | 推理太慢（需扩散重建），不适合 CI 批量 |
| DRCT | 同理，依赖扩散重建，速度慢 |
| 所有在线 API | 违反离线原则 |
| Go + ONNX Runtime | 模型生态不如 Python 成熟，预处理复杂 |

---

## 三、检测策略详解

### 3.1 第一层：元数据分析（耗时 < 1ms/文件）

**工具：ExifTool + c2patool + 自定义 Python 脚本**

检测内容：

| 检测项 | 方法 | AI 信号示例 |
|--------|------|-------------|
| 软件标识 | EXIF:Software | "Stable Diffusion", "ComfyUI", "AUTOMATIC1111", "NovelAI" |
| 生成参数 | PNG tEXt chunks | "Steps: 20, Sampler: Euler, CFG scale: 7, Seed: 12345" |
| 提示词 | PNG/EXIF UserComment | "prompt:", "negative_prompt:", "Dream:" |
| AI 水印 | XMP/C2PA | ai:generatedWith, c2pa.ai_generated claim |
| 创建工具 | XMP:CreatorTool | "Midjourney", "DALL-E", "Adobe Firefly" |
| 数字凭证 | C2PA manifest | Content Credentials 包含 AI 生成声明 |
| 可疑缺失 | EXIF 完整性 | 正常相机照片有完整 EXIF，AI 图通常没有或很少 |

**AI 工具签名库（持续维护）：**

```python
AI_SOFTWARE_SIGNATURES = [
    # Stable Diffusion 生态
    "stable diffusion", "automatic1111", "a1111", "comfyui",
    "invoke ai", "invokeai", "diffusionbee", "draw things",
    "easy diffusion", "fooocus", "forge",
    # 商业 AI 工具
    "midjourney", "dall-e", "dalle", "openai",
    "adobe firefly", "imagen", "ideogram",
    "leonardo.ai", "playground ai", "nightcafe",
    # 中国 AI 工具
    "通义万相", "文心一格", "即梦", "liblib",
    "百度ai", "腾讯ai", "可图",
    # NovelAI / 动漫
    "novelai", "nai diffusion", "waifu diffusion",
    # 视频/3D AI
    "runway", "pika", "sora", "kling", "可灵",
    "meshy", "tripo", "point-e", "shap-e",
]

AI_PARAMETER_PATTERNS = [
    r"steps:\s*\d+",
    r"sampler:\s*\w+",
    r"cfg[\s_]scale:\s*[\d.]+",
    r"seed:\s*\d+",
    r"model[\s_]hash:\s*[a-f0-9]+",
    r"negative[\s_]prompt:",
    r"denoising[\s_]strength:\s*[\d.]+",
    r"lora:",
    r"controlnet",
]
```

### 3.2 第二层：像素级取证分析（耗时 ~100ms/文件）

**工具：Pillow + OpenCV + PhotoHolmes**

| 分析方法 | 原理 | AI 图像特征 |
|----------|------|-------------|
| **ELA (Error Level Analysis)** | 对 JPEG 重新压缩比较差异 | AI 图 ELA 均匀，真实图 ELA 有层次 |
| **频率域分析 (DCT/FFT)** | 分析频域分布 | AI 图高频成分异常、频谱有周期性伪影 |
| **噪声一致性分析** | 提取图像噪声模式 | AI 图噪声过于均匀或不自然 |
| **色彩直方图分析** | 统计颜色分布 | AI 图色彩分布过于平滑 |
| **JPEG 量化表检查** | 检查量化矩阵 | AI 生成的 JPEG 可能没有标准相机量化表 |
| **边缘连续性** | Canny/Sobel 边缘检测 | AI 图边缘可能有不自然的过渡 |

```python
# ELA 分析核心逻辑
def compute_ela(image_path, quality=90, scale=15):
    """
    Error Level Analysis - AI 图像 ELA 结果趋向均匀
    """
    img = Image.open(image_path)
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer)

    ela = ImageChops.difference(img, recompressed)
    extrema = ela.getextrema()
    max_diff = max([ex[1] for ex in extrema])

    if max_diff == 0:
        return ela, 0.0

    scale_factor = 255.0 / max_diff * scale
    ela = ImageEnhance.Brightness(ela).enhance(scale_factor)

    # 计算 ELA 均匀度（AI 图趋向高均匀度）
    ela_array = np.array(ela.convert("L"))
    uniformity = 1.0 - (ela_array.std() / ela_array.mean() if ela_array.mean() > 0 else 0)

    return ela, uniformity
```

### 3.3 第三层：深度学习模型推理（耗时 ~500ms-2s/文件）

**三模型投票机制：**

```
文件 ──→ NPR (快筛, ~100ms)
      ├──→ Community-Forensics (主模型, ~800ms)
      └──→ UniversalFakeDetect (辅助, ~500ms)
               │
               ▼
         加权投票 → 最终分数
```

**投票权重：**
- Community-Forensics: 0.45（泛化最强，训练数据最丰富）
- UniversalFakeDetect: 0.35（CLIP 特征，独立视角）
- NPR: 0.20（速度快但泛化稍弱）

**当 Organika/sdxl-detector 启用时（检测到 SD 风格图片）：**
- 追加 SDXL 专项分数，权重 0.15（总权重归一化）

---

## 四、3D 资源检测方案

### 4.1 3D 资源 AI 生成特征

AI 生成的 3D 模型（Meshy、Tripo、Point-E 等）通常有以下特征：

| 特征 | 检测方法 |
|------|----------|
| 网格拓扑混乱 | 面数异常、非流形面、T 型顶点过多 |
| UV 展开质量差 | UV 岛碎片化、拉伸严重 |
| 顶点密度不均匀 | 局部过密或过疏 |
| 纹理质量不匹配 | 渲染截图后走图片检测流水线 |
| 文件元数据 | 含 Meshy/Tripo/PointE 等标记 |

### 4.2 工具链

```
FBX/OBJ/GLB 文件
      │
      ├──→ [Blender headless] 渲染多角度截图（6 视角）
      │         └──→ 截图进入图片检测流水线
      │
      ├──→ [Trimesh] 网格质量分析
      │         ├── 非流形面数量
      │         ├── 退化面(degenerate faces)数量
      │         ├── 顶点密度方差
      │         └── watertight 检查
      │
      └──→ [Open3D] 拓扑分析
                ├── 连通组件数量
                ├── 法线一致性
                └── 边界边检查
```

### 4.3 Blender 渲染脚本

```python
# blender_render.py - Blender headless 多角度渲染
import bpy
import sys
import math
import os

def render_views(input_path, output_dir, views=6):
    """渲染 3D 模型的多角度截图"""
    bpy.ops.wm.read_factory_settings(use_empty=True)

    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=input_path)
    elif ext == ".obj":
        bpy.ops.import_scene.obj(filepath=input_path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=input_path)

    # 设置渲染参数
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 32

    # 计算包围盒中心
    objects = [o for o in bpy.data.objects if o.type == 'MESH']
    if not objects:
        return []

    # 多角度渲染
    angles = [(0, 0), (90, 0), (180, 0), (270, 0), (0, 45), (0, -45)]
    output_files = []

    for i, (azimuth, elevation) in enumerate(angles[:views]):
        # 设置相机位置
        rad_az = math.radians(azimuth)
        rad_el = math.radians(elevation)
        dist = 3.0
        x = dist * math.cos(rad_el) * math.cos(rad_az)
        y = dist * math.cos(rad_el) * math.sin(rad_az)
        z = dist * math.sin(rad_el)

        cam = bpy.data.objects.get("Camera") or bpy.data.cameras.new("Camera")
        cam_obj = bpy.data.objects.new("Camera", cam) if not bpy.data.objects.get("Camera") else bpy.data.objects["Camera"]
        cam_obj.location = (x, y, z)

        output_path = os.path.join(output_dir, f"view_{i:02d}.png")
        bpy.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        output_files.append(output_path)

    return output_files

if __name__ == "__main__":
    input_file = sys.argv[sys.argv.index("--") + 1]
    output_dir = sys.argv[sys.argv.index("--") + 2]
    render_views(input_file, output_dir)
```

---

## 五、项目结构

```
f:/ainoai/
├── docs/
│   └── AI美术资源离线检测流水线方案.md    # 本文档
├── src/
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── file_scanner.py          # 文件扫描（目录/git diff）
│   │   └── format_detector.py       # 文件格式嗅探（避免伪造扩展名）
│   ├── metadata/
│   │   ├── __init__.py
│   │   ├── exif_analyzer.py         # ExifTool 封装
│   │   ├── png_chunks.py            # PNG tEXt/iTXt 解析
│   │   ├── c2pa_checker.py          # c2patool 封装
│   │   ├── xmp_parser.py            # XMP AI 字段检测
│   │   └── signatures.py            # AI 工具签名库
│   ├── forensics/
│   │   ├── __init__.py
│   │   ├── ela.py                   # Error Level Analysis
│   │   ├── frequency.py             # 频率域分析 (FFT/DCT)
│   │   ├── noise.py                 # 噪声一致性分析
│   │   ├── color_stats.py           # 色彩统计分析
│   │   └── jpeg_forensics.py        # JPEG 量化表/伪影分析
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                  # 模型基类接口
│   │   ├── community_forensics.py   # Community-Forensics 推理
│   │   ├── universal_fake.py        # UniversalFakeDetect 推理
│   │   ├── npr_detect.py            # NPR 推理
│   │   ├── sdxl_detector.py         # Organika/sdxl-detector 推理
│   │   └── ensemble.py             # 多模型集成投票
│   ├── threed/
│   │   ├── __init__.py
│   │   ├── blender_render.py        # Blender headless 渲染
│   │   ├── mesh_analysis.py         # Trimesh 网格分析
│   │   └── topology.py             # Open3D 拓扑分析
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── pipeline.py             # 三层检测流水线编排
│   │   └── scorer.py              # 综合评分逻辑
│   ├── report/
│   │   ├── __init__.py
│   │   ├── json_report.py          # JSON 报告生成
│   │   ├── markdown_report.py       # Markdown 报告生成
│   │   └── evidence.py            # 证据快照保存
│   └── audit/
│       ├── __init__.py
│       └── code_audit.py           # 代码审计联动
├── models/                          # 预下载的模型权重（.gitignore）
│   ├── community-forensics/
│   ├── universal-fake-detect/
│   ├── npr/
│   ├── sdxl-detector/
│   └── download_models.sh          # 一次性模型下载脚本（需联网）
├── config/
│   ├── config.yaml                  # 主配置文件
│   ├── signatures.yaml              # AI 签名库（可热更新）
│   └── thresholds.yaml              # 阈值配置
├── scripts/
│   ├── install.sh                   # 环境安装脚本
│   ├── download_models.sh           # 模型下载（唯一需要联网的步骤）
│   └── ci_hook.sh                   # CI 集成 hook 脚本
├── tests/
│   ├── test_assets/                 # 测试用图片
│   │   ├── ai_generated/           # 已知 AI 生成的图
│   │   └── human_created/          # 已知人工创作的图
│   ├── test_metadata.py
│   ├── test_forensics.py
│   ├── test_models.py
│   └── test_pipeline.py
├── cli.py                           # CLI 入口（Click/Typer）
├── requirements.txt
├── pyproject.toml
├── Dockerfile                       # 容器化部署
└── .gitignore
```

---

## 六、配置文件设计

### config/config.yaml

```yaml
# ============================================================
# AI 美术资源检测 - 主配置
# ============================================================

scan:
  extensions:
    image: [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tga", ".psd"]
    threed: [".fbx", ".obj", ".glb", ".gltf", ".blend"]
  mode: "directory"       # "directory" | "git-diff" | "file-list"
  path: "./assets"
  exclude_patterns:
    - "**/.git/**"
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "**/thumbnails/**"
  max_file_size_mb: 200   # 跳过超大文件
  parallel_workers: 4     # 并行工作线程数

# --- 第一层：元数据检测 ---
metadata:
  enabled: true
  tools:
    exiftool_path: "exiftool"        # ExifTool CLI 路径
    c2patool_path: "c2patool"        # c2patool CLI 路径
  check_exif: true
  check_png_chunks: true
  check_xmp: true
  check_c2pa: true
  check_iptc: true
  signatures_file: "./config/signatures.yaml"

# --- 第二层：像素取证 ---
forensics:
  enabled: true
  ela:
    enabled: true
    quality: 90
    uniformity_threshold: 0.75       # 高于此值视为异常
  frequency:
    enabled: true
    method: "fft"                    # "fft" | "dct"
  noise:
    enabled: true
    block_size: 64
  color_stats:
    enabled: true

# --- 第三层：模型推理 ---
models:
  enabled: true
  device: "cuda"                     # "cuda" | "cpu"
  batch_size: 8                      # GPU 批量推理
  input_size: 224

  community_forensics:
    enabled: true
    weight: 0.45
    weights_path: "./models/community-forensics/model.pth"

  universal_fake_detect:
    enabled: true
    weight: 0.35
    weights_path: "./models/universal-fake-detect/model.pth"
    backbone: "clip_vitl14"

  npr:
    enabled: true
    weight: 0.20
    weights_path: "./models/npr/model.pth"

  sdxl_detector:
    enabled: false                   # 按需启用
    weight: 0.15
    weights_path: "./models/sdxl-detector/"

# --- 3D 资源检测 ---
threed:
  enabled: true
  blender_path: "blender"            # Blender 可执行文件路径
  render_views: 6                    # 渲染视角数
  render_resolution: 512
  mesh_analysis:
    max_non_manifold_ratio: 0.05     # 非流形面占比阈值
    min_vertex_density_cv: 0.8       # 顶点密度变异系数阈值

# --- 流水线策略 ---
pipeline:
  # 短路策略：元数据命中直接标记，不走后续层
  metadata_shortcircuit: true
  # 模型置信度高时跳过低优先级模型
  skip_ensemble_if_confident: true
  confidence_threshold: 0.85
  # 灰色地带需要多模型确认
  gray_zone: [0.4, 0.7]

# --- 报告输出 ---
report:
  format: ["json", "markdown"]       # 输出格式
  output_dir: "./ai-detection-reports"
  include_evidence: true             # 保留 ELA 截图等证据
  evidence_dir: "./ai-detection-reports/evidence"

# --- 阈值 ---
thresholds:
  flag_score: 0.6                    # >= 标记为"疑似AI"
  high_confidence_score: 0.85        # >= 标记为"高度疑似AI"
```

---

## 七、CLI 接口设计

```bash
# ============ 基础扫描 ============

# 扫描目录（完整三层检测）
python cli.py scan ./assets/textures

# 扫描 git 变更（CI 最常用模式）
python cli.py scan --mode git-diff --base main --head HEAD

# 扫描文件列表
python cli.py scan --mode file-list --input changed_files.txt

# ============ 层级控制 ============

# 仅第一层：元数据检测（最快，<1s 扫完数百文件）
python cli.py scan --layer metadata ./assets

# 前两层：元数据 + 像素取证（中等速度）
python cli.py scan --layer forensics ./assets

# 全部三层（最慢但最准）
python cli.py scan --layer full ./assets

# 跳过模型推理（无 GPU 环境）
python cli.py scan --no-model ./assets

# ============ 3D 资源 ============

# 扫描 3D 资源
python cli.py scan-3d ./assets/models

# ============ 配置与模型管理 ============

# 使用指定配置
python cli.py scan --config ./config/config.yaml ./assets

# 查看模型状态
python cli.py model status

# 验证环境（检查所有工具是否就绪）
python cli.py doctor

# ============ 报告 ============

# 输出 JSON 报告
python cli.py scan --format json --output report.json ./assets

# 输出 Markdown 报告（人工审阅）
python cli.py scan --format markdown --output report.md ./assets

# ============ CI 集成 ============

# CI 模式（非零退出码表示有标记文件）
python cli.py scan --ci --mode git-diff --base origin/main
# 退出码: 0=无异常, 1=有疑似AI, 2=有高置信AI, 3=检测错误
```

---

## 八、报告输出格式

### 8.1 JSON 报告

```json
{
  "version": "1.0",
  "scan_time": "2026-05-25T22:30:00+08:00",
  "scan_mode": "git-diff",
  "base_ref": "main",
  "environment": {
    "hostname": "ci-runner-01",
    "gpu": "NVIDIA RTX 4090",
    "models_loaded": ["community-forensics", "universal-fake-detect", "npr"]
  },
  "summary": {
    "total_files_scanned": 45,
    "images_scanned": 38,
    "threed_scanned": 7,
    "flagged_suspicious": 3,
    "flagged_high_confidence": 1,
    "clean": 41
  },
  "results": [
    {
      "file": "assets/character/hero_portrait.png",
      "file_size": 2457600,
      "file_hash_sha256": "a1b2c3...",
      "detection_layers": {
        "metadata": {
          "score": 1.0,
          "signals": [
            "PNG tEXt 'parameters': Steps: 20, Sampler: Euler a, CFG: 7, Seed: 1234567890",
            "PNG tEXt 'prompt': masterpiece, best quality, 1girl..."
          ],
          "tool_detected": "Stable Diffusion (AUTOMATIC1111)"
        },
        "forensics": null,
        "model": null
      },
      "final_score": 1.0,
      "verdict": "high_confidence_ai",
      "verdict_reason": "元数据包含完整 Stable Diffusion 生成参数",
      "short_circuited_at": "metadata"
    },
    {
      "file": "assets/ui/banner_event.jpg",
      "file_size": 856320,
      "file_hash_sha256": "d4e5f6...",
      "detection_layers": {
        "metadata": {
          "score": 0.0,
          "signals": []
        },
        "forensics": {
          "ela_uniformity": 0.82,
          "frequency_anomaly": 0.65,
          "noise_consistency": 0.71,
          "combined_score": 0.68
        },
        "model": {
          "community_forensics": 0.78,
          "universal_fake_detect": 0.72,
          "npr": 0.65,
          "ensemble_score": 0.73
        }
      },
      "final_score": 0.73,
      "verdict": "suspicious",
      "verdict_reason": "像素取证和模型推理均指向 AI 生成",
      "evidence_files": [
        "evidence/banner_event_ela.png",
        "evidence/banner_event_fft.png"
      ]
    }
  ]
}
```

### 8.2 Markdown 报告（人工审阅用）

```markdown
# AI 美术资源检测报告

**扫描时间**: 2026-05-25 22:30:00
**扫描模式**: git-diff (main → HEAD)
**运行环境**: ci-runner-01 (GPU: RTX 4090)

## 摘要

| 类别 | 数量 |
|------|------|
| 扫描文件总数 | 45 |
| 高度疑似 AI | 1 |
| 疑似 AI（需复审） | 3 |
| 未检出 | 41 |

---

## 需要人工复审的文件

### [高危] assets/character/hero_portrait.png
- **综合评分**: 1.00 (高度疑似 AI)
- **检出层**: 元数据
- **原因**: 包含完整 Stable Diffusion 生成参数
- **详情**:
  - 工具: AUTOMATIC1111 (Stable Diffusion)
  - Prompt: "masterpiece, best quality, 1girl..."
  - 参数: Steps=20, Sampler=Euler a, CFG=7

### [中危] assets/ui/banner_event.jpg
- **综合评分**: 0.73 (疑似 AI)
- **检出层**: 像素取证 + 模型推理
- **原因**: ELA 均匀度异常 + 模型集成判定
- **证据**: [ELA 分析图](evidence/banner_event_ela.png) | [频谱图](evidence/banner_event_fft.png)
```

---

## 九、部署步骤

### 9.1 环境要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| OS | Linux / Windows / macOS | Ubuntu 22.04+ |
| Python | 3.10+ | 3.11 |
| GPU | 无（CPU 可运行，慢 5-10x） | NVIDIA RTX 3060 12GB+ |
| RAM | 8GB | 16GB+ |
| 磁盘 | 10GB（模型+工具） | SSD 50GB+ |
| ExifTool | 12.0+ | 最新版 |
| Blender | 3.6+（仅 3D 检测需要） | 4.0+ |

### 9.2 安装步骤

```bash
# ============ 步骤 1: 基础环境 ============

# 创建项目目录
mkdir -p /opt/ainoai && cd /opt/ainoai
git clone <repo-url> .

# 创建 Python 虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# ============ 步骤 2: 安装外部工具 ============

# ExifTool (Linux)
sudo apt-get install libimage-exiftool-perl
# ExifTool (macOS)
# brew install exiftool
# ExifTool (Windows)
# 下载 https://exiftool.org/ 放入 PATH

# c2patool (Rust CLI)
# 从 https://github.com/contentauth/c2patool/releases 下载预编译包
curl -L https://github.com/contentauth/c2patool/releases/latest/download/c2patool-linux-x64.tar.gz | tar xz
sudo mv c2patool /usr/local/bin/

# Blender (仅 3D 检测需要)
sudo snap install blender --classic
# 或从 https://www.blender.org/download/ 下载

# ============ 步骤 3: 下载模型权重（唯一需要联网的步骤） ============

# 此脚本下载所有预训练模型，之后即可断网运行
bash scripts/download_models.sh

# ============ 步骤 4: 验证安装 ============

# 检查所有组件是否就绪
python cli.py doctor

# 预期输出：
# [✓] Python 3.11.x
# [✓] PyTorch 2.x (CUDA available: True, Device: RTX 4090)
# [✓] ExifTool 12.x
# [✓] c2patool 0.x.x
# [✓] Blender 4.x
# [✓] Model: community-forensics (loaded)
# [✓] Model: universal-fake-detect (loaded)
# [✓] Model: npr (loaded)
# [✓] Model: sdxl-detector (loaded)
# All systems ready. Network: DISCONNECTED (as expected)

# ============ 步骤 5: 断网测试 ============

# 断开网络后运行测试
python cli.py scan ./tests/test_assets/
# 确认所有功能正常
```

### 9.3 模型下载脚本 (scripts/download_models.sh)

```bash
#!/bin/bash
set -e

MODEL_DIR="./models"
mkdir -p "$MODEL_DIR"

echo "=== 下载 AI 检测模型权重 ==="
echo "注意：这是唯一需要联网的步骤"
echo ""

# 1. Community-Forensics
echo "[1/4] 下载 Community-Forensics..."
git clone https://github.com/mever-team/community-forensics.git "$MODEL_DIR/community-forensics-repo" --depth 1
# 下载预训练权重（根据实际 release 地址）
# wget -O "$MODEL_DIR/community-forensics/model.pth" <model_url>

# 2. UniversalFakeDetect
echo "[2/4] 下载 UniversalFakeDetect..."
git clone https://github.com/Yuheng-Li/UniversalFakeDetect.git "$MODEL_DIR/universal-fake-detect-repo" --depth 1
# 下载 CLIP ViT-L/14 权重
pip download clip-openai -d "$MODEL_DIR/clip-cache" --no-deps

# 3. NPR
echo "[3/4] 下载 NPR..."
git clone https://github.com/chuangchuangtan/NPR-DeepfakeDetection.git "$MODEL_DIR/npr-repo" --depth 1

# 4. Organika/sdxl-detector
echo "[4/4] 下载 Organika/sdxl-detector..."
python -c "
from huggingface_hub import snapshot_download
snapshot_download('Organika/sdxl-detector', local_dir='$MODEL_DIR/sdxl-detector')
"

echo ""
echo "=== 所有模型下载完成 ==="
echo "现在可以断开网络，工具将完全离线运行。"
```

### 9.4 Docker 部署

```dockerfile
FROM nvidia/cuda:12.4-runtime-ubuntu22.04

# 基础依赖
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    libimage-exiftool-perl \
    blender \
    && rm -rf /var/lib/apt/lists/*

# 安装 c2patool
COPY --from=c2patool-builder /usr/local/bin/c2patool /usr/local/bin/

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码和预下载的模型
COPY src/ ./src/
COPY config/ ./config/
COPY models/ ./models/
COPY cli.py .

# 断网验证
# 容器运行时不需要网络访问
ENTRYPOINT ["python", "cli.py"]
CMD ["scan", "--help"]
```

---

## 十、CI 集成

### 10.1 Git Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit (或通过 pre-commit 框架)

# 获取暂存的图片文件
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -iE '\.(png|jpg|jpeg|webp|tga|psd|fbx|obj|glb)$')

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

echo "🔍 AI 美术资源检测中..."

# 将文件列表传入检测器
echo "$STAGED_FILES" > /tmp/staged_art_files.txt
RESULT=$(python /opt/ainoai/cli.py scan --mode file-list --input /tmp/staged_art_files.txt --ci --format json 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
    echo "❌ 检测到高置信度 AI 生成资源，提交已拦截："
    echo "$RESULT" | python -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('results', []):
    if r['verdict'] == 'high_confidence_ai':
        print(f'  - {r[\"file\"]}: {r[\"verdict_reason\"]}')
"
    echo ""
    echo "如确认为误报，使用 git commit --no-verify 绕过"
    exit 1
elif [ $EXIT_CODE -eq 1 ]; then
    echo "⚠️  检测到疑似 AI 生成资源（需人工复审）："
    echo "$RESULT" | python -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('results', []):
    if r['verdict'] == 'suspicious':
        print(f'  - {r[\"file\"]} (score: {r[\"final_score\"]:.2f})')
"
    echo ""
    echo "提交将继续，但已生成复审报告。"
fi

exit 0
```

### 10.2 GitHub Actions Workflow

```yaml
name: AI Art Detection

on:
  pull_request:
    paths:
      - 'assets/**'
      - 'art/**'
      - 'textures/**'

jobs:
  ai-detection:
    runs-on: [self-hosted, gpu]  # 需要自托管 runner（确保离线）
    container:
      image: your-registry/ainoai:latest
      options: --gpus all --network none  # 关键：--network none 确保离线

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect AI-generated assets
        run: |
          python cli.py scan \
            --mode git-diff \
            --base ${{ github.event.pull_request.base.sha }} \
            --head ${{ github.event.pull_request.head.sha }} \
            --ci \
            --format json \
            --output /tmp/ai-report.json

      - name: Process results
        if: always()
        run: |
          python cli.py report \
            --input /tmp/ai-report.json \
            --format markdown \
            --output /tmp/ai-report.md

      - name: Comment on PR
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('/tmp/ai-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });
```

### 10.3 GitLab CI

```yaml
ai-art-detection:
  stage: test
  image: your-registry/ainoai:latest
  tags:
    - gpu
    - no-internet  # 自定义 tag，确保 runner 无外网
  variables:
    NVIDIA_VISIBLE_DEVICES: all
  rules:
    - changes:
        - "assets/**"
        - "art/**"
  script:
    - python cli.py scan
        --mode git-diff
        --base $CI_MERGE_REQUEST_TARGET_BRANCH_SHA
        --head $CI_COMMIT_SHA
        --ci
        --output ai-report.json
  artifacts:
    paths:
      - ai-report.json
      - ai-detection-reports/
    when: always
```

---

## 十一、代码审计联动

### 11.1 审计点

AI 资源检测不仅需要检查资源本身，还需要审计相关代码确保：

| 审计点 | 说明 | 检查方法 |
|--------|------|----------|
| 资源引用一致性 | 代码中引用的资源文件是否都经过检测 | 扫描代码中的资源路径引用 |
| 绕过检测代码 | 是否有代码试图绕过检测流程 | grep 关键词：no-verify, skip-check |
| 资源来源声明 | 代码/配置是否声明了资源来源 | 检查 ATTRIBUTION 或 LICENSE 文件 |
| 模型完整性 | 检测模型文件是否被篡改 | SHA256 校验 |
| 配置篡改 | 检测阈值是否被恶意调低 | 配置文件 git diff + 基线对比 |

### 11.2 代码审计脚本

```python
# src/audit/code_audit.py

"""
代码审计模块 - 联动检测
确保 AI 检测流程不被绕过，资源引用与检测结果一致
"""

import re
import hashlib
from pathlib import Path
from typing import List, Dict

class CodeAuditor:
    # 可疑的绕过模式
    BYPASS_PATTERNS = [
        r"--no-verify",
        r"skip[_-]?ai[_-]?check",
        r"SKIP_AI_DETECTION",
        r"ai[_-]?whitelist",
        r"force[_-]?commit",
        r"disable[_-]?scan",
    ]

    # 资源引用模式（按项目实际情况扩展）
    ASSET_REF_PATTERNS = [
        r'["\']assets/[^"\']+\.(png|jpg|jpeg|webp|tga|psd)["\']',
        r'["\']textures/[^"\']+\.(png|jpg|jpeg|webp|tga)["\']',
        r'["\']models/[^"\']+\.(fbx|obj|glb|gltf)["\']',
        r'Resources\.Load\(["\'][^"\']+["\']\)',          # Unity
        r'AssetDatabase\.LoadAssetAtPath',                 # Unity Editor
        r'UE_LOG.*Asset.*Load',                           # Unreal
    ]

    def __init__(self, project_root: str):
        self.root = Path(project_root)

    def audit_bypass_attempts(self) -> List[Dict]:
        """检查是否有代码试图绕过 AI 检测"""
        findings = []
        code_files = self.root.rglob("*.py")  # 扩展到其他语言

        for f in code_files:
            if ".venv" in str(f) or "node_modules" in str(f):
                continue
            content = f.read_text(errors="ignore")
            for pattern in self.BYPASS_PATTERNS:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for m in matches:
                    line_num = content[:m.start()].count("\n") + 1
                    findings.append({
                        "file": str(f.relative_to(self.root)),
                        "line": line_num,
                        "pattern": pattern,
                        "match": m.group(),
                        "severity": "high",
                        "message": f"疑似 AI 检测绕过代码: {m.group()}"
                    })
        return findings

    def audit_asset_references(self, detection_results: Dict) -> List[Dict]:
        """检查代码引用的资源是否都经过了检测"""
        findings = []
        scanned_files = {r["file"] for r in detection_results.get("results", [])}

        for f in self.root.rglob("*"):
            if f.suffix not in (".cs", ".cpp", ".py", ".js", ".ts", ".gd"):
                continue
            content = f.read_text(errors="ignore")
            for pattern in self.ASSET_REF_PATTERNS:
                for m in re.finditer(pattern, content):
                    ref_path = m.group().strip("\"'")
                    if ref_path not in scanned_files:
                        findings.append({
                            "file": str(f.relative_to(self.root)),
                            "referenced_asset": ref_path,
                            "severity": "medium",
                            "message": f"资源 {ref_path} 被代码引用但未经过 AI 检测"
                        })
        return findings

    def audit_model_integrity(self, models_dir: str, expected_hashes: Dict[str, str]) -> List[Dict]:
        """验证检测模型文件完整性（防止被替换为空操作模型）"""
        findings = []
        models_path = Path(models_dir)

        for model_name, expected_hash in expected_hashes.items():
            model_file = models_path / model_name
            if not model_file.exists():
                findings.append({
                    "model": model_name,
                    "severity": "critical",
                    "message": f"模型文件缺失: {model_name}"
                })
                continue

            actual_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                findings.append({
                    "model": model_name,
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                    "severity": "critical",
                    "message": f"模型文件哈希不匹配（可能被篡改）: {model_name}"
                })
        return findings

    def audit_config_changes(self, config_path: str, baseline_path: str) -> List[Dict]:
        """检查配置阈值是否被恶意调低"""
        import yaml

        findings = []
        with open(config_path) as f:
            current = yaml.safe_load(f)
        with open(baseline_path) as f:
            baseline = yaml.safe_load(f)

        # 检查关键阈值
        critical_thresholds = [
            ("thresholds.flag_score", 0.4),        # 不应低于此值
            ("thresholds.high_confidence_score", 0.7),
        ]

        current_thresholds = current.get("thresholds", {})
        baseline_thresholds = baseline.get("thresholds", {})

        for key, min_value in critical_thresholds:
            field = key.split(".")[-1]
            current_val = current_thresholds.get(field, 0)
            baseline_val = baseline_thresholds.get(field, 0)

            if current_val < min_value:
                findings.append({
                    "config_key": key,
                    "current_value": current_val,
                    "minimum_allowed": min_value,
                    "severity": "high",
                    "message": f"阈值 {key} 被设置为 {current_val}，低于安全下限 {min_value}"
                })
            elif current_val < baseline_val - 0.1:
                findings.append({
                    "config_key": key,
                    "current_value": current_val,
                    "baseline_value": baseline_val,
                    "severity": "medium",
                    "message": f"阈值 {key} 从 {baseline_val} 降低到 {current_val}"
                })

        # 检查是否有层被禁用
        for layer in ["metadata", "forensics", "models"]:
            if not current.get(layer, {}).get("enabled", True):
                if baseline.get(layer, {}).get("enabled", True):
                    findings.append({
                        "config_key": f"{layer}.enabled",
                        "severity": "high",
                        "message": f"检测层 '{layer}' 已被禁用（基线配置中为启用）"
                    })

        return findings
```

### 11.3 审计集成到 CI

```yaml
# 在 AI 检测 job 之后添加审计 job
ai-audit:
  stage: audit
  needs: [ai-detection]
  script:
    - python cli.py audit
        --check bypass
        --check references
        --check model-integrity
        --check config-drift
        --baseline config/config.baseline.yaml
        --output audit-report.json
  artifacts:
    paths:
      - audit-report.json
```

---

## 十二、性能估算

### 12.1 单文件检测耗时（RTX 4090）

| 层 | 耗时/文件 | 说明 |
|----|-----------|------|
| 元数据分析 | < 5ms | ExifTool + 自定义解析 |
| 像素取证 | ~100-200ms | ELA + FFT + 噪声分析 |
| NPR 模型 | ~50ms | 轻量快速 |
| Community-Forensics | ~300ms | 主模型 |
| UniversalFakeDetect | ~200ms | CLIP 特征提取 |
| **完整流水线** | **~500-800ms** | 含短路优化 |

### 12.2 批量扫描吞吐量

| 场景 | 文件数 | GPU | 预计耗时 |
|------|--------|-----|----------|
| 日常提交（5-20 图片） | 20 | RTX 3060 | < 30s |
| 版本发布全扫描 | 500 | RTX 4090 | ~5min |
| 大型项目全扫描 | 5000 | RTX 4090 x2 | ~30min |

### 12.3 短路优化效果

实际场景中，约 10-20% 的 AI 图片在元数据层即可命中（保留了生成参数），无需走后续层。剩余文件中，如果模型高置信度命中（>0.85），也无需多模型交叉验证。预估实际平均耗时为理论值的 60-70%。

---

## 十三、维护与更新

### 13.1 签名库更新

```yaml
# config/signatures.yaml 定期更新
# 新增 AI 工具出现时，添加其软件签名
update_frequency: "每月一次或有新工具发布时"
update_method: "手动维护，通过 git pull 分发"
```

### 13.2 模型更新

当新的生成模型出现时，检测准确率可能下降。建议：

1. **季度评估**：用最新 AI 工具生成测试图片，评估检测率
2. **模型替换**：当社区发布更新的检测模型时，更新权重文件
3. **签名补充**：新 AI 工具的元数据特征加入签名库（最快、最有效）

### 13.3 误报处理

```yaml
# config/whitelist.yaml - 已确认的误报文件
whitelist:
  - file: "assets/ui/hand_painted_banner.jpg"
    reason: "人工绘制，模型误判。审核人：张三，2026-05-25"
    approved_by: "art-lead"
    date: "2026-05-25"
```

---

## 十四、风险与局限

| 风险 | 缓解措施 |
|------|----------|
| 元数据被清除 | 第二、三层兜底（像素分析 + 模型检测） |
| 新 AI 模型的图片未被训练过 | 定期更新模型；Community-Forensics 泛化性最强 |
| 误报（人工高质量图被标记） | 设置白名单机制 + 人工复审流程 |
| 漏报（精心处理的 AI 图） | 多层 + 多模型投票降低风险 |
| GPU 不可用 | 退化为 CPU 模式（慢但可用）+ 元数据层无需 GPU |
| 3D AI 检测不成熟 | 依赖渲染截图 → 走图片检测；网格分析作为辅助 |

---

## 十五、总结

本方案实现了一套**完全离线**的 AI 美术资源检测流水线：

1. **三层递进检测**：元数据（快/确定性高）→ 像素取证（中速/辅助判断）→ 模型推理（慢/最准）
2. **多模型集成投票**：Community-Forensics + UniversalFakeDetect + NPR 三模型交叉验证
3. **零网络依赖**：运行时完全离线，模型权重预先部署
4. **CI 深度集成**：支持 Git Hook / GitHub Actions / GitLab CI
5. **代码审计联动**：防止检测流程被绕过或配置被篡改
6. **3D 资源覆盖**：Blender 渲染 + 网格分析
7. **可审计可追溯**：JSON 报告 + 证据快照 + 完整审计日志
