# AI 美术资源离线检测流水线方案（最终版）

> **v1.0 | 2026-05-26**
>
> 本方案合并自工程实现方案与安全基线方案，以完整工程设计为主体，强制合入保密安全要求。

---

## 一、核心原则

本方案面向保密游戏美术资源审核，**第一优先级是防泄密**。

| # | 硬性约束 |
|---|----------|
| 1 | **不使用任何在线检测 API** |
| 2 | **不上传资源到第三方平台** |
| 3 | **不调用云端模型** |
| 4 | **不让工具运行时联网** |
| 5 | 所有模型、依赖、报告、日志均在本机或内网保存 |
| 6 | 输入资源默认只读，检测过程不得覆盖原始文件 |
| 7 | 检测到联网能力时程序必须拒绝启动 |

---

## 二、检测流水线总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   AI 美术资源离线检测流水线                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  输入目录                                                               │
│    ↓                                                                    │
│  ┌──────────────────────┐                                              │
│  │ 安全预扫描            │                                              │
│  │ · 禁止软链接逃逸      │                                              │
│  │ · 文件大小限制        │                                              │
│  │ · 格式白名单          │                                              │
│  │ · SHA256 记录         │                                              │
│  │ · magic bytes 验真    │                                              │
│  └──────────┬───────────┘                                              │
│             ↓                                                           │
│  ┌──────────────────────┐                                              │
│  │ 第一层：证据链扫描    │  ExifTool + c2patool + PNG chunks + XMP      │
│  └──────────┬───────────┘                                              │
│             │                                                           │
│     命中 AI 签名 ←───────┘───────→ 未命中                               │
│         │                              │                                │
│         ↓                              ↓                                │
│  Confirmed AI               ┌──────────────────────┐                   │
│                             │ 第二层：像素取证(辅助) │                   │
│                             │ ELA/FFT/噪声(仅佐证)  │                   │
│                             └──────────┬───────────┘                   │
│                                        ↓                                │
│                             ┌──────────────────────┐                   │
│                             │ 第三层：模型推理       │                   │
│                             │ CF(主) + UFD(辅) + NPR │                   │
│                             └──────────┬───────────┘                   │
│                                        ↓                                │
│                             ┌──────────────────────┐                   │
│                             │ 风险融合 → 5级分级    │                   │
│                             └──────────┬───────────┘                   │
│                                        ↓                                │
│                             ┌──────────────────────┐                   │
│                             │ 代码审计联动          │                   │
│                             └──────────┬───────────┘                   │
│                                        ↓                                │
│                               输出离线报告 → 人工复核                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 三、检测目标

### 3.1 覆盖资源类型

| 类型 | 格式 | 处理方式 |
|------|------|----------|
| 图片资源 | png, jpg, jpeg, webp, bmp, tga, tif, tiff | 直接检测 |
| 3D 模型 | fbx, obj, glb, gltf, blend | 贴图提取 + 渲染截图 → 图片检测 |
| 设计/矢量 | svg, pdf | 元数据解析 + 本地渲染成图片 |
| 后续扩展 | psd, psb, ai, eps, heic, avif | 第二阶段 |

### 3.2 输出结果

- JSON 结构化报告
- CSV 汇总表
- Markdown 人工审阅报告
- HTML 离线报告（可选）
- 5 级风险等级
- 证据链记录（ELA 截图、频谱图等）
- 人工复核清单
- 代码审计报告

---

## 四、工具链选型

### 4.1 最终工具选型

| 工具 | 职责 | 联网需求 | 许可证 | 备注 |
|------|------|----------|--------|------|
| **ExifTool** | EXIF/XMP/IPTC/ICC 元数据提取 | 不联网 | GPL/Artistic | 必须 |
| **c2patool** | C2PA 内容凭证验证 | 不联网 | Apache-2.0 | 必须 |
| **Pillow + OpenCV** | 图片解码、预处理、辅助取证 | 不联网 | PIL/Apache | 必须 |
| **Community-Forensics** | 主 AI 图片检测模型 | 不联网 | MIT | **必须 - 主模型** |
| **UniversalFakeDetect** | CLIP 特征 AI 检测 | 不联网 | MIT | 建议 - 辅助模型 |
| **NPR** | 相邻像素关系检测 | 不联网 | Apache-2.0 | 建议 - 快筛模型 |
| **Organika/sdxl-detector** | SD/SDXL 专项检测 | 不联网 | **cc-by-nc-3.0** | 条件使用，**非商用许可** |
| **PhotoHolmes** | 图像取证框架 | 不联网 | MIT | 辅助取证 |
| **Blender headless** | FBX/OBJ/GLB 渲染 + 贴图提取 | 不联网 | GPL | 3D 检测必须 |
| **Trimesh + Open3D** | 3D 网格拓扑/质量分析 | 不联网 | MIT/BSD | 3D 检测建议 |
| **Semgrep + Bandit** | 代码静态分析/安全审计 | 不联网 | MIT/Apache | 代码审计 |
| **python-magic** | 文件真实格式嗅探 | 不联网 | MIT | 防伪造扩展名 |

### 4.2 许可证风险说明

| 模型 | 许可证 | 商业内审风险 |
|------|--------|-------------|
| Community-Forensics | MIT | 无风险 |
| UniversalFakeDetect | MIT | 无风险 |
| NPR | Apache-2.0 | 无风险 |
| **Organika/sdxl-detector** | **cc-by-nc-3.0** | **仅限非商业/教育用途，商业内审需法务评估** |

**建议**：Organika/sdxl-detector 仅作为 SD/SDXL 专项复核使用，且标注许可证限制。如法务不允许，可剔除此模型，不影响主流程。

### 4.3 模型对比与定位

| 模型 | 定位 | 泛化能力 | 推理速度 | 模型大小 |
|------|------|----------|----------|----------|
| **Community-Forensics** | **主模型** | ★★★★★ | ~300ms/张 | ~1GB |
| **UniversalFakeDetect** | 辅助交叉验证 | ★★★★★ | ~200ms/张 | ~400MB |
| **NPR** | 快速预筛 | ★★★★ | ~50ms/张 | ~50MB |
| Organika/sdxl-detector | SD/SDXL 专项 | ★★★ | ~150ms/张 | ~350MB |

### 4.4 第二阶段预留模型

