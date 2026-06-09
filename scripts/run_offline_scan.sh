#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${1:?用法: $0 <输入资源目录> [报告输出目录]}"
REPORT_DIR="${2:-./reports}"

echo "=== 断网审核扫描 ==="

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export NO_PROXY="*"

echo ">>> 环境检查..."
python cli.py doctor --offline --probe-network

echo ">>> 开始扫描..."
python cli.py scan "${INPUT_DIR}" \
    --offline \
    --probe-network \
    --config ./config/config.yaml \
    --output "${REPORT_DIR}" \
    --layer full

EXIT_CODE=$?

echo ""
echo "=== 扫描完成 ==="
echo "报告目录: ${REPORT_DIR}"
echo "退出码: ${EXIT_CODE}"
echo ""
echo "退出码说明:"
echo "  0 = 无异常"
echo "  1 = 存在 Suspicious"
echo "  2 = 存在 Likely AI / Confirmed AI"
echo "  3 = 检测错误"
echo "  4 = 离线安全检查失败"

exit ${EXIT_CODE}
