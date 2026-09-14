param(
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(Mandatory=$true)][string]$PromptFile,
    [ValidateSet("Read","Write")][string]$Mode = "Read",
    [string]$Variant = "",
    [string[]]$File = @()
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$promptPath = (Resolve-Path $PromptFile).Path

$normalModels = @(
    "opencode-go/minimax-m3",
    "opencode-go/qwen3.8-flash",
    "opencode-go/deepseek-v4.1-flash",
    "opencode-go/deepseek-v4-flash-vision-exp"
)

$modelRef = if ($Model.StartsWith("opencode-go/")) { $Model } else { "opencode-go/$Model" }
if ($modelRef -notin $normalModels) {
    throw "Model '$modelRef' is outside the normal cost-controlled routing set."
}

$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $available = @(
        & opencode models opencode-go 2>&1 |
        Where-Object { "$_" -match '^opencode-go/' } |
        ForEach-Object { "$_".Trim() }
    )
} finally {
    $ErrorActionPreference = $prev
}

if ($modelRef -notin $available) { throw "Model is not currently selectable: $modelRef" }

$agent = if ($Mode -eq "Write") { "amr-direct-write" } else { "amr-direct-read" }
$prompt = Get-Content -Raw $promptPath

$args = @("run",$prompt,"--agent",$agent,"--model",$modelRef,"--auto","--dir",$repo)
if ($Variant) { $args += @("--variant",$Variant) }
$args += @("--file",$promptPath)
foreach ($f in $File) { $args += @("--file",(Resolve-Path $f).Path) }

$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & opencode @args
    $code = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $prev
}
exit $code
