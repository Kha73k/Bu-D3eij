<#
  build.ps1 - stage the installer inputs into installer/build/, then you compile
  installer/bud3eij.iss with Inno Setup (ISCC.exe).

  Lays out installer/build/ to mirror the install layout:
      build/python/      relocatable standalone CPython 3.11 (python-build-standalone)
      build/app.py, build/bud3eij/, build/assets/, build/requirements/,
      build/bootstrap.py, theme/icons/licenses ...

  installer/build/ and installer/dist/ are git-ignored (the staged Python + the
  compiled setup are build artifacts, not source).

  STATUS: unverified end to end - the layout/URLs are correct by construction but
  have not been compiled/installed in this environment. Verify the PyRelease tag
  at https://github.com/astral-sh/python-build-standalone/releases (the asset is
  the '...-x86_64-pc-windows-msvc-install_only.tar.gz', which ships tkinter + pip).

  Usage:
      pwsh installer\build.ps1                  # download Python + stage app
      pwsh installer\build.ps1 -SkipPython      # re-stage app source only
#>
[CmdletBinding()]
param(
  [string]$PyVersion = "3.11.15",
  [string]$PyRelease = "20260610",   # python-build-standalone release tag (verified asset exists)
  [switch]$SkipPython
)
$ErrorActionPreference = "Stop"
$Root  = Split-Path -Parent $PSScriptRoot          # repo root
$Build = Join-Path $PSScriptRoot "build"
$Cache = Join-Path $Build "_cache"
$PyDir = Join-Path $Build "python"

New-Item -ItemType Directory -Force -Path $Build, $Cache | Out-Null

if (-not $SkipPython) {
  $asset = "cpython-$PyVersion+$PyRelease-x86_64-pc-windows-msvc-install_only.tar.gz"
  $url   = "https://github.com/astral-sh/python-build-standalone/releases/download/$PyRelease/$asset"
  $tar   = Join-Path $Cache $asset
  if (-not (Test-Path $tar)) {
    Write-Host "Downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $tar
  }
  if (Test-Path $PyDir) { Remove-Item -Recurse -Force $PyDir }
  Write-Host "Extracting standalone Python..."
  tar -xzf $tar -C $Build       # the install_only archive extracts to a top-level python/
  if (-not (Test-Path (Join-Path $PyDir "python.exe"))) {
    throw "python/python.exe not found after extract - check the archive layout/tag."
  }
}

# Copy the app source into the build root (mirrors the install layout).
$items = @("app.py","bud3eij","assets","requirements","bud3eij_theme.json",
           "AppLogo.ico","DashboardLogo.png","LICENSE","THIRD_PARTY.md",
           "SYSTEM_REQUIREMENTS.md","README.md")
foreach ($it in $items) {
  $src = Join-Path $Root $it
  if (-not (Test-Path $src)) { Write-Warning "missing source: $it"; continue }
  Copy-Item $src -Destination $Build -Recurse -Force
}
# bootstrap.py goes to the build root so the installer runs {app}\bootstrap.py.
Copy-Item (Join-Path $PSScriptRoot "bootstrap.py") -Destination $Build -Force

# Drop any stray __pycache__ that Copy-Item swept in.
Get-ChildItem $Build -Recurse -Directory -Filter "__pycache__" |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Staged -> $Build"
Write-Host "Next: compile installer\bud3eij.iss with Inno Setup (ISCC.exe) ->"
Write-Host "      installer\dist\BuD3eij-Setup.exe"
