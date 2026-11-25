<#
.SYNOPSIS  Build the portable Windows app (PyInstaller onedir) from a clean checkout.
.EXAMPLE   powershell -File packaging\build_windows.ps1            # output in %TEMP%\newsmon-build
.EXAMPLE   powershell -File packaging\build_windows.ps1 -Out D:\out
Needs: uv, and `uv sync --frozen` already run (or it is run here). PyInstaller is NOT a project dependency: it is added
only to the throwaway environment of `uv run --with`, so pyproject.toml and uv.lock are untouched.
#>
param(
    [string]$Out = (Join-Path $env:TEMP "newsmon-build"),
    [string]$PyInstallerVersion = "6.22.3",
    [switch]$Zip
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Push-Location $Repo
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    uv sync --frozen
    if ($LASTEXITCODE) { throw "uv sync failed" }
    uv run --frozen --with "pyinstaller==$PyInstallerVersion" pyinstaller --noconfirm --clean `
        --distpath (Join-Path $Out "dist") --workpath (Join-Path $Out "work") packaging\newsmon.spec
    if ($LASTEXITCODE) { throw "pyinstaller failed" }
    $dist = Join-Path $Out "dist\Newsmon"
    $sw.Stop()
    $mb = [math]::Round((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
    Write-Host ("built {0} ({1} MB) in {2:n0} s" -f $dist, $mb, $sw.Elapsed.TotalSeconds)
    if ($Zip) {
        $zipPath = Join-Path $Out "Newsmon-windows-x64.zip"
        if (Test-Path $zipPath) { Remove-Item $zipPath }
        Compress-Archive -Path $dist -DestinationPath $zipPath -CompressionLevel Optimal
        Write-Host ("zip {0} ({1} MB)" -f $zipPath, [math]::Round((Get-Item $zipPath).Length / 1MB, 1))
    }
} finally { Pop-Location }