| 模型 | 用途 | 开源可用性 |
|------|------|-----------|
| RA-Det | 未知生成器泛化检测 | **待确认**（未找到明确公开仓库） |
| SPAI | 抗压缩/裁剪鲁棒检测 | **待确认** |
| HEDGE | 抗后处理检测增强 | **待确认** |
| CNNDetection | 经典 GAN 检测 baseline | 可用（github.com/peterwang512/CNNDetection） |

> 注：RA-Det/SPAI/HEDGE 在第二阶段接入前需确认开源仓库地址和许可证。

### 4.5 淘汰方案

| 方案 | 淘汰原因 |
|------|----------|
| DIRE | 推理太慢（需扩散重建），不适合 CI 批量 |
| DRCT | 同理，依赖扩散重建 |
| 所有在线 API | 违反离线原则 |
| Go + ONNX Runtime | Python 模型生态更成熟 |

---

## 五、风险等级体系

不使用简单的"AI/非AI"二分法，采用 **5 级分级**：

| 等级 | 含义 | 触发条件 |
|------|------|----------|
| **Confirmed AI** | 明确 AI 生成 | 元数据包含完整 AI 生成参数，或 C2PA 标记 AI |
| **Likely AI** | 极可能 AI | 主模型高风险(>0.85)且至少一个辅助模型支持 |
| **Suspicious** | 需人工复核 | 单模型高风险、或元数据异常、或取证指标异常 |
| **Likely Human** | 极可能人工 | 多模型低风险(<0.3)且无 AI 元数据证据 |
| **Inconclusive** | 无法判定 | 文件损坏、过度压缩、模型分歧大、信息不足 |

### 融合权重

**第一阶段权重（当前部署）：**

```
元数据明确 AI → 直接 Confirmed AI（短路）

否则进入模型推理：
Community-Forensics      0.55
UniversalFakeDetect      0.30
NPR                      0.15
```

**完整模型接入后（第二阶段）：**

```
Community-Forensics      0.35
RA-Det                   0.25
SPAI / HEDGE             0.20
UniversalFakeDetect      0.15
NPR                      0.05
```

**Organika/sdxl-detector**：不参与主权重投票，仅当图片被初步判定为 SD 风格时，追加专项分数作为佐证（不影响主判定）。

### 像素取证定位说明

ELA、频率域、噪声分析 **仅作为辅助佐证**，不作为强判定依据：
- 用于在模型分数处于灰色地带(0.4-0.7)时提供辅助信号
- 作为人工复审时的参考证据
- **不会单独触发 Likely AI 或更高等级判定**

---

## 六、检测策略详解

### 6.1 第一层：证据链扫描（耗时 < 5ms/文件）

**工具：ExifTool + c2patool + 自定义 PNG/XMP 解析**

| 检测项 | 方法 | AI 信号示例 |
|--------|------|-------------|
| 软件标识 | EXIF:Software | "Stable Diffusion", "ComfyUI", "AUTOMATIC1111" |
| 生成参数 | PNG tEXt chunks | "Steps: 20, Sampler: Euler, CFG: 7, Seed: 12345" |
| 提示词 | PNG/EXIF UserComment | "prompt:", "negative_prompt:", "Dream:" |
| AI 水印 | XMP/C2PA | ai:generatedWith, c2pa.ai_generated claim |
| 创建工具 | XMP:CreatorTool | "Midjourney", "DALL-E", "Adobe Firefly" |
| 数字凭证 | C2PA manifest | Content Credentials 中的 AI 生成声明 |
| EXIF 完整性 | EXIF 分析 | 正常相机照片有完整 EXIF，AI 图通常缺失 |
| 文件来源 | IPTC/XMP Source | 可疑 AI 平台来源标记 |

**AI 工具签名库（持续维护）：**

```python
AI_SOFTWARE_SIGNATURES = [
    # Stable Diffusion 生态
    "stable diffusion", "automatic1111", "a1111", "comfyui",
    "invoke ai", "invokeai", "diffusionbee", "draw things",
    "easy diffusion", "fooocus", "forge", "webui",
    # 商业 AI 工具
    "midjourney", "dall-e", "dalle", "openai",
    "adobe firefly", "imagen", "ideogram",
    "leonardo.ai", "playground ai", "nightcafe",
    # 中国 AI 工具
    "通义万相", "文心一格", "即梦", "liblib",
    "百度ai", "腾讯ai", "可图", "星流", "pixverse",
    # NovelAI / 动漫
    "novelai", "nai diffusion", "waifu diffusion",
    # 视频/3D AI
    "runway", "pika", "sora", "kling", "可灵",
    "meshy", "tripo", "point-e", "shap-e", "rodin",
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
    r"clip[\s_]skip:\s*\d+",
]
```

### 6.2 第二层：像素取证（辅助，耗时 ~100-200ms/文件）

**定位：辅助佐证层，不单独决定判定等级**

**工具：Pillow + OpenCV + PhotoHolmes**

| 分析方法 | 原理 | 辅助信号 |
|----------|------|----------|
| **ELA** | JPEG 重压缩差异 | AI 图 ELA 均匀度异常高 |
| **FFT 频域分析** | 频谱分布 | AI 图高频伪影/周期性模式 |
| **噪声一致性** | 噪声模式提取 | AI 图噪声过于均匀 |
| **色彩直方图** | 颜色分布统计 | AI 图色彩过于平滑 |
| **JPEG 量化表** | 量化矩阵检查 | AI 图缺少标准相机量化表 |

```python
def compute_ela(image_path, quality=90, scale=15):
    """ELA 分析 - 仅作辅助佐证"""
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
    ela_array = np.array(ela.convert("L"))
    uniformity = 1.0 - (ela_array.std() / ela_array.mean() if ela_array.mean() > 0 else 0)
    return ela, uniformity
```

### 6.3 第三层：深度学习模型推理（耗时 ~500ms-1.5s/文件）

**主模型 + 辅助模型投票：**

```
文件 ──→ NPR (快筛, ~50ms)
      ├──→ Community-Forensics (主模型, ~300ms)
      └──→ UniversalFakeDetect (辅助, ~200ms)
               │
               ↓
         加权投票 → 风险等级
               │
               ↓ (如检测到 SD 风格且 Organika 启用)
         Organika/sdxl-detector 专项复核（佐证）
```

