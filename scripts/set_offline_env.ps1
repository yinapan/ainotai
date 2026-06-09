$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE = "1"
$env:NO_PROXY = "*"

Write-Host "=== 离线环境变量已设置 ===" -ForegroundColor Green
Write-Host "  HF_HUB_OFFLINE = $env:HF_HUB_OFFLINE"
Write-Host "  TRANSFORMERS_OFFLINE = $env:TRANSFORMERS_OFFLINE"
Write-Host "  HF_DATASETS_OFFLINE = $env:HF_DATASETS_OFFLINE"
Write-Host "  NO_PROXY = $env:NO_PROXY"
Write-Host ""
Write-Host "运行 doctor 检查: python cli.py doctor --offline" -ForegroundColor Cyan
