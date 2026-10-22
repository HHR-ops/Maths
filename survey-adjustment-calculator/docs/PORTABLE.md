# Windows 便携版使用与迁移

1. 从 [测量平差工作台 v0.6.3 发布页](https://github.com/HHR-ops/Maths/releases/tag/survey-adjustment-v0.6.3) 下载 `SurveyAdjustment-v0.6.3-Windows-x64.zip`。
2. 解压到本机文件夹，双击 `测量平差工作台-v0.6.3-React.exe`。
3. 无需安装 Python、Node.js 或项目依赖。计算在本机完成，不需要联网。

目标电脑需要 64 位 Windows 10 / 11、.NET Framework 4.6.2 或更高版本、Microsoft Edge WebView2 Runtime。WebView2 缺失时，可从 [微软官方下载页](https://developer.microsoft.com/microsoft-edge/webview2/) 安装；需要全离线部署时选择 x64 Evergreen Standalone Installer，并预先带到目标电脑上安装。

程序 EXE 已内嵌前端、Python 解释器和计算内核，源码、虚拟环境与 node_modules 不需要复制。便携包同时附带 README、使用说明和第三方许可，分发时建议一并保留。

## 迁移已有项目

在原电脑点击“保存项目”，将控制网保存为 `.net.json`，或将矩阵模型保存为 `.sap.json`。把这些文件复制到新电脑，再点击程序中的“打开”载入。

自动草稿位于 `%LOCALAPPDATA%/SurveyAdjustmentWorkbench/workspace.json`，不会随 EXE 自动迁移。正式成果应保存为独立项目文件；结果 JSON、TXT 或 CSV 为导出成果，不替代可继续编辑的项目文件。

## 校验下载文件

发布页附带 `SHA256SUMS.txt`。可在 PowerShell 中计算压缩包校验值，与该文件中的同名条目比对：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .\SurveyAdjustment-v0.6.3-Windows-x64.zip
```

## 当前验证范围

- 95 项 Python 计算及接口测试。
- 17 组实际浏览器界面测试，覆盖七类网、四种方法、画布、项目读写及导出。
- 打包 EXE 的 45 项计算冒烟检查，以及原生窗口、桥接、计算、文件导出和正常退出检查。

已在开发电脑验证从 PATH 中移除 Python 和 Node 后运行；尚未在另一台干净电脑上完成实机测试。
