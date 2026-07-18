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
        if (-not $candidate) { continue }
        $trimmedCandidate = $candidate.TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        )
        $leaf = Split-Path -Leaf $trimmedCandidate
        if ($leaf -notmatch "(?i)miniforge") { continue }
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "Miniforge was not found. Set SOLAR_MINIFORGE_ROOT or pass -MiniforgeRoot."
}

$resolvedMiniforgeRoot = Find-MiniforgeRoot -ExplicitRoot $MiniforgeRoot
$miniforgeMarkers = Get-ChildItem `
    -LiteralPath (Join-Path $resolvedMiniforgeRoot "conda-meta") `
    -Filter "miniforge_console_shortcut-*.json" `
    -ErrorAction SilentlyContinue
if (-not $miniforgeMarkers) {
    throw "The selected Conda installation is not Miniforge."
}
$environmentRoot = Join-Path $resolvedMiniforgeRoot ("envs\" + $EnvironmentName)
$pythonExecutable = Join-Path $environmentRoot "python.exe"
if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Miniforge environment '$EnvironmentName' is missing. Expected its python.exe under the selected Miniforge root."
}
if (-not (Test-Path -LiteralPath (Join-Path $environmentRoot "conda-meta") -PathType Container)) {
    throw "The selected directory is not a valid Miniforge environment: $EnvironmentName"
}

$appsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $appsRoot
$pythonRoot = Join-Path $workspaceRoot "Python"
$localRoot = if ($env:SOLAR_APPS_LOCAL_ROOT) {
    $env:SOLAR_APPS_LOCAL_ROOT
} else {
    Join-Path $workspaceRoot "Local"
}
if (-not (Test-Path -LiteralPath $pythonRoot -PathType Container)) {
    throw "Public Python partition not found beside Apps/."
}

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $localRoot "configs\paths.local.yaml"
}
$resolvedConfigPath = [IO.Path]::GetFullPath($ConfigPath)

Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$env:PYTHONNOUSERSITE = "1"
$env:SOLAR_APPS_REPO_ROOT = [IO.Path]::GetFullPath($workspaceRoot)
$env:SOLAR_APPS_LOCAL_ROOT = [IO.Path]::GetFullPath($localRoot)
$env:SOLAR_APPS_CONFIG = $resolvedConfigPath
$env:SOLAR_PHYSICS_CONFIG = $resolvedConfigPath
$env:SOLAR_APPS_PYTHON_EXECUTABLE = (Resolve-Path -LiteralPath $pythonExecutable).Path
$env:SOLAR_APPS_ENVIRONMENT = $EnvironmentName
$env:SOLAR_MINIFORGE_ROOT = $resolvedMiniforgeRoot

$environmentPaths = @(
    $environmentRoot
    (Join-Path $environmentRoot "Library\mingw-w64\bin")
    (Join-Path $environmentRoot "Library\usr\bin")
    (Join-Path $environmentRoot "Library\bin")
    (Join-Path $environmentRoot "Scripts")
)
$env:PATH = (@($environmentPaths) + @($env:PATH)) -join [IO.Path]::PathSeparator

& $pythonExecutable -m solar_apps.platform.environment_probe `
    --apps-root $appsRoot `
    --python-root $pythonRoot
if ($LASTEXITCODE -ne 0) {
    throw "Apps are not installed in '$EnvironmentName'. Install editable packages with that Miniforge Python: -m pip install -e <repo>\Python[quality-ml] -e <repo>\Apps"
}

if (-not $Command -or $Command.Count -eq 0) {
    $Command = @("--help")
}
& $pythonExecutable -m solar_apps.cli @Command
exit $LASTEXITCODE