**短路优化：**
- 元数据命中 → 直接 Confirmed AI，不走后续层
- 主模型 > 0.85 且辅助模型 > 0.75 → 直接 Likely AI，跳过其他
- 所有模型 < 0.3 → Likely Human

---

## 七、3D 资源检测方案

### 7.1 检测流程

```
FBX/OBJ/GLB 文件
  ↓
读取文件哈希、大小、创建时间
  ↓
Blender headless 导入
  ↓
提取信息：
  · mesh 数量、vertex/face 数
  · 材质数量、贴图路径
  · 外部引用、导出软件信息
  ↓
收集贴图（逐通道）：
  · basecolor / albedo / diffuse
  · normal
  · roughness / metallic
  · emissive
  ↓
贴图进入图片检测流水线
  ↓
自动渲染 6-12 张多角度视图
  ↓
渲染图进入图片检测流水线
  ↓
网格质量分析（Trimesh + Open3D）：
  · 非流形面占比
  · 退化面数量
  · 顶点密度方差
  · 连通组件数量
  · 法线一致性
  ↓
输出 3D 资产风险报告
```

### 7.2 AI 生成 3D 模型特征

| 特征 | 检测方法 | 说明 |
|------|----------|------|
| 网格拓扑混乱 | Trimesh 面分析 | AI 模型面数异常、非流形面过多 |
| UV 展开质量差 | Blender UV 检查 | UV 岛碎片化、拉伸严重 |
| 顶点密度不均匀 | Open3D 统计 | 局部过密或过疏 |
| 贴图风格异常 | 贴图 → 图片检测 | 贴图本身可能是 AI 生成 |
| 渲染效果异常 | 渲染图 → 图片检测 | 整体观感不自然 |
| 软件标记 | 文件元数据 | 含 Meshy/Tripo/PointE 等 |

### 7.3 Blender 渲染脚本

```python
# blender_render.py - 审核机上运行，Blender headless
import bpy, sys, math, os

def render_views(input_path, output_dir, views=6):
    bpy.ops.wm.read_factory_settings(use_empty=True)

    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=input_path)
    elif ext == ".obj":
        bpy.ops.import_scene.obj(filepath=input_path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=input_path)

    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 32

    objects = [o for o in bpy.data.objects if o.type == 'MESH']
    if not objects:
        return []

    angles = [(0,0),(90,0),(180,0),(270,0),(0,45),(0,-45),
              (45,30),(135,30),(225,30),(315,30),(0,90),(0,-90)]
    output_files = []

    for i, (azimuth, elevation) in enumerate(angles[:views]):
        rad_az, rad_el = math.radians(azimuth), math.radians(elevation)
        dist = 3.0
        x = dist * math.cos(rad_el) * math.cos(rad_az)
        y = dist * math.cos(rad_el) * math.sin(rad_az)
        z = dist * math.sin(rad_el)

        cam_obj = bpy.data.objects.get("Camera")
        if not cam_obj:
            cam_data = bpy.data.cameras.new("Camera")
            cam_obj = bpy.data.objects.new("Camera", cam_data)
            bpy.context.scene.collection.objects.link(cam_obj)
            bpy.context.scene.camera = cam_obj
        cam_obj.location = (x, y, z)

        output_path = os.path.join(output_dir, f"view_{i:02d}.png")
        bpy.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        output_files.append(output_path)

    return output_files

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    render_views(args[0], args[1], int(args[2]) if len(args) > 2 else 6)
```

---

## 八、安全架构：双机隔离

### 8.1 机器划分

```
┌─────────────────┐              ┌─────────────────────┐
│    下载机        │   离线介质    │      审核机          │
│  (可联网)        │ ──────────→ │  (禁止联网)          │
│                 │   USB/内网    │                     │
│ · 下载源码       │              │ · 处理保密资源       │
│ · 下载模型权重   │              │ · 运行检测程序       │
│ · 下载依赖 wheel │              │ · 生成报告          │
│ · 生成 hash 清单 │              │ · 断网验证          │
│ · 依赖安全审计   │              │ · 输入目录只读       │
└─────────────────┘              └─────────────────────┘
```

### 8.2 下载机操作（唯一联网步骤）

**准备离线包目录：**

```
ai_asset_audit_bundle/
├── source/                      # 项目源码
├── wheels/                      # Python wheel 包
├── models/                      # 模型权重
│   ├── community-forensics/
│   ├── universal-fake-detect/
│   ├── npr/
│   └── sdxl-detector/
├── tools/                       # ExifTool, c2patool, Blender 安装包
├── checksums/                   # 所有文件的 SHA256
│   ├── models.sha256
│   ├── tools.sha256
│   └── wheels.sha256
├── audit/                       # 依赖审计报告
│   ├── pip-audit-report.json
│   ├── bandit-report.json
│   └── trivy-report.json
└── docker/                      # Docker 镜像 tar（可选）
    └── ai-asset-audit-offline.tar
```

**下载脚本 (download_bundle.sh)：**

