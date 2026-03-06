param(
    [switch]$VerboseOutput
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Test-PythonCmd {
    param(
        [string]$Command,
        [string[]]$PrefixArgs
    )

    try {
        & $Command @PrefixArgs '--version' | Out-Null
        return $true
    } catch {
        return $false
    }
}

$pythonCmd = $null
$pythonPrefixArgs = @()

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if ((Test-Path $venvPython) -and (Test-PythonCmd -Command $venvPython -PrefixArgs @())) {
    $pythonCmd = $venvPython
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonCmd -Command 'python' -PrefixArgs @())) {
    $pythonCmd = 'python'
} elseif ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonCmd -Command 'py' -PrefixArgs @('-3'))) {
    $pythonCmd = 'py'
    $pythonPrefixArgs = @('-3')
} else {
    Write-Error 'No usable Python interpreter found. Activate a working .venv or install Python.'
}

$pytestArgs = @('-m', 'pytest', 'apps/api/tests')
if ($VerboseOutput) {
    $pytestArgs += '-vv'
} else {
    $pytestArgs += '-q'
}

Write-Host "Running tests from $repoRoot"
& $pythonCmd @pythonPrefixArgs @pytestArgs
exit $LASTEXITCODE
