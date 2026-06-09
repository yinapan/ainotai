#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${1:-ai_asset_audit_bundle}"

echo "=== 准备离线安装包 ==="
echo "目标目录: ${BUNDLE_DIR}"

mkdir -p "${BUNDLE_DIR}"/{source,wheels,models,tools,config,checksums,docker}

echo ">>> 下载 Python 依赖..."
pip download -r requirements.txt -d "${BUNDLE_DIR}/wheels/"

echo ">>> 复制源码..."
cp -r src/ cli.py pyproject.toml requirements.txt "${BUNDLE_DIR}/source/"

echo ">>> 复制配置..."
cp -r config/ "${BUNDLE_DIR}/config/"

echo ">>> 复制模型权重目录（若已下载）..."
if [ -d "models" ] && [ "$(ls -A models/)" ]; then
    cp -r models/ "${BUNDLE_DIR}/models/"
else
    echo "    注意: models/ 为空，请手动下载模型权重到 ${BUNDLE_DIR}/models/"
fi

echo ">>> 复制工具（若已下载）..."
if [ -d "tools" ] && [ "$(ls -A tools/ 2>/dev/null)" ]; then
    cp -r tools/ "${BUNDLE_DIR}/tools/"
else
    echo "    注意: tools/ 为空，请手动下载 exiftool/c2patool/aicheck 到 ${BUNDLE_DIR}/tools/"
fi

echo ">>> 构建 Docker 镜像..."
if command -v docker &>/dev/null; then
    docker build -t ai-asset-audit:offline --target offline .
    docker save ai-asset-audit:offline -o "${BUNDLE_DIR}/docker/ai-asset-audit-offline.tar"
    echo "    Docker 镜像已保存到 ${BUNDLE_DIR}/docker/"
else
    echo "    Docker 未安装，跳过镜像构建"
fi

echo ">>> 生成 SHA256 校验和..."
find "${BUNDLE_DIR}/source" "${BUNDLE_DIR}/wheels" "${BUNDLE_DIR}/models" \
     "${BUNDLE_DIR}/tools" "${BUNDLE_DIR}/config" \
     -type f -print0 2>/dev/null | xargs -0 sha256sum > "${BUNDLE_DIR}/checksums/all.sha256"

echo ""
echo "=== 离线安装包准备完成 ==="
echo "目录: ${BUNDLE_DIR}"
echo "校验文件: ${BUNDLE_DIR}/checksums/all.sha256"
echo ""
echo "下一步："
echo "  1. 将 ${BUNDLE_DIR} 复制到审核机"
echo "  2. 关闭外网连接"
echo "  3. 设置离线环境变量"
echo "  4. 运行 scripts/run_offline_scan.sh"
