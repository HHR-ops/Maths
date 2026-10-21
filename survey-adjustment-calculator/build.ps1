$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskTemp = Join-Path $PSScriptRoot '.tmp'
New-Item -ItemType Directory -Path $taskTemp -Force | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.build-cache'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv --system-site-packages .venv
    if ($LASTEXITCODE -ne 0) { throw '创建构建环境失败。' }
    & $taskPython -m pip install -r requirements.txt pyinstaller==6.22.3
    if ($LASTEXITCODE -ne 0) { throw '安装构建依赖失败。' }
}
& $taskPython -m pip install -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw '安装构建依赖失败。' }
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw '安装 React 构建依赖失败。' }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'React 构建失败。' }
} finally { Pop-Location }
& $taskPython -m unittest -v test_adjustment test_network test_desktop test_v05 test_theory
if ($LASTEXITCODE -ne 0) { throw '计算测试失败，停止打包。' }
& $taskPython tools\prepare_notices.py
if ($LASTEXITCODE -ne 0) { throw '第三方许可收集失败。' }
& $taskPython tools\build_theory_docs.py
if ($LASTEXITCODE -ne 0) { throw '理论手册生成失败。' }
& $taskPython -m PyInstaller --noconfirm --onefile --windowed --name '测量平差工作台-v0.6.1-React' --icon 'assets/app.ico' --add-data 'frontend/web-dist:frontend/web-dist' --add-data 'THIRD_PARTY_NOTICES.md:.' --exclude-module torch --exclude-module tensorflow --exclude-module jax --exclude-module jaxlib --exclude-module cupy --exclude-module numba --exclude-module dask --exclude-module matplotlib --exclude-module pandas --exclude-module IPython --exclude-module PIL --exclude-module tkinter --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide6 desktop.py
if ($LASTEXITCODE -ne 0) { throw 'EXE 打包失败。' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $PSScriptRoot 'dist\README.md') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $PSScriptRoot 'dist\THIRD_PARTY_NOTICES.md') -Force
Write-Host '已生成 dist\测量平差工作台-v0.6.1-React.exe'
