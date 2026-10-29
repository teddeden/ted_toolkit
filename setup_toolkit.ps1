<#
.SYNOPSIS
    Guided first-time setup for Ted's Toolkit.

.DESCRIPTION
    1. Asks whether to use conda (environment.yml) or standard python.org Python + pip
       (requirements.txt), auto-detecting what is installed.
    2. Creates (or optionally updates) the environment and checks it is Python 3.12.
    3. Writes local_env.cmd next to this script - a one-line, machine-specific activation
       command that start_ted_toolkit.bat and regression_test.bat call if present.
    4. Optionally runs the regression suite.
    Normally started via setup_toolkit.bat. See GETTING_STARTED.md for the manual steps.

.PARAMETER Flow
    'conda' or 'venv'. Prompted if omitted.
.PARAMETER EnvPath
    Where to create the environment. Prompted if omitted (default: a folder next to the repo).
.PARAMETER Defaults
    Accept every default answer without prompting (useful for unattended setup).
#>
param(
    [ValidateSet('conda', 'venv')] [string] $Flow,
    [string] $EnvPath,
    [switch] $Defaults
)

$ErrorActionPreference = 'Stop'
$RepoDir = $PSScriptRoot
$LocalEnvFile = Join-Path $RepoDir 'local_env.cmd'
$RequiredPython = '3.12'

function Ask([string] $Prompt, [string] $Default) {
    if ($Defaults) { Write-Host "$Prompt [$Default]: $Default"; return $Default }
    $answer = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
    return $answer.Trim().Trim('"')
}

function AskYN([string] $Prompt, [bool] $DefaultYes) {
    $hint = 'y/N'
    if ($DefaultYes) { $hint = 'Y/n' }
    if ($Defaults) { Write-Host "$Prompt ($hint): (default)"; return $DefaultYes }
    $answer = Read-Host "$Prompt ($hint)"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return $answer.Trim().ToLower().StartsWith('y')
}

function Invoke-Checked([string] $Exe, [string[]] $Arguments) {
    Write-Host "`n> $Exe $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit code $LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

function Get-PythonVersion([string] $PythonExe) {
    $version = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ($LASTEXITCODE -ne 0) { throw "Could not run $PythonExe" }
    return $version.Trim()
}

function Find-CondaBase {
    $candidates = @()
    $condaCmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaCmd) {
        try { $candidates += (& conda info --base 2>$null).Trim() } catch { }
    }
    $candidates += @(
        'C:\ProgramData\Anaconda3', 'C:\ProgramData\Miniconda3',
        (Join-Path $env:USERPROFILE 'anaconda3'), (Join-Path $env:USERPROFILE 'miniconda3'),
        (Join-Path $env:LOCALAPPDATA 'anaconda3'), (Join-Path $env:LOCALAPPDATA 'miniconda3')
    )
    foreach ($base in $candidates) {
        if ($base -and (Test-Path (Join-Path $base 'Scripts\activate.bat')) -and
                (Test-Path (Join-Path $base 'Scripts\conda.exe'))) {
            return $base
        }
    }
    return $null
}

function Find-Python312 {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $exe = (& py "-$RequiredPython" -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        } catch { }
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        'C:\Program Files\Python312\python.exe'
    )
    foreach ($exe in $candidates) { if (Test-Path $exe) { return $exe } }
    return $null
}

Write-Host ''
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host " Ted's Toolkit setup" -ForegroundColor Cyan
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host "Toolkit folder: $RepoDir`n"

$condaBase = Find-CondaBase
$python312 = Find-Python312
if ($condaBase) { Write-Host "Found conda:       $condaBase" } else { Write-Host 'Found conda:       (none)' }
if ($python312) { Write-Host "Found Python 3.12: $python312" } else { Write-Host 'Found Python 3.12: (none)' }
Write-Host ''

if (-not $Flow) {
    $defaultChoice = '2'
    if ($condaBase -or -not $python312) { $defaultChoice = '1' }
    Write-Host 'How do you want to install the toolkit environment?'
    Write-Host '  1) conda          (environment.yml - recommended; required for the desktop GUI)'
    Write-Host '  2) Python + pip   (python.org Python 3.12 + requirements.txt; command-line toolkit only)'
    $choice = Ask 'Choice' $defaultChoice
    if ($choice -eq '2') { $Flow = 'venv' } else { $Flow = 'conda' }
}