```bash
#!/bin/bash
set -e

BUNDLE="./ai_asset_audit_bundle"
mkdir -p "$BUNDLE"/{source,wheels,models,tools,checksums,audit}

echo "=== [1/6] 下载项目源码 ==="
git clone <repo-url> "$BUNDLE/source" --depth 1

echo "=== [2/6] 下载 Python 依赖 wheel ==="
pip download -r "$BUNDLE/source/requirements.txt" \
    -d "$BUNDLE/wheels" \
    --platform manylinux2014_x86_64 \
    --python-version 311

echo "=== [3/6] 下载模型权重 ==="
# Community-Forensics
git clone https://github.com/mever-team/community-forensics.git \
    "$BUNDLE/models/community-forensics" --depth 1

# UniversalFakeDetect
git clone https://github.com/Yuheng-Li/UniversalFakeDetect.git \
    "$BUNDLE/models/universal-fake-detect" --depth 1

# NPR
git clone https://github.com/chuangchuangtan/NPR-DeepfakeDetection.git \
    "$BUNDLE/models/npr" --depth 1

# Organika/sdxl-detector (注意: cc-by-nc-3.0 许可)
python -c "
from huggingface_hub import snapshot_download
snapshot_download('Organika/sdxl-detector',
                  local_dir='$BUNDLE/models/sdxl-detector')
"

echo "=== [4/6] 下载工具 ==="
# ExifTool
wget -O "$BUNDLE/tools/exiftool.tar.gz" \
    "https://exiftool.org/Image-ExifTool-12.87.tar.gz"

# c2patool
wget -O "$BUNDLE/tools/c2patool.tar.gz" \
    "https://github.com/contentauth/c2patool/releases/latest/download/c2patool-linux-x64.tar.gz"

# Blender LTS
wget -O "$BUNDLE/tools/blender.tar.xz" \
    "https://mirror.clarkson.edu/blender/release/Blender4.1/blender-4.1.1-linux-x64.tar.xz"

echo "=== [5/6] 生成校验文件 ==="
find "$BUNDLE/models" -type f -exec sha256sum {} \; > "$BUNDLE/checksums/models.sha256"
find "$BUNDLE/tools" -type f -exec sha256sum {} \; > "$BUNDLE/checksums/tools.sha256"
find "$BUNDLE/wheels" -type f -exec sha256sum {} \; > "$BUNDLE/checksums/wheels.sha256"

echo "=== [6/6] 依赖安全审计 ==="
pip-audit -r "$BUNDLE/source/requirements.txt" \
    --format json > "$BUNDLE/audit/pip-audit-report.json" || true
bandit -r "$BUNDLE/source/src" \
    -f json > "$BUNDLE/audit/bandit-report.json" || true

echo ""
echo "=== 离线包准备完成 ==="
echo "请将 $BUNDLE/ 拷贝到审核机"
```

### 8.3 审核机部署

**步骤 1：校验完整性**

```bash
# 校验所有文件 hash
cd /secure/ai_asset_audit_bundle
sha256sum -c checksums/models.sha256
sha256sum -c checksums/tools.sha256
sha256sum -c checksums/wheels.sha256
```

**步骤 2：安装环境（离线）**

```bash
# 创建虚拟环境
python3.11 -m venv /opt/ainoai/.venv
source /opt/ainoai/.venv/bin/activate

# 从本地 wheel 安装依赖（不联网）
pip install --no-index --find-links=/secure/ai_asset_audit_bundle/wheels \
    -r /secure/ai_asset_audit_bundle/source/requirements.txt

# 安装 ExifTool
tar xzf tools/exiftool.tar.gz -C /opt/ainoai/tools/
ln -s /opt/ainoai/tools/Image-ExifTool-*/exiftool /usr/local/bin/exiftool

# 安装 c2patool
tar xzf tools/c2patool.tar.gz -C /usr/local/bin/

# 安装 Blender
tar xJf tools/blender.tar.xz -C /opt/
ln -s /opt/blender-*/blender /usr/local/bin/blender
```

**步骤 3：设置离线环境变量**

```bash
# /etc/environment 或 .bashrc
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export NO_PROXY="*"
export AINOAI_OFFLINE=1
export AINOAI_MODELS_DIR="/secure/ai_asset_audit_bundle/models"
```

**步骤 4：阻断联网（三层控制）**

```bash
# 第一层：OS 防火墙
iptables -A OUTPUT -m owner --uid-owner ainoai -j DROP
# 或 Windows: New-NetFirewallRule 阻止 python.exe/blender.exe 出站

# 第二层：Docker 网络隔离（推荐）
docker run --rm --network none \
    --gpus all \
    -v /secure/input:/app/input:ro \
    -v /secure/reports:/app/reports \
    -v /secure/models:/app/models:ro \
    ai-asset-audit:offline scan /app/input

# 第三层：程序启动前自检（见运行时防泄密章节）
```

**步骤 5：验证安装**

```bash
python cli.py doctor

# 预期输出：
# [✓] Python 3.11.x
# [✓] PyTorch 2.x (CUDA: True, Device: RTX 4090)
# [✓] ExifTool 12.x
# [✓] c2patool 0.x.x
# [✓] Blender 4.x
# [✓] Model: community-forensics (loaded, hash OK)
# [✓] Model: universal-fake-detect (loaded, hash OK)
# [✓] Model: npr (loaded, hash OK)
# [✓] Model: sdxl-detector (loaded, hash OK)
# [✓] Network: UNREACHABLE (as expected)
# [✓] HF_HUB_OFFLINE=1
# [✓] TRANSFORMERS_OFFLINE=1
# [✓] Input directory: read-only
# ══════════════════════════════════
# All systems ready. Offline mode verified.
```

### 8.4 Docker 部署（推荐）

```dockerfile
FROM nvidia/cuda:12.4-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    perl \
    && rm -rf /var/lib/apt/lists/*

# 从离线包安装工具
COPY tools/exiftool /opt/exiftool
COPY tools/c2patool /usr/local/bin/c2patool
COPY tools/blender /opt/blender
ENV PATH="/opt/exiftool:/opt/blender:$PATH"

# 从离线 wheel 安装 Python 依赖
COPY wheels/ /tmp/wheels/
COPY source/requirements.txt /tmp/
RUN pip install --no-index --find-links=/tmp/wheels -r /tmp/requirements.txt \
    && rm -rf /tmp/wheels /tmp/requirements.txt

# 复制代码
COPY source/src/ /app/src/
COPY source/config/ /app/config/
COPY source/cli.py /app/

# 模型通过 volume 挂载，不烧入镜像
# 强制离线环境变量
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    AINOAI_OFFLINE=1

WORKDIR /app
ENTRYPOINT ["python3.11", "cli.py"]
CMD ["--help"]
```

**运行方式（关键：--network none）：**

```bash
docker run --rm \
    --network none \
    --gpus all \
    -v /secure/input:/app/input:ro \
    -v /secure/reports:/app/reports \
    -v /secure/models:/app/models:ro \
    ai-asset-audit:offline \
    scan /app/input --output /app/reports
```

---

## 九、运行时防泄密

### 9.1 启动前自检

程序启动时 **必须** 执行以下检查，任一失败则拒绝运行：

