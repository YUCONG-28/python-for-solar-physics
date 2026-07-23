param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Command,
    [string]$EnvironmentName = "solarphysics_env_latest",
    [string]$MiniforgeRoot,
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
$supportedEnvironments = @("solarphysics_env_latest", "solarphysics_env")
if ($EnvironmentName -notin $supportedEnvironments) {
    throw "Unsupported environment '$EnvironmentName'. Use solarphysics_env_latest or explicitly select solarphysics_env."
}

function Find-MiniforgeRoot {
    param([string]$ExplicitRoot)
    foreach ($trustedCandidate in @($ExplicitRoot, $env:SOLAR_MINIFORGE_ROOT)) {
        if (-not $trustedCandidate) { continue }
        if (Test-Path -LiteralPath $trustedCandidate -PathType Container) {
            return (Resolve-Path -LiteralPath $trustedCandidate).Path
        }
        throw "Explicit Miniforge root was not found: $trustedCandidate"
    }
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:CONDA_EXE) {
        $condaParent = Split-Path -Parent $env:CONDA_EXE
        if ((Split-Path -Leaf $condaParent) -in @("Scripts", "condabin")) {
            $candidates.Add((Split-Path -Parent $condaParent))
        }
    }
    if ($env:USERPROFILE) {
        $candidates.Add((Join-Path $env:USERPROFILE "miniforge3"))
        $candidates.Add((Join-Path $env:USERPROFILE "Miniforge3"))
    }
    foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
        $candidates.Add((Join-Path $drive.Root "miniforge3"))
        $candidates.Add((Join-Path $drive.Root "Miniforge3"))
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "Miniforge was not found. Set SOLAR_MINIFORGE_ROOT or pass -MiniforgeRoot."
}

$resolvedMiniforgeRoot = Find-MiniforgeRoot -ExplicitRoot $MiniforgeRoot
$environmentRoot = Join-Path (Join-Path $resolvedMiniforgeRoot "envs") $EnvironmentName
$pythonExecutable = Join-Path $environmentRoot "python.exe"
if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Miniforge environment '$EnvironmentName' is missing: $pythonExecutable"
}

$appsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $appsRoot
$arguments = @(
    "-m", "solar_apps.launcher",
    "--workspace-root", $workspaceRoot,
    "--miniforge-root", $resolvedMiniforgeRoot,
    "--environment-name", $EnvironmentName,
    "--launcher-name", "Apps/run.ps1"
)
if ($ConfigPath) {
    $arguments += @("--config-path", $ConfigPath)
}
$arguments += "--"
$arguments += $Command
& $pythonExecutable @arguments
exit $LASTEXITCODE