$parentDir = Split-Path $RepoDir -Parent
if ($Flow -eq 'conda') {
    if (-not $condaBase) {
        $condaBase = Ask 'Path to your Anaconda/Miniconda install folder' 'C:\ProgramData\Anaconda3'
    }
    $condaExe = Join-Path $condaBase 'Scripts\conda.exe'
    $activateBat = Join-Path $condaBase 'Scripts\activate.bat'
    if (-not (Test-Path $condaExe) -or -not (Test-Path $activateBat)) {
        throw "No conda installation found at $condaBase (expected Scripts\conda.exe and Scripts\activate.bat)."
    }
    if (-not $EnvPath) { $EnvPath = Ask 'Folder for the toolkit-env conda environment' (Join-Path $parentDir 'toolkit-env') }
    $pythonExe = Join-Path $EnvPath 'python.exe'
    if (Test-Path $pythonExe) {
        Write-Host "`nAn environment already exists at $EnvPath."
        if (AskYN 'Update it from environment.yml (conda env update --prune)?' $false) {
            Invoke-Checked $condaExe @('env', 'update', '-p', $EnvPath, '-f', (Join-Path $RepoDir 'environment.yml'), '--prune')
        }
    } else {
        Invoke-Checked $condaExe @('env', 'create', '-p', $EnvPath, '-f', (Join-Path $RepoDir 'environment.yml'))
    }
    $activateLine = "call `"$activateBat`" `"$EnvPath`""
} else {
    if (-not $python312) {
        Write-Host 'Python 3.12 was not found. Install it from https://www.python.org/downloads/windows/'
        Write-Host '(choose a 3.12.x release - NOT 3.13 or newer), or give the path to an existing python.exe.'
        $python312 = Ask 'Path to python.exe (3.12)' 'C:\Program Files\Python312\python.exe'
    }
    $baseVersion = Get-PythonVersion $python312
    if ($baseVersion -ne $RequiredPython) {
        throw "$python312 is Python $baseVersion; the toolkit requires Python $RequiredPython exactly."
    }
    if (-not $EnvPath) { $EnvPath = Ask 'Folder for the toolkit virtual environment' (Join-Path $parentDir 'toolkit-venv') }
    $pythonExe = Join-Path $EnvPath 'Scripts\python.exe'
    if (Test-Path $pythonExe) {
        Write-Host "`nA virtual environment already exists at $EnvPath."
        $install = AskYN 'Re-run pip install -r requirements.txt in it?' $false
    } else {
        Invoke-Checked $python312 @('-m', 'venv', $EnvPath)
        $install = $true
    }
    if ($install) {
        Invoke-Checked $pythonExe @('-m', 'pip', 'install', '--upgrade', 'pip')
        Invoke-Checked $pythonExe @('-m', 'pip', 'install', '-r', (Join-Path $RepoDir 'requirements.txt'))
    }
    $activateLine = "call `"$(Join-Path $EnvPath 'Scripts\activate.bat')`""
}

$envVersion = Get-PythonVersion $pythonExe
if ($envVersion -ne $RequiredPython) {
    throw "The environment at $EnvPath has Python $envVersion; the toolkit requires Python $RequiredPython exactly."
}
Write-Host "`nEnvironment OK: $pythonExe (Python $envVersion)" -ForegroundColor Green

$writeConfig = $true
if (Test-Path $LocalEnvFile) {
    Write-Host "`nExisting local_env.cmd:"
    Get-Content $LocalEnvFile | ForEach-Object { Write-Host "    $_" }
    $writeConfig = AskYN 'Replace it?' $true
}
if ($writeConfig) {
    $lines = @(
        "@rem Generated by setup_toolkit.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm') ($Flow flow).",
        '@rem Machine-specific (git-ignored): activates the toolkit environment for',
        '@rem start_ted_toolkit.bat and regression_test.bat. Delete it to fall back to their defaults.',
        $activateLine
    )
    # cmd.exe reads .cmd files in the console's OEM code page, not UTF-8.
    $oem = [System.Text.Encoding]::GetEncoding([System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
    [System.IO.File]::WriteAllLines($LocalEnvFile, $lines, $oem)
    Write-Host "Wrote $LocalEnvFile" -ForegroundColor Green
}

if ($Flow -eq 'venv') {
    Write-Host "`nNOTE: the desktop GUI (start_ted_toolkit_gui.bat) currently supports the conda flow only." -ForegroundColor Yellow
} else {
    $guiConfig = Get-Content (Join-Path $RepoDir 'toolkit_gui\config.py') -Raw
    if ($guiConfig -notmatch [regex]::Escape($EnvPath) -or $guiConfig -notmatch [regex]::Escape($activateBat)) {
        Write-Host "`nNOTE: to use the desktop GUI, set ACTIVATE_BAT / ENV_PATH / TOOLKIT_PY in" -ForegroundColor Yellow
        Write-Host '      toolkit_gui\config.py and the paths in start_ted_toolkit_gui.bat to:' -ForegroundColor Yellow
        Write-Host "      $activateBat"
        Write-Host "      $EnvPath"
        Write-Host "      $(Join-Path $RepoDir 'ted_toolkit.py')"
    }
}

if (AskYN "`nRun the regression test suite now?" $false) {
    & $pythonExe (Join-Path $RepoDir 'run_regression_tests.py')
}

Write-Host "`nSetup complete. Start the toolkit with start_ted_toolkit.bat." -ForegroundColor Green
