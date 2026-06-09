#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${1:-ai_asset_audit_bundle}"
CHECKSUM_FILE="${BUNDLE_DIR}/checksums/all.sha256"

if [ ! -f "${CHECKSUM_FILE}" ]; then
    echo "ERROR: 校验文件不存在: ${CHECKSUM_FILE}"
    exit 1
fi

echo "=== 验证文件完整性 ==="
echo "校验文件: ${CHECKSUM_FILE}"

if sha256sum -c "${CHECKSUM_FILE}"; then
    echo ""
    echo "=== 所有文件校验通过 ==="
    exit 0
else
    echo ""
    echo "ERROR: 文件校验失败！可能存在篡改或传输损坏。"
    exit 1
fi