```python
# src/safety/preflight.py

import os
import socket

class OfflineViolation(Exception):
    pass

def preflight_check():
    """启动前安全自检，失败则拒绝运行"""

    # 1. 检查离线环境变量
    required_env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    for key, expected in required_env.items():
        if os.environ.get(key) != expected:
            raise OfflineViolation(
                f"环境变量 {key} 未设置为 {expected}。"
                f"审核机必须设置离线环境变量。"
            )

    # 2. 检查网络不可达
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        raise OfflineViolation(
            "ERROR: Offline mode violation. Network is reachable.\n"
            "审核机不应有外网访问能力。请检查防火墙/网络配置。"
        )
    except (socket.timeout, OSError):
        pass  # 期望：网络不可达

    # 3. 检查输入目录只读
    input_dir = os.environ.get("AINOAI_INPUT_DIR", "/app/input")
    if os.path.exists(input_dir) and os.access(input_dir, os.W_OK):
        raise OfflineViolation(
            f"输入目录 {input_dir} 可写。输入资源目录必须只读挂载。"
        )

    # 4. 检查模型路径为本地路径
    models_dir = os.environ.get("AINOAI_MODELS_DIR", "./models")
    if not os.path.isdir(models_dir):
        raise OfflineViolation(f"模型目录不存在: {models_dir}")
```

### 9.2 日志脱敏规则

日志 **允许** 写入：

```
sha256 哈希
相对路径（脱敏后）
文件类型/分辨率
模型分数
风险等级
错误码
```

日志 **禁止** 写入：

```
原图绝对路径
用户名/项目名
完整 EXIF 数据
图片 base64 内容
高分辨率缩略图
模型推理中间图
原始 prompt 内容（仅记录"检测到 prompt 字段"）
```

---

## 十、代码审计联动

### 10.1 审计四维度

#### 维度一：联网行为审计

扫描所有代码中的联网 API 调用：

```bash
rg -n "requests\.|httpx\.|aiohttp|urllib\.request|socket\.connect|websocket|grpc|boto3|openai|huggingface_hub|snapshot_download|from_pretrained|curl|wget|Invoke-WebRequest|Invoke-RestMethod" src/
```

**规则：**
- 允许 `from_pretrained(local_path, local_files_only=True)`
- 禁止 `from_pretrained("远程repo")` 未设置 `local_files_only=True`
- 禁止 `snapshot_download` 在审核机代码中出现
- 禁止任何上传接口

#### 维度二：文件外传审计

```bash
rg -n "upload|multipart|form-data|\.post\(|\.put\(|s3\.put|oss\.put|cos\.put|ftp|sftp|smtp|sendmail|telemetry|analytics" src/
```

#### 维度三：日志泄密审计

检查日志输出是否包含敏感信息：

```bash
rg -n "logging\.|logger\.|print\(|sys\.stdout" src/ | \
  rg "abspath|realpath|expanduser|getuser|base64|exif|thumbnail|raw_image"
```

#### 维度四：依赖供应链审计

```bash
# 在下载机执行，报告随包带入审核机
pip-audit -r requirements.txt --format json > audit/pip-audit.json
bandit -r src/ -f json > audit/bandit.json
semgrep --config=auto src/ --json > audit/semgrep.json
trivy fs . --format json > audit/trivy.json
```

### 10.2 代码审计模块

```python
# src/audit/code_audit.py

import re
import hashlib
from pathlib import Path
from typing import List, Dict

class CodeAuditor:

    NETWORK_PATTERNS = [
        r"requests\.(get|post|put|delete|patch)\(",
        r"httpx\.(get|post|put|delete|AsyncClient)",
        r"aiohttp\.ClientSession",
        r"urllib\.request\.(urlopen|urlretrieve)",
        r"socket\.(connect|create_connection)",
        r"websocket",
        r"grpc\.",
        r"boto3\.",
        r"openai\.",
        r"snapshot_download\(",
        r"from_pretrained\([^)]*(?!local_files_only)",
    ]

    UPLOAD_PATTERNS = [
        r"\.upload\(", r"multipart", r"form-data",
        r"s3\.put_object", r"oss\.put_object", r"cos\.put_object",
        r"ftp\.stor", r"sftp\.put", r"smtp", r"sendmail",
        r"telemetry", r"analytics\.track",
    ]

    BYPASS_PATTERNS = [
        r"--no-verify", r"skip[_-]?ai[_-]?check",
        r"SKIP_AI_DETECTION", r"ai[_-]?whitelist",
        r"force[_-]?commit", r"disable[_-]?scan",
    ]

    ASSET_REF_PATTERNS = [
        r'["\']assets/[^"\']+\.(png|jpg|jpeg|webp|tga|psd)["\']',
        r'["\']textures/[^"\']+\.(png|jpg|jpeg|webp|tga)["\']',
        r'["\']models/[^"\']+\.(fbx|obj|glb|gltf)["\']',
        r'Resources\.Load\(["\'][^"\']+["\']\)',
        r'AssetDatabase\.LoadAssetAtPath',
    ]

    def __init__(self, project_root: str):
        self.root = Path(project_root)

    def audit_network_calls(self) -> List[Dict]:
        """联网行为审计"""
        return self._scan_patterns(self.NETWORK_PATTERNS, "network", "critical")

    def audit_upload_calls(self) -> List[Dict]:
        """文件外传审计"""
        return self._scan_patterns(self.UPLOAD_PATTERNS, "upload", "critical")

    def audit_bypass_attempts(self) -> List[Dict]:
        """绕过检测审计"""
        return self._scan_patterns(self.BYPASS_PATTERNS, "bypass", "high")

    def audit_model_integrity(self, models_dir: str, expected_hashes: Dict[str, str]) -> List[Dict]:
        """验证检测模型文件完整性"""
        findings = []
        models_path = Path(models_dir)

        for model_name, expected_hash in expected_hashes.items():
            model_file = models_path / model_name
            if not model_file.exists():
                findings.append({
                    "model": model_name, "severity": "critical",
                    "message": f"模型文件缺失: {model_name}"
                })
                continue
            actual_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                findings.append({
                    "model": model_name, "severity": "critical",
                    "expected_hash": expected_hash, "actual_hash": actual_hash,
                    "message": f"模型文件哈希不匹配: {model_name}"
                })
        return findings

    def audit_config_drift(self, config_path: str, baseline_path: str) -> List[Dict]:
        """配置漂移检查"""
        import yaml
        findings = []
        with open(config_path) as f:
            current = yaml.safe_load(f)
        with open(baseline_path) as f:
            baseline = yaml.safe_load(f)

        # 检查阈值是否被恶意调低
        for key in ("flag_score", "high_confidence_score"):
            cur_val = current.get("thresholds", {}).get(key, 0)
            base_val = baseline.get("thresholds", {}).get(key, 0)
            if cur_val < base_val - 0.1:
                findings.append({
                    "config_key": f"thresholds.{key}",
                    "current": cur_val, "baseline": base_val,
                    "severity": "high",
                    "message": f"阈值从 {base_val} 降低到 {cur_val}"
                })

        # 检查检测层是否被禁用
        for layer in ("metadata", "forensics", "models"):
            if not current.get(layer, {}).get("enabled", True):
                if baseline.get(layer, {}).get("enabled", True):
                    findings.append({
                        "config_key": f"{layer}.enabled", "severity": "high",
                        "message": f"检测层 '{layer}' 已被禁用"
                    })
        return findings

    def _scan_patterns(self, patterns, category, severity) -> List[Dict]:
        findings = []
        for f in self.root.rglob("*.py"):
            if any(x in str(f) for x in [".venv", "node_modules", "__pycache__"]):
                continue
            content = f.read_text(errors="ignore")
            for pattern in patterns:
                for m in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[:m.start()].count("\n") + 1
                    findings.append({
                        "file": str(f.relative_to(self.root)),
                        "line": line_num,
                        "category": category,
                        "match": m.group(),
                        "severity": severity,
                    })
        return findings
```

