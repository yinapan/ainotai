#!/bin/bash
# ──────────────────────────────────────────────────────
# 模型权重下载脚本 (Linux/Mac 下载机)
# 运行前需要: pip install huggingface-hub
# ──────────────────────────────────────────────────────
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_DIR="$ROOT/models"
WHEEL_DIR="$ROOT/wheels"

echo "=== AI 美术资源离线检测 — 下载脚本 ==="
echo "Root: $ROOT"
echo ""

# ──── 1. NPR (已内置 17MB) ────
echo "[1/4] NPR (AI 绘图风格检测)"
if [ -f "$MODEL_DIR/npr/NPR.pth" ]; then
    echo "  OK: NPR.pth 已存在"
else
    echo "  TODO: 请将 NPR.pth 放入 $MODEL_DIR/npr/"
fi

# ──── 2. Community-Forensics (HuggingFace, ~300MB) ────
echo "[2/4] Community-Forensics (OwensLab/commfor-model-384)"
if [ -f "$MODEL_DIR/community-forensics/config.json" ]; then
    echo "  SKIP: 已存在"
else
    echo "  下载中..."
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('OwensLab/commfor-model-384', local_dir='$MODEL_DIR/community-forensics')
print('DONE')
" 2>&1 | tail -3
fi

# ──── 3. SDXL Detector (HuggingFace, ~100MB) ────
echo "[3/4] SDXL Detector (ash12321/sdxl-detector-resnet50)"
if [ -f "$MODEL_DIR/sdxl-detector/config.json" ]; then
    echo "  SKIP: 已存在"
else
    echo "  下载中..."
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('ash12321/sdxl-detector-resnet50', local_dir='$MODEL_DIR/sdxl-detector')
print('DONE')
" 2>&1 | tail -3
fi

# ──── 4. CLIP ViT-B/32 (HuggingFace, ~600MB) ────
echo "[4/6] CLIP ViT-B/32 (openai/clip-vit-base-patch32)"
if [ -f "$MODEL_DIR/clip-detector/config.json" ]; then
    echo "  SKIP: 已存在"
else
    echo "  下载中..."
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('openai/clip-vit-base-patch32', local_dir='$MODEL_DIR/clip-detector')
print('DONE')
" 2>&1 | tail -3
fi

# ──── 5. CNNDetection (GitHub, ~100MB) ────
echo "[5/6] CNNDetection (PeterWang512/CNNDetection)"
if ls "$MODEL_DIR/cnn-detection"/*.pth 1>/dev/null 2>&1; then
    echo "  SKIP: 已存在"
else
    echo "  下载中..."
    mkdir -p "$MODEL_DIR/cnn-detection"
    python3 -c "
import urllib.request, os
url = 'https://www.dropbox.com/s/h0tc880f2jl83dk/blur_jpg_prob0.5.pth?dl=1'
dst = '$MODEL_DIR/cnn-detection/blur_jpg_prob0.5.pth'
if not os.path.exists(dst):
    print('  Downloading CNNDetection weights...')
    urllib.request.urlretrieve(url, dst)
    print('  DONE:', os.path.getsize(dst), 'bytes')
else:
    print('  Already exists')
" 2>&1 | tail -3
fi

# ──── 6. UniversalFakeDetect (~350MB) ────
echo "[6/6] UniversalFakeDetect (Corvi et al.)"
if ls "$MODEL_DIR/universal-fake-detect"/*.pth 1>/dev/null 2>&1; then
    echo "  SKIP: 已存在"
else
    echo "  TODO: 请手动下载 UniversalFakeDetect 权重"
    echo "    来源: https://github.com/Yuheng-Li/UniversalFakeDetect"
    echo "    将 .pth 文件放入 $MODEL_DIR/universal-fake-detect/"
fi

# ──── Pip wheels ────
echo ""
echo "=== Pip 离线包 ==="
mkdir -p "$WHEEL_DIR"
pip download opencv-python-headless fbxloader PyYAML -d "$WHEEL_DIR"

# ──── SHA256 ────
echo ""
echo "=== 生成校验和 ==="
python3 -c "
import hashlib, glob
for f in sorted(glob.glob('$MODEL_DIR/**/*.pth', recursive=True) + sorted(glob.glob('$WHEEL_DIR/*.whl')):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b''):
            h.update(chunk)
    print(f'{h.hexdigest()}  {f}')
" | tee checksums.sha256

echo ""
echo "=== 完成 ==="
echo "模型目录: $MODEL_DIR"
echo "Wheels: $WHEEL_DIR"
echo ""
echo "下一步: 将整个项目目录拷贝到审核机"
echo "  审核机上运行: bash scripts/run_offline_scan.sh"
