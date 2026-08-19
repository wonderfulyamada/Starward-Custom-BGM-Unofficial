param(
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"
$appDir = Join-Path $distDir "StarwardBGM"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Tk-capable Python interpreter not found: $Python"
}
$pythonRoot = Split-Path -Parent (Resolve-Path -LiteralPath $Python)
$env:TCL_LIBRARY = Join-Path $pythonRoot "tcl\tcl8.6"
$env:TK_LIBRARY = Join-Path $pythonRoot "tcl\tk8.6"

& $Python -c "import os, sys, tkinter; print('sys.executable =', sys.executable); print('Python version =', sys.version); print('tkinter.TclVersion / TkVersion =', tkinter.TclVersion, '/', tkinter.TkVersion); print('TCL_LIBRARY =', os.environ.get('TCL_LIBRARY')); print('TK_LIBRARY =', os.environ.get('TK_LIBRARY')); root = tkinter.Tk(); print('loaded Tcl library =', root.tk.eval('info library')); print('loaded Tcl patchlevel =', root.tk.eval('info patchlevel')); print('loaded Tk library =', root.tk.eval('set tk_library')); print('loaded Tk patchlevel =', root.tk.eval('set tk_patchLevel')); root.destroy(); print('tkinter.Tk() create/destroy = PASS')"
if ($LASTEXITCODE -ne 0) {
    throw "Build interpreter cannot initialize tkinter/Tcl-Tk: $Python"
}
Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue
& $Python -m pip install -r (Join-Path $projectRoot "requirements.txt") pyinstaller
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name StarwardBGM `
    --paths $projectRoot --collect-all pygame --collect-all mss `
    --workpath $buildDir --distpath $distDir (Join-Path $projectRoot "launcher.py")

Copy-Item (Join-Path $projectRoot "config.json") (Join-Path $appDir "config.json") -Force
New-Item -ItemType Directory -Path (Join-Path $appDir "BGM") -Force | Out-Null
Copy-Item (Join-Path $projectRoot "BGM\README.txt") (Join-Path $appDir "BGM\README.txt") -Force
@'
{
  "version": 2,
  "groups": {
    "デフォルト": []
  }
}
'@ | Set-Content -LiteralPath (Join-Path $appDir "bgm_library.json") -Encoding utf8
New-Item -ItemType Directory -Path (Join-Path $appDir "templates") -Force | Out-Null
Copy-Item (Join-Path $projectRoot "templates\README.txt") (Join-Path $appDir "templates\README.txt") -Force