---

## 十一、项目结构

```
/opt/ainoai/
├── docs/
│   └── AI美术资源离线检测流水线方案-最终版.md
├── src/
│   ├── safety/
│   │   ├── __init__.py
│   │   └── preflight.py             # 启动前安全自检
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── file_scanner.py          # 文件扫描（目录/git diff/文件列表）
│   │   └── format_detector.py       # magic bytes 格式嗅探
│   ├── metadata/
│   │   ├── __init__.py
│   │   ├── exif_analyzer.py         # ExifTool 封装
│   │   ├── png_chunks.py            # PNG tEXt/iTXt 解析
│   │   ├── c2pa_checker.py          # c2patool 封装
│   │   ├── xmp_parser.py            # XMP AI 字段检测
│   │   └── signatures.py            # AI 工具签名库
│   ├── forensics/
│   │   ├── __init__.py
│   │   ├── ela.py                   # Error Level Analysis（辅助）
│   │   ├── frequency.py             # 频率域分析（辅助）
│   │   ├── noise.py                 # 噪声一致性（辅助）
│   │   └── color_stats.py           # 色彩统计（辅助）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                  # 模型基类接口
│   │   ├── community_forensics.py   # 主模型推理
│   │   ├── universal_fake.py        # 辅助模型推理
│   │   ├── npr_detect.py            # 快筛模型推理
│   │   ├── sdxl_detector.py         # SD 专项（条件使用）
│   │   └── ensemble.py             # 多模型集成投票
│   ├── threed/
│   │   ├── __init__.py
│   │   ├── blender_render.py        # Blender headless 渲染
│   │   ├── texture_extract.py       # 贴图逐通道提取
│   │   ├── mesh_analysis.py         # Trimesh 网格分析
│   │   └── topology.py             # Open3D 拓扑分析
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── pipeline.py             # 检测流水线编排
│   │   └── scorer.py              # 综合评分 + 5级分级
│   ├── report/
│   │   ├── __init__.py
│   │   ├── json_report.py          # JSON 报告
│   │   ├── csv_report.py           # CSV 汇总
│   │   ├── markdown_report.py       # Markdown 报告
│   │   ├── html_report.py          # HTML 离线报告
│   │   └── evidence.py            # 证据快照（脱敏）
│   └── audit/
│       ├── __init__.py
│       └── code_audit.py           # 代码审计四维度
├── config/
│   ├── config.yaml                  # 主配置
│   ├── config.baseline.yaml         # 基线配置（用于漂移检查）
│   ├── signatures.yaml              # AI 签名库
│   └── whitelist.yaml               # 误报白名单
├── scripts/
│   ├── download_bundle.sh           # 下载机：准备离线包
│   └── verify_install.sh            # 审核机：安装验证
├── tests/
│   ├── test_assets/
│   │   ├── ai_generated/
│   │   └── human_created/
│   ├── test_metadata.py
│   ├── test_forensics.py
│   ├── test_models.py
│   ├── test_pipeline.py
│   └── test_safety.py              # 安全自检测试
├── cli.py                           # CLI 入口
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── .gitignore
```

---

## 十二、配置文件

### config/config.yaml

```yaml
# AI 美术资源离线检测 - 主配置

safety:
  offline_check: true                # 启动前验证离线
  input_readonly: true               # 输入目录只读
  log_sanitize: true                 # 日志脱敏

scan:
  extensions:
    image: [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tga"]
    threed: [".fbx", ".obj", ".glb", ".gltf", ".blend"]
    vector: [".svg", ".pdf"]
  mode: "directory"                  # "directory" | "git-diff" | "file-list"
  exclude_patterns:
    - "**/.git/**"
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "**/thumbnails/**"
  max_file_size_mb: 200
  parallel_workers: 4
  symlink_policy: "reject"           # 禁止软链接逃逸

metadata:
  enabled: true
  tools:
    exiftool_path: "exiftool"
    c2patool_path: "c2patool"
  signatures_file: "./config/signatures.yaml"

forensics:
  enabled: true
  role: "auxiliary"                   # 明确标注：仅辅助佐证
  ela:
    enabled: true
    quality: 90
  frequency:
    enabled: true
    method: "fft"
  noise:
    enabled: true
    block_size: 64

models:
  enabled: true
  device: "cuda"                     # "cuda" | "cpu"
  batch_size: 8
  models_dir: "${AINOAI_MODELS_DIR}"

  community_forensics:
    enabled: true
    role: "primary"
    weight: 0.55
    weights_path: "${AINOAI_MODELS_DIR}/community-forensics/model.pth"

  universal_fake_detect:
    enabled: true
    role: "auxiliary"
    weight: 0.30
    weights_path: "${AINOAI_MODELS_DIR}/universal-fake-detect/model.pth"
    backbone: "clip_vitl14"

  npr:
    enabled: true
    role: "fast_screen"
    weight: 0.15
    weights_path: "${AINOAI_MODELS_DIR}/npr/model.pth"

  sdxl_detector:
    enabled: false                   # 默认关闭，按需启用
    role: "specialist"
    license: "cc-by-nc-3.0"          # 非商用许可，需法务确认
    weights_path: "${AINOAI_MODELS_DIR}/sdxl-detector/"

threed:
  enabled: true
  blender_path: "blender"
  render_views: 6
  render_resolution: 512
  extract_textures: true             # 逐通道贴图提取
  texture_channels: ["basecolor", "albedo", "diffuse", "normal",
                     "roughness", "metallic", "emissive"]

pipeline:
  metadata_shortcircuit: true        # 元数据命中直接确认
  model_confident_threshold: 0.85    # 主模型高置信跳过其余
  gray_zone: [0.4, 0.7]             # 灰色地带需多模型确认

verdicts:
  confirmed_ai: 0.95                 # >= 此分 → Confirmed AI
  likely_ai: 0.75                    # >= 此分 → Likely AI
  suspicious: 0.50                   # >= 此分 → Suspicious
  likely_human_below: 0.30           # < 此分 → Likely Human
  # 其余 → Inconclusive

report:
  format: ["json", "csv", "markdown"]
  output_dir: "./reports"
  include_evidence: true
  evidence_max_resolution: 256       # 证据图缩略最大尺寸
  no_original_copy: true             # 禁止在报告中包含原图副本
```

