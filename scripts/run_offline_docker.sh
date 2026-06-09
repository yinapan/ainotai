#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${1:?用法: $0 <输入资源目录> [报告输出目录]}"
REPORT_DIR="${2:-./reports}"

INPUT_ABS="$(cd "${INPUT_DIR}" && pwd)"
REPORT_ABS="$(mkdir -p "${REPORT_DIR}" && cd "${REPORT_DIR}" && pwd)"
MODELS_ABS="$(cd ./models && pwd)"
TOOLS_ABS="$(cd ./tools && pwd)"

echo "=== Docker 断网审核 ==="
echo "输入目录: ${INPUT_ABS} (只读)"
echo "报告目录: ${REPORT_ABS}"
echo "网络模式: none"

docker run --rm --network none \
    -v "${INPUT_ABS}:/app/input:ro" \
    -v "${MODELS_ABS}:/app/models:ro" \
    -v "${TOOLS_ABS}:/app/tools:ro" \
    -v "${REPORT_ABS}:/app/reports" \
    ai-asset-audit:offline \
    python cli.py scan /app/input \
        --offline \
        --output /app/reports \
        --layer full

EXIT_CODE=$?

echo ""
echo "=== Docker 审核完成 ==="
echo "退出码: ${EXIT_CODE}"
exit ${EXIT_CODE}
