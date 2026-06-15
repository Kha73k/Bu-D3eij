<#
  test-sandbox.ps1 - launch the compiled installer in a clean Windows Sandbox.

  Maps installer\dist (read-only) to C:\Setup inside a fresh, disposable Windows
  (no Python, no ffmpeg, no model cache - a true cold-start) and opens it.

  Requires Windows Sandbox enabled (one-time): "Turn Windows features on or off"
  -> Windows Sandbox -> restart  (Win10/11 Pro; needs virtualization in BIOS).

  Usage:  powershell -ExecutionPolicy Bypass -File installer\test-sandbox.ps1
#>
$ErrorActionPreference = "Stop"
$dist = Join-Path $PSScriptRoot "dist"
$exe  = Join-Path $dist "BuD3eij-Setup.exe"

if (-not (Test-Path $exe)) {
  throw "BuD3eij-Setup.exe not found in $dist - compile installer\bud3eij.iss first (Inno Setup F9)."
}
if (-not (Get-Command "WindowsSandbox.exe" -ErrorAction SilentlyContinue)) {
  throw "Windows Sandbox is not enabled. Enable it in 'Turn Windows features on or off' -> Windows Sandbox -> restart."
}

$wsb = Join-Path $env:TEMP "bud3eij-test.wsb"
@"
<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$dist</HostFolder>
      <SandboxFolder>C:\Setup</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>explorer.exe C:\Setup</Command>
  </LogonCommand>
</Configuration>
"@ | Set-Content -Path $wsb -Encoding ASCII

Write-Host "Launching Windows Sandbox; the installer is at C:\Setup inside it."
Write-Host "Run BuD3eij-Setup.exe there, install (pick Core or Vanguard for a fast test), and launch."
Start-Process $wsb