---

## 十三、CLI 接口

```bash
# ============ 基础扫描 ============

# 扫描目录（完整检测）
python cli.py scan /secure/input/project_a

# 扫描 git 变更（CI 模式）
python cli.py scan --mode git-diff --base main --head HEAD

# 扫描文件列表
python cli.py scan --mode file-list --input changed_files.txt

# ============ 层级控制 ============

# 仅元数据（最快）
python cli.py scan --layer metadata /secure/input

# 元数据 + 模型（跳过像素取证）
python cli.py scan --layer model /secure/input

# 全部层（含像素取证辅助）
python cli.py scan --layer full /secure/input

# 仅 CPU（无 GPU 环境）
python cli.py scan --device cpu /secure/input

# ============ 3D 资源 ============

python cli.py scan-3d /secure/input/models --render-views 12

# ============ 安全与审计 ============

# 环境自检
python cli.py doctor

# 代码审计
python cli.py audit --check network --check upload --check bypass \
    --check model-integrity --check config-drift \
    --baseline config/config.baseline.yaml

# ============ CI 模式 ============

# 非零退出码：0=清洁, 1=Suspicious, 2=Likely/Confirmed AI, 3=错误
python cli.py scan --ci --mode git-diff --base origin/main

# ============ 报告 ============

python cli.py scan --format json,csv,markdown \
    --output /secure/reports/2026-05-26/ /secure/input
```

---

## 十四、CI 集成

### 14.1 Git Pre-commit Hook

```bash
#!/bin/bash
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | \
    grep -iE '\.(png|jpg|jpeg|webp|tga|psd|fbx|obj|glb)$')

[ -z "$STAGED_FILES" ] && exit 0

echo "AI 美术资源检测中..."
echo "$STAGED_FILES" > /tmp/staged_art.txt

python /opt/ainoai/cli.py scan \
    --mode file-list --input /tmp/staged_art.txt --ci --format json 2>/tmp/ai-scan.json
EXIT_CODE=$?

case $EXIT_CODE in
    2) echo "检测到高置信 AI 资源，提交拦截。"; exit 1 ;;
    1) echo "检测到疑似 AI 资源，已标记待复审。" ;;
esac
exit 0
```

### 14.2 GitHub Actions (self-hosted, 离线 runner)

```yaml
name: AI Art Detection
on:
  pull_request:
    paths: ['assets/**', 'art/**', 'textures/**']

jobs:
  ai-detection:
    runs-on: [self-hosted, gpu, no-internet]
    container:
      image: your-registry/ainoai:offline
      options: --gpus all --network none
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Run detection
        run: |
          python cli.py scan --ci --mode git-diff \
            --base ${{ github.event.pull_request.base.sha }} \
            --head ${{ github.event.pull_request.head.sha }} \
            --format json,markdown \
            --output /tmp/report
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ai-detection-report
          path: /tmp/report/
```

### 14.3 GitLab CI

```yaml
ai-art-detection:
  stage: test
  image: your-registry/ainoai:offline
  tags: [gpu, no-internet]
  variables:
    NVIDIA_VISIBLE_DEVICES: all
  rules:
    - changes: ["assets/**", "art/**"]
  script:
    - python cli.py scan --ci --mode git-diff
        --base $CI_MERGE_REQUEST_TARGET_BRANCH_SHA
        --head $CI_COMMIT_SHA
        --output ai-report/
  artifacts:
    paths: [ai-report/]
    when: always
```

---

## 十五、报告格式

### JSON 报告示例

```json
{
  "version": "1.0",
  "scan_time": "2026-05-26T10:00:00+08:00",
  "scan_mode": "git-diff",
  "environment": {
    "hostname": "audit-server-01",
    "gpu": "NVIDIA RTX 4090",
    "network_status": "unreachable",
    "models_loaded": ["community-forensics", "universal-fake-detect", "npr"]
  },
  "summary": {
    "total_files": 45,
    "confirmed_ai": 1,
    "likely_ai": 1,
    "suspicious": 2,
    "likely_human": 38,
    "inconclusive": 3
  },
  "results": [
    {
      "file_id": "sha256:a1b2c3d4...",
      "relative_path": "characters/hero/portrait.png",
      "type": "image",
      "size_bytes": 2457600,
      "dimensions": "2048x2048",
      "detection_layers": {
        "metadata": {
          "score": 1.0,
          "signals": ["PNG tEXt 'parameters': Steps=20, Sampler=Euler a"],
          "tool_detected": "Stable Diffusion (AUTOMATIC1111)"
        },
        "forensics": null,
        "model": null
      },
      "final_score": 1.0,
      "verdict": "Confirmed AI",
      "evidence": ["元数据包含完整 SD 生成参数"],
      "short_circuited_at": "metadata",
      "review_required": false
    },
    {
      "file_id": "sha256:e5f6a7b8...",
      "relative_path": "ui/banner_event.jpg",
      "type": "image",
      "size_bytes": 856320,
      "dimensions": "1920x1080",
      "detection_layers": {
        "metadata": { "score": 0.0, "signals": [] },
        "forensics": {
          "ela_uniformity": 0.82,
          "frequency_anomaly": 0.65,
          "role": "auxiliary_evidence"
        },
        "model": {
          "community_forensics": 0.81,
          "universal_fake_detect": 0.74,
          "npr": 0.68,
          "ensemble_score": 0.77
        }
      },
      "final_score": 0.77,
      "verdict": "Likely AI",
      "evidence": [
        "主模型 Community-Forensics: 0.81",
        "辅助模型 UniversalFakeDetect: 0.74",
        "ELA 均匀度异常(辅助佐证): 0.82"
      ],
      "review_required": true
    }
  ]
}
```

