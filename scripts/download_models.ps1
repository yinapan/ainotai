<#
.SYNOPSIS
  下载预训练 AI 检测模型权重到 models/ 目录
.DESCRIPTION
  在联网下载机上运行。下载完成后可将整个 models/ 目录拷贝到审核机。
  需要: Python 3.10+, pip, huggingface-cli (可选)
#>
param(
    [switch]$SkipHuggingFace,
    [switch]$SkipPip
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ModelDir = Join-Path $Root "models"
$WheelDir = Join-Path $Root "wheels"

Write-Host "=== AI 美术资源离线检测 — 模型权重下载 ===" -ForegroundColor Cyan
Write-Host "Root: $Root"
Write-Host ""

# ──── 1. CNNdetection (ResNet-50, ~100MB) ────
Write-Host "[1/5] CNNdetection (Wang et al.)" -ForegroundColor Yellow
$CnnDir = Join-Path $ModelDir "cnn-detection"
if (Test-Path (Join-Path $CnnDir "model_epoch_best.pth")) {
    Write-Host "  SKIP: 已存在"
} else {
    Write-Host "  → 从 GitHub Releases 下载..."
    $CnnUrl = "https://github.com/PeterWang512/CNNDetection/releases/download/v0.3/model_epoch_best.pth"
    try {
        Invoke-WebRequest -Uri $CnnUrl -OutFile (Join-Path $CnnDir "model_epoch_best.pth") -ErrorAction Stop
        Write-Host "  OK: CNNdetection 下载完成" -ForegroundColor Green
    } catch {
        Write-Host "  WARN: 下载失败，请手动从 https://github.com/PeterWang512/CNNDetection 下载" -ForegroundColor DarkYellow
        Write-Host "  手动步骤: 下载 model_epoch_best.pth → 放入 $CnnDir"
    }
}

# ──── 2. NPR (已内置) ────
Write-Host "[2/5] NPR (AI 绘图风格检测)" -ForegroundColor Yellow
$NprDir = Join-Path $ModelDir "npr"
if (Test-Path (Join-Path $NprDir "NPR.pth")) {
    Write-Host "  OK: NPR.pth 已存在 (17MB)" -ForegroundColor Green
} else {
    Write-Host "  TODO: 请手动下载 NPR 权重到 $NprDir"
}

# ──── 3. CLIP ViT-B/32 (HuggingFace) ────
Write-Host "[3/5] CLIP ViT-B/32 (OpenAI/HuggingFace)" -ForegroundColor Yellow
$ClipDir = Join-Path $ModelDir "clip-detector"
if (Test-Path (Join-Path $ClipDir "config.json")) {
    Write-Host "  SKIP: 已存在"
} else {
    if (-not $SkipHuggingFace) {
        Write-Host "  → 通过 huggingface-cli 下载..."
        try {
            $env:HF_HUB_ENABLE_HF_TRANSFER = "1"
            huggingface-cli download openai/clip-vit-base-patch32 --local-dir $ClipDir --local-dir-use-symlinks False 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK: CLIP 下载完成 (~600MB)" -ForegroundColor Green
            } else {
                throw "huggingface-cli failed"
            }
        } catch {
            Write-Host "  WARN: 需要先安装: pip install huggingface-hub" -ForegroundColor DarkYellow
            Write-Host "  然后运行: huggingface-cli download openai/clip-vit-base-patch32 --local-dir $ClipDir"
        }
    }
}

# ──── 4. Community-Forensics ────
Write-Host "[4/5] Community-Forensics" -ForegroundColor Yellow
$CfDir = Join-Path $ModelDir "community-forensics"
$CfWeights = Get-ChildItem $CfDir -Filter "*.pth" -ErrorAction SilentlyContinue
if ($CfWeights) {
    Write-Host "  OK: 权重已存在" -ForegroundColor Green
} else {
    Write-Host "  手动步骤:" -ForegroundColor DarkYellow
    Write-Host "  1. git clone https://github.com/Community-Forensics/Community-Forensics.git /tmp/cf"
    Write-Host "  2. 复制权重文件到 $CfDir"
    Write-Host "  3. 或从 HuggingFace: huggingface-cli download community-forensics/cf-model --local-dir $CfDir"
}

# ──── 5. Organika/sdxl-detector (HuggingFace) ────
Write-Host "[5/5] SDXL Detector (Organika/HuggingFace)" -ForegroundColor Yellow
$SdxlDir = Join-Path $ModelDir "sdxl-detector"
if (Test-Path (Join-Path $SdxlDir "config.json")) {
    Write-Host "  SKIP: 已存在"
} else {
    if (-not $SkipHuggingFace) {
        Write-Host "  → 通过 huggingface-cli 下载..."
        try {
            huggingface-cli download Organika/sdxl-detector --local-dir $SdxlDir --local-dir-use-symlinks False 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK: SDXL Detector 下载完成" -ForegroundColor Green
            }
        } catch {
            Write-Host "  WARN: 下载失败，手动: huggingface-cli download Organika/sdxl-detector --local-dir $SdxlDir" -ForegroundColor DarkYellow
        }
    }
}

# ──── 6. Pip wheels ────
Write-Host ""
Write-Host "=== Pip 离线包下载 ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

if (-not $SkipPip) {
    Write-Host "  下载 opencv-python-headless, fbxloader, PyYAML..."
    pip download opencv-python-headless fbxloader PyYAML -d $WheelDir
    Write-Host "  下载 transformers + torch (可选，用于模型推理)..."
    pip download torch torchvision transformers -d $WheelDir 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: wheels 已保存到 $WheelDir" -ForegroundColor Green
    }
}

# ──── Summary ────
Write-Host ""
Write-Host "=== 下载完成 ===" -ForegroundColor Cyan
Write-Host "模型目录: $ModelDir"
Get-ChildItem $ModelDir -Directory | ForEach-Object {
    $files = Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue
    $count = ($files | Measure-Object).Count
    $size = "{0:N0} MB" -f (($files | Measure-Object -Property Length -Sum).Sum / 1MB)
    $icon = if ($count -gt 0) { "✅" } else { "⬜" }
    Write-Host "  $icon $($_.Name): $count 文件, $size"
}
Write-Host ""
Write-Host "Wheels 目录: $WheelDir"
if (Test-Path $WheelDir) {
    $w_count = (Get-ChildItem $WheelDir -File | Measure-Object).Count
    Write-Host "  📦 $w_count 个 wheel 文件"
}
Write-Host ""
Write-Host "下一步: 将整个工程目录拷贝到审核机，断网后运行:"
Write-Host '  .\scripts\run_scan.ps1 -InputPath .\input_assets -OutputPath .\reports'
