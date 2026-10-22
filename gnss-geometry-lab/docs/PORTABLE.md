# Windows 便携版使用说明

解压 GNSSGeometryLab-v0.2.0-Windows-x64.zip，双击 GNSS交互实验室-v0.2.0.exe。

目标电脑需要 Windows 10/11 x64、.NET Framework 4.6.2 或更高版本，以及 Microsoft Edge WebView2 Runtime。运行无需 Python、Node.js 或网络。缺少 WebView2 时可从 [微软官方网站](https://developer.microsoft.com/microsoft-edge/webview2/) 安装；离线电脑可预先带上 x64 Evergreen Standalone Installer。

程序内嵌前端与 Python 桌面宿主。依赖目录、源码和开发环境不需要复制到目标电脑。分发时请保留 LICENSE 与 THIRD_PARTY_NOTICES.md。

## 保存与迁移

“保存项目”生成 .gnss.json 文件，包含卫星、截止角、精度设置、遮挡和对照场景。将项目文件带到另一台电脑，在程序中点击“打开”即可继续编辑。

轨迹状态、噪声样本、SP3 全部历元及站点输入不会写入项目文件。保存的是当前显示的方向帧；继续 SP3 播放需要在新会话中重新导入文件和设置站点。

自动草稿位于 %LOCALAPPDATA%/GnssGeometryLab/workspace.json。此目录独立于测量平差计算器，且不会随 EXE 自动迁移。PNG 和 CSV 是导出成果，继续编辑应保存项目文件。

## 校验

同目录的 SHA256SUMS.txt 包含 EXE 与压缩包的 SHA-256。可在 PowerShell 使用 Get-FileHash -Algorithm SHA256 -LiteralPath 后接文件路径进行比对。

## 当前验证范围

开发电脑使用 Windows x64 和 Edge WebView2；计算通过 24 组前端测试（含 40 组独立 NumPy 参考），桌面宿主通过 9 组测试，浏览器流程通过 13 组检查。最终 EXE 另检查真实窗口、原生桥接、DOP、秩退化、JSON/PNG 导出和正常退出。

三维视图需要 WebGL 2。图形环境不能创建三维视图时会提示原因，天空图与计算仍可使用。尚未在另一台干净电脑上实测。
