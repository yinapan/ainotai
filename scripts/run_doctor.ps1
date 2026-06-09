param(
  [switch]$ProbeNetwork
)

& "$PSScriptRoot\set_offline_env.ps1"

$argsList = @("doctor", "--offline")
if ($ProbeNetwork) {
  $argsList += "--probe-network"
}

python "$PSScriptRoot\..\cli.py" @argsList
