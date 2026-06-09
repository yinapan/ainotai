param(
    [Parameter(Mandatory=$true)]
    [string]$InputDir,

    [string]$OutputDir = "./reports",
    [string]$Layer = "full"
)

$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE = "1"
$env:NO_PROXY = "*"

Write-Host "=== 断网审核扫描 ===" -ForegroundColor Green
Write-Host "输入目录: $InputDir"
Write-Host "报告目录: $OutputDir"
Write-Host "检测层级: $Layer"
Write-Host ""

Write-Host ">>> 环境检查..." -ForegroundColor Cyan
python cli.py doctor --offline

Write-Host ">>> 开始扫描..." -ForegroundColor Cyan
python cli.py scan $InputDir `
    --offline `
    --config ./config/config.yaml `
    --output $OutputDir `
    --layer $Layer

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=== 扫描完成 ===" -ForegroundColor Green
Write-Host "退出码: $exitCode"
exit $exitCode
