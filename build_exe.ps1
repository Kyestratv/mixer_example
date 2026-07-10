param(
    [string]$AppName = "MixerSpectrumDemo",
    [string]$EntryPoint = "mixer_gui.py"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

$PythonExe = (Get-Command python).Source
$PythonRoot = Split-Path -Parent $PythonExe
$TclRoot = Join-Path $PythonRoot "tcl"
$RuntimeTcl = Join-Path $ProjectRoot "runtime_tcl"

$TclSource = Join-Path $TclRoot "tcl8.6"
$TkSource = Join-Path $TclRoot "tk8.6"

if (-not (Test-Path $EntryPoint)) {
    throw "Entry point not found: $EntryPoint"
}
if (-not (Test-Path $TclSource)) {
    throw "Tcl runtime not found: $TclSource"
}
if (-not (Test-Path $TkSource)) {
    throw "Tk runtime not found: $TkSource"
}

$ExistingProcess = Get-Process -Name $AppName -ErrorAction SilentlyContinue
if ($ExistingProcess) {
    Write-Host "Stopping running $AppName process before rebuilding..."
    $ExistingProcess | Stop-Process -Force
    Start-Sleep -Seconds 1
}

Write-Host "Using Python: $PythonExe"
Write-Host "Preparing Tcl/Tk runtime..."

New-Item -ItemType Directory -Force -Path $RuntimeTcl | Out-Null
Copy-Item -Recurse -Force -Path $TclSource -Destination $RuntimeTcl
Copy-Item -Recurse -Force -Path $TkSource -Destination $RuntimeTcl

Write-Host "Checking PyInstaller..."
try {
    & $PythonExe -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller check failed"
    }
} catch {
    Write-Host "PyInstaller is not installed. Installing it with pip..."
    Invoke-Native $PythonExe @("-m", "pip", "install", "pyinstaller")
}

Write-Host "Building $AppName.exe..."
Invoke-Native $PythonExe @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", $AppName,
    "--runtime-hook", "pyinstaller_runtime_hook.py",
    "--add-data", "runtime_tcl;runtime_tcl",
    $EntryPoint
)

$ExePath = Join-Path $ProjectRoot "dist\$AppName.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build finished but exe was not found: $ExePath"
}

Write-Host "Built: $ExePath"