### HTML 报告安全约束

```
- 默认不保存原图副本
- 缩略图仅保存低分辨率(≤256px)、带水印、不可还原版本
- 内网 Web 页面优先动态读取本地文件，不复制资产
- 报告中不包含完整 EXIF/prompt 原文（仅摘要）
```

---

## 十六、性能估算

### 单文件耗时（RTX 4090）

| 层 | 耗时/文件 | 说明 |
|----|-----------|------|
| 安全预扫描 | < 1ms | hash + magic bytes |
| 元数据分析 | < 5ms | ExifTool + 自定义解析 |
| 像素取证（辅助） | ~100-200ms | ELA + FFT + 噪声 |
| NPR 快筛 | ~50ms | 轻量模型 |
| Community-Forensics | ~300ms | 主模型 |
| UniversalFakeDetect | ~200ms | CLIP 特征提取 |
| **完整流水线** | **~500-800ms** | 含短路优化 |

### 批量吞吐

| 场景 | 文件数 | GPU | 耗时 |
|------|--------|-----|------|
| 日常提交 | 5-20 | RTX 3060 | < 30s |
| 版本发布全扫描 | 500 | RTX 4090 | ~5min |
| 大型项目 | 5000 | RTX 4090 | ~30min |

### 短路优化

- ~10-20% AI 图在元数据层直接命中
- 主模型高置信(>0.85)时跳过辅助模型
- 实际平均耗时约为理论值的 60-70%

---

## 十七、落地阶段

### 第一阶段（2-3 天，可用版）

```
[必须] ExifTool + c2patool + 元数据签名库
[必须] Community-Forensics 主模型
[建议] UniversalFakeDetect + NPR 辅助
[必须] 离线启动自检
[必须] JSON/CSV/Markdown 报告
[必须] 基础代码审计（联网+上传扫描）
[必须] Docker --network none 部署
```

### 第二阶段（1-2 周）

```
FBX/OBJ/GLB 3D 资源支持
Blender 多角度渲染 + 贴图逐通道提取
像素取证辅助层
人工复核流程 + 白名单管理
HTML 离线报告
完整代码审计四维度
Git Hook / CI 集成
```

### 第三阶段（待确认后）

```
RA-Det / SPAI / HEDGE 模型接入（确认开源后）
SVG/PDF/PSD 格式支持
内网 Web 审核台
更细化的 3D 网格质量评分
审计日志 + 权限管理
```

---

## 十八、上线验收清单

| # | 验收项 | 通过标准 |
|---|--------|----------|
| 1 | 断网运行 | 审核机断网后所有功能正常 |
| 2 | 模型不自动下载 | HF_HUB_OFFLINE=1 下模型加载正常 |
| 3 | 网络自检 | `cli.py doctor` 显示 Network: UNREACHABLE |
| 4 | 报告无原图 | 报告中不含原始资源副本 |
| 5 | 日志脱敏 | 日志无绝对路径、用户名、EXIF 全文 |
| 6 | 3D 渲染安全 | Blender 不访问外部贴图 URL |
| 7 | 代码审计 | 无上传/外联逻辑 |
| 8 | 依赖 hash | 所有 wheel/模型/工具 hash 校验通过 |
| 9 | 结果稳定 | 同一输入重复运行结果一致 |
| 10 | 误报处理 | 误报样本可加入白名单 |
| 11 | 输入只读 | 检测过程不修改原始文件 |
| 12 | Docker 隔离 | `--network none` 运行成功 |

---

## 十九、风险与局限

| 风险 | 缓解措施 |
|------|----------|
| 元数据被清除 | 模型检测兜底 |
| 新 AI 模型未被训练过 | 定期更新模型；CF 泛化最强 |
| 误报（高质量人工图） | 白名单 + 人工复审 |
| 漏报（精心处理的 AI 图） | 多模型投票 + 取证辅助 |
| GPU 不可用 | CPU 模式退化（慢但可用） |
| 3D AI 检测不成熟 | 贴图+渲染双路检测 |
| Organika 许可证风险 | 默认关闭，需法务确认后启用 |
| RA-Det/SPAI/HEDGE 无公开仓库 | 标注"第二阶段待确认"，不阻塞一期 |
| 模型被篡改 | SHA256 完整性校验 |
| 配置被调低 | 基线对比 + 审计告警 |

---

## 二十、维护策略

### 签名库更新

- 频率：每月或有新 AI 工具发布时
- 方式：更新 `config/signatures.yaml`，通过离线包分发

### 模型更新

- 季度评估：用最新 AI 工具生成测试图评估检测率
- 模型替换：通过离线包更新权重文件 + hash 重新签名

### 误报管理

```yaml
# config/whitelist.yaml
whitelist:
  - file_hash: "sha256:abc123..."
    reason: "人工绘制水彩画，模型误判"
    approved_by: "art-lead-zhang"
    date: "2026-05-26"
    expires: "2027-05-26"
```

---

## 总结

```
最终方案 = 完整工程设计（三层检测 + 多模型 + 3D + CI + CLI）
        + 保密安全基线（双机隔离 + 三层断网 + 四维审计 + 运行时自检）
        + 修正（Organika 许可证 + 取证层定位 + 模型优先级 + 分阶段落地）
```

**核心不是模型数量最多，而是：**

1. 资源绝不出内网
2. 证据可追溯
3. 检测结果可复核
4. 工具本身经过防泄密审计
5. 运行时强制断网
