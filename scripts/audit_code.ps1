param(
  [string]$Path = ".\src",
  [string]$Output = ".\reports\code-audit.json"
)

New-Item -ItemType Directory -Force -Path (Split-Path $Output) | Out-Null
python "$PSScriptRoot\..\cli.py" audit-code $Path --output $Output
