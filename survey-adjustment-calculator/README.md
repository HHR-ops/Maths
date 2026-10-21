# 测量平差工作台 v0.6 · React 桌面版

从 [GitHub Releases](https://github.com/HHR-ops/Maths/releases/tag/survey-adjustment-v0.6.0) 下载 Windows x64 压缩包，解压后双击 `测量平差工作台-v0.6-React.exe`。本地构建产物位于 `dist`，运行无需安装 Python 或 Node.js。
此版本使用 React + TypeScript + Vite 重做界面，使用本机 WebView2 显示窗口，沿用 Python / NumPy 平差内核。
运行环境为 64 位 Windows 10 / 11、.NET Framework 4.6.2 或更高版本，以及 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。环境齐全后可以离线使用。
旧 Tk 界面源码保留供对照。Git 仓库存放源码与说明，EXE 和便携压缩包通过 Releases 分发。

![控制网工作台](docs/screenshots/workbench.png)

跨电脑使用与项目迁移见 [便携版使用说明](docs/PORTABLE.md)。

## v0.6 新增

- **离线理论库**：六章十三篇，涵盖误差基础、误差传播、最小二乘、统计与模型检验、精度和质量、误差椭圆。
- **公式与学习工具**：本地公式字体、全文检索、符号速查、手算例题、逐篇自测与原始资料链接。
- **交互例题与成果联动**：正态分布、相关传播、加权平均、χ² 检验与置信椭圆；从结果页进入理论后可返回继续计算。

操作与验证见 [v0.6 使用说明](docs/V06.md)，完整知识手册见 [理论与知识](docs/THEORY.md)。

## v0.5 新增

- **批量导入**：Excel / CSV / TSV、列映射、单位转换、GNSS 协方差、逐行错误预览，确认后一次性写入。
- **分步计算**：观测与参数、线性化、定权、所选模型、法方程、迭代、精度传播；矩阵标签可定位画布对象，并支持四法对照。
- **统计诊断**：先验尺度下的整体 χ² 检验、标准化残差与相关观测块检验，采用 Holm 校正；可停用疑似观测并比较复算前后结果。

操作、统计假设与测试范围见 [v0.5 使用说明](docs/V05.md)。

## 界面与开源参考

- 参考 [satnaing/shadcn-admin](https://github.com/satnaing/shadcn-admin) 的侧栏与工作区布局。
- 按 [shadcn/ui](https://github.com/shadcn-ui/ui) 的组件模式适配按钮；使用 Radix Dialog、Lucide 图标。
- 统一字体、细边框、按钮高度、图标尺寸与留白。中央为交互画布，右侧编辑对象和计算设置，下方切换数据、矩阵、精度与报告。
- 不加载在线字体、不连接云端服务。计算接口仅监听本机回环地址，并校验随机会话令牌与请求来源。
- 参考来源、MIT 许可和运行时依赖许可见 `THIRD_PARTY_NOTICES.md`；版本固定在 `frontend/package-lock.json`。

## 控制网工作台

支持水准网、导线网、GNSS 网、测边网、测角网、边角网、坐标观测网。平面网可组合距离、水平角、方位角、坐标观测。

1. 选择网型，载入对应示例，或点击“新建”创建空网。切换网型会载入对应示例，并提示替换已有修改。
2. 画布左侧 ＋ 添加点；选择工具拖动点改变近似坐标；拖动空白处平移，滚轮缩放。“适应画布”恢复完整网形。
3. 在右侧输入坐标，逐分量设置精确固定值，再点击“应用坐标”。水准网的 X、Y 只用于示意，H 参与计算。
4. 用观测工具依次点击端点。水平角按“后视点 → 测站 → 前视点”，坐标观测只需选择一个点。
5. 双击观测表或点击编辑按钮，填写实测值和标准差；支持停用观测。GNSS 填 ΔX、ΔY、ΔZ，可输入公共/各分量标准差或完整 3×3 协方差阵。
6. 右侧选择条件平差、附有参数的条件平差、间接平差或附有限制条件的间接平差。
7. 点击“计算精度”或“计算平差”，在下方查看点位精度、相对精度、实测改正数、矩阵和报告。

布网设计无需实测值，由网形与标准差计算先验精度，σ₀=1；不会由几何模拟值的零残差推断零误差。
实测平差要求每条启用观测均有实测值，距离与角度模型通过迭代求解。实测模式中点击“示例”可载入含实测值的例题。

### 实时统计与矩阵

- n：启用的标量观测分量数；GNSS 一条基线计 3，二维坐标观测计 2，高差、距离、水平角计 1。
- u：未固定的坐标参数数；固定坐标已消去，不重复计入独立限制数 c。
- c：独立精确限制的秩；t：限制消元后加权观测系数的秩；r=n−t。
- 基准/几何亏损=u−c−t。亏损非零时需增加固定坐标、独立限制或有效观测，不任意给出唯一坐标解。
- B、P、Q、N=BᵀPB 与法方程右端项自动生成。计算后增加 Qxx、Qvv、观测平差值协因数及参数协方差。
- 实测值不完整时，仅显示网形系数和权，暂不生成对应常数项与闭合差。
- 结果矩阵在最终坐标处线性化，同时保留首次 B₀、l₀。表格预览最多 80 行 × 40 列，复制、CSV 和 JSON 保留完整数值。

“提取至矩阵工作台”提取当前近似坐标处的一次线性化模型，保留权、观测值、参数初值与精确限制。存在限制的间接模型会提取为附限间接模型。
条件法的 A 为左零空间生成的等价线性化条件基，不保证每行对应一个几何闭合环。附参条件法保留全部自由参数；有精确限制时先消元，提取后的参数是零空间坐标 z，不能直接视为各点坐标。
非线性网的最终坐标应在控制网工作台迭代计算。

### 限制条件

点击“限制条件”，每行填写一式，例如：

```text
B.H:1 C.H:1 = 203.2
```

左侧格式为“点名.分量:系数”，右侧是绝对坐标组合值，不是改正数。固定值与近似坐标自动折入 d。
限制应相互独立。设计模式中的名义坐标需满足精确限制；实测平差可通过迭代满足限制。

### 保存、导出与恢复

- 控制网项目保存为 `.net.json`，矩阵项目保存为 `.sap.json`，支持重新打开旧版项目。
- 计算报告页导出 TXT 报告、CSV 点位成果和完整 JSON 结果；矩阵可单独导出 CSV。
- 桌面版使用系统保存对话框。工作草稿自动保存在 `%LOCALAPPDATA%/SurveyAdjustmentWorkbench/workspace.json`，下次启动可恢复；仍建议用“保存项目”保存正式文件。
- Ctrl+S 保存；Ctrl+Z 撤销；Ctrl+Shift+Z 重做；Delete 删除选中对象。删除控制点会一并删除关联观测和限制，可撤销恢复。

### 坐标、精度与计算范围

长度与标准差使用米；角度值使用十进制度或 `123:45:56.7`；角度标准差使用角秒。角度协方差阵使用 rad²，角度方程内部使用弧度。P 由输入标准差/协方差生成，Q=P⁻¹，各观测块之间按不相关处理。

平面坐标 X 北、Y 东。GNSS 坐标、ΔX/ΔY/ΔZ 和协方差必须在同一 XYZ 直角框架中，可以是地心框架。GNSS 精度包含 XYZ 分量和三维点位中误差；画布与误差椭圆仅为 XY 投影，椭圆方向从 +X 向 +Y。不自动进行 ENU、地心坐标、投影或高程基准转换。

误差椭圆为 1σ 半轴，不表示联合 68% 置信区间；画布按最大半轴/高程标准差统一放大显示。相对精度包含参数间协方差。
无多余观测时后验精度不可估计，可使用先验标准差。非线性网依赖合理近似坐标；不处理原始卫星观测、仪器系统误差、地球曲率或投影改正。
当前最多 120 个点、500 个标量观测/参数，采用稠密矩阵。

## 矩阵工作台

| 模型 | 方程 | 自由度 f |
| --- | --- | --- |
| 条件平差 | A v + w = 0 | 条件方程数 k |
| 附有参数的条件平差 | A v + B x + w = 0 | k − 参数数 u |
| 间接平差 | v = B x − l | n − u |
| 附有限制条件的间接平差 | v = B x − l，C x + d = 0 | n − u + c |

约定 v=平差值−观测值，目标 min vᵀPv。矩阵页统计统一显示 t=n−f，r=f；结果 JSON 中 t 为模型参数数，r 是条件方程数（条件法）或限制数（间接法），dof 为自由度，以字段约定为准。

每种模型均有可直接运行的例题。输入支持从 Excel 粘贴，空格/Tab/逗号分列，换行/分号分行，科学计数法及 # 注释。不接受表达式。
输入的是权阵 P，不是协因数 Q。支持等权、对角权、完整正定权阵。
可选 L 用于显示 L̂=L+v；X₀ 仅在 x 为改正数时填写，用于输出 X̂=X₀+x。

Cov=所选 σ₀²×Q。可采用先验 σ₀，或后验 σ̂₀=sqrt(vᵀPv/f)。自由度为零时无法估计后验精度。
矩阵页处理线性或已经线性化的方程，不自动转换单位；自动列式与迭代由控制网工作台完成。

## 开发与验证

需要 Python 3.13、Node.js 22.12+，以及 Windows WebView2 Runtime。构建依赖的具体版本见 requirements.txt 与 package-lock.json。

```powershell
python -m venv --system-site-packages .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt pyinstaller==6.22.3
Set-Location frontend
npm ci
npm run build
Set-Location ..
.venv/Scripts/python.exe desktop.py
```

React 修改后执行 `npm run build`，重启桌面程序即可。浏览器联调使用 `python desktop.py --serve --port 8877`，再打开其输出的回环地址；浏览器模式不向桌面草稿目录写入数据。
需要热更新时，先启动上述 8877 端口的 Python 服务，再在 frontend 中执行 `npm run dev`；Vite 会代理本地计算接口。生产桌面版始终使用已构建产物。

- `python -m unittest -v test_adjustment test_network test_desktop test_v05 test_theory`：计算内核、几何雅可比、GNSS 相关协方差、四法一致性、JSON/API 边界、矩阵提取、草稿持久化与会话访问校验。
- 在 frontend 执行 `npm run test:e2e`：实际 Edge 中验证画布交互、实时统计、七类网与四法、实测 GNSS、输入错误、结果失效、项目与导出、多个窗口尺寸。
- `python desktop.py --self-test <输出JSON>`：七类实测网 × 四种方法、四个矩阵例题、七类 Excel 模板和已知模拟粗差的打包后验证。
- `python desktop.py --ui-self-test <输出JSON>`：实际 React 桌面窗口、Python 桥接、精度计算与原生文件导出冒烟验证；会短暂打开窗口后自动关闭。
- `powershell -ExecutionPolicy Bypass -File build.ps1`：构建 React，运行 Python 测试，生成单文件 Windows EXE，复制说明与第三方许可。

旧 Tk 界面仍可通过 `python app.py` 运行；其源码与旧 EXE 保留供对照。

## 计算参考

- [Ohio State University — Notes on Adjustment Computations，第 3–5、9 章](https://earthsciences.osu.edu/sites/default/files/OSU_Adjustment_Notes_Part_1_0.pdf)
- [GNU Gama — Network adjustment with gama-local](https://www.gnu.org/s/gama/manual/html_node/Network-adjustment-with-gama_002dlocal.html)

求解采用 Cholesky 白化、SVD 与零空间消元；法方程矩阵供复核。参考资料的 A/B 命名与残差符号可能不同，以本程序的方程为准。
