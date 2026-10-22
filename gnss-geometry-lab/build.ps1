$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskTemp = Join-Path $PSScriptRoot '.tmp'
New-Item -ItemType Directory -Path $taskTemp -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'qa') -Force | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.build-cache'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败。' }
}
& $taskPython -m pip install -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw '安装构建依赖失败。' }
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw '安装前端依赖失败。' }
    }
    npm test
    if ($LASTEXITCODE -ne 0) { throw '计算检查失败。' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败。' }
} finally { Pop-Location }
& $taskPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '桌面接口检查失败。' }
& $taskPython tools\prepare_notices.py
if ($LASTEXITCODE -ne 0) { throw '许可收集失败。' }
& $taskPython -m PyInstaller --noconfirm --onefile --windowed --name 'GNSS交互实验室-v0.2.0' --icon assets/app.ico --add-data 'frontend/web-dist:frontend/web-dist' --exclude-module numpy --exclude-module scipy --exclude-module torch --exclude-module tensorflow --exclude-module jax --exclude-module jaxlib --exclude-module cupy --exclude-module numba --exclude-module dask --exclude-module matplotlib --exclude-module pandas --exclude-module IPython --exclude-module PIL --exclude-module tkinter --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide6 desktop.py
if ($LASTEXITCODE -ne 0) { throw 'EXE 打包失败。' }
foreach ($name in @('LICENSE','README.md','THIRD_PARTY_NOTICES.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $PSScriptRoot ('dist\'+$name)) -Force
}
& $taskPython tools\package_release.py
if ($LASTEXITCODE -ne 0) { throw '便携压缩包或校验生成失败。' }
Write-Host '已生成 dist\GNSS交互实验室-v0.2.0.exe'
