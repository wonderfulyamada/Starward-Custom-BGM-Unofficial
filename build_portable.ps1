param(
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
)

$ErrorActionPreference = "Stop"
$ReleaseVersion = "0.2.2"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"
$appDir = Join-Path $distDir "StarwardBGM"
Write-Host "Preparing StarwardBGM v$ReleaseVersion"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Tk-capable Python interpreter not found: $Python"
}
$pythonRoot = Split-Path -Parent (Resolve-Path -LiteralPath $Python).Path
$tclLibrary = Join-Path $pythonRoot "tcl\tcl8.6"
$tkLibrary = Join-Path $pythonRoot "tcl\tk8.6"
foreach ($requiredFile in @(
    (Join-Path $tclLibrary "init.tcl"),
    (Join-Path $tkLibrary "tk.tcl")
)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Build interpreter Tcl/Tk file is missing: $requiredFile"
    }
}
# Scope these overrides to the build process.  Never require persistent
# user-level TCL_LIBRARY or TK_LIBRARY settings.
$env:TCL_LIBRARY = $tclLibrary
$env:TK_LIBRARY = $tkLibrary
Write-Host "Using Tcl library: $env:TCL_LIBRARY"
Write-Host "Using Tk library: $env:TK_LIBRARY"

& $Python -E -c "import os, sys, tkinter; print('sys.executable =', sys.executable); print('Python version =', sys.version); print('tkinter.TclVersion / TkVersion =', tkinter.TclVersion, '/', tkinter.TkVersion); print('TCL_LIBRARY =', os.environ.get('TCL_LIBRARY')); print('TK_LIBRARY =', os.environ.get('TK_LIBRARY')); root = tkinter.Tk(); print('loaded Tcl library =', root.tk.eval('info library')); print('loaded Tcl patchlevel =', root.tk.eval('info patchlevel')); print('loaded Tk library =', root.tk.eval('set tk_library')); print('loaded Tk patchlevel =', root.tk.eval('set tk_patchLevel')); root.destroy(); print('tkinter.Tk() create/destroy = PASS')"
if ($LASTEXITCODE -ne 0) {
    throw "Build interpreter cannot initialize tkinter/Tcl-Tk: $Python"
}
Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue
& $Python -m pip install -r (Join-Path $projectRoot "requirements.txt") pyinstaller
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name StarwardBGM `
    --paths $projectRoot --collect-all mss `
    --workpath $buildDir --distpath $distDir (Join-Path $projectRoot "launcher.py")

# Do not package settings from this developer's working tree.  The committed
# default configuration is the distributable baseline.
$releaseConfig = & git -C $projectRoot show HEAD:config.json
if ($LASTEXITCODE -ne 0) {
    throw "Could not read committed default config.json"
}
$releaseConfig = $releaseConfig | ConvertFrom-Json
$releaseConfig.app_version = $ReleaseVersion
$releaseConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $appDir "config.json") -Encoding utf8
New-Item -ItemType Directory -Path (Join-Path $appDir "BGM\Default") -Force | Out-Null
@'
{
  "version": 2,
  "groups": {
    "Default": []
  }
}
'@ | Set-Content -LiteralPath (Join-Path $appDir "bgm_library.json") -Encoding utf8
New-Item -ItemType Directory -Path (Join-Path $appDir "templates") -Force | Out-Null
Copy-Item (Join-Path $projectRoot "templates\README.txt") (Join-Path $appDir "templates\README.txt") -Force

$zipPath = Join-Path $projectRoot "Starward-Custom-BGM-Unofficial-v$ReleaseVersion.zip"
if (Test-Path -LiteralPath $zipPath) {
    throw "Release ZIP already exists and will not be overwritten: $zipPath"
}
Compress-Archive -LiteralPath $appDir -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "Created release ZIP: $zipPath"
