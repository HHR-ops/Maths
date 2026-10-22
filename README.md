# Maths

数学与测量计算小工具合集，包含源码、使用说明、测试与 Windows 便携版。每个项目在独立目录中维护。

| 项目 | 用途 | 平台 | 下载 |
| --- | --- | --- | --- |
| [测量平差工作台](survey-adjustment-calculator/README.md) | 七类控制网、四种平差方法、精度与统计分析 | Windows 10/11 x64 | [最新便携版](https://github.com/HHR-ops/Maths/releases/tag/survey-adjustment-v0.6.3) |
| [GNSS 交互实验室](gnss-geometry-lab/README.md) | 卫星几何、DOP、误差区域、动态与噪声实验、SP3 历元 | Windows 10/11 x64 | [v0.2.0 便携版](https://github.com/HHR-ops/Maths/releases/tag/gnss-geometry-lab-v0.2.0) |

## 测量平差工作台

[项目源码与使用说明](survey-adjustment-calculator/README.md) · [Windows 便携版下载](https://github.com/HHR-ops/Maths/releases/tag/survey-adjustment-v0.6.3)

基于 React + TypeScript 的本地桌面工作台，支持七类控制网布设、四种平差方法、自动矩阵建模和精度评估。支持 Excel / CSV 批量导入、分步计算、四法对照与统计诊断。v0.6 提供六章十三篇离线理论、交互例题、自测与成果说明入口；v0.6.1 优化文字对比度、按钮轮廓与浅色滚动条；v0.6.2 润色章节表述、参数计数与检验说明；v0.6.3 增加七套不同的典型控制网、实时统计与保留基准限制的导入模板。

![控制网工作台](survey-adjustment-calculator/docs/screenshots/workbench.png)

## GNSS 交互实验室

[项目源码与使用说明](gnss-geometry-lab/README.md) · [Windows 便携版下载](https://github.com/HHR-ops/Maths/releases/tag/gnss-geometry-lab-v0.2.0)

黑金主题的 React / TypeScript / Three.js 本地实验工具。支持天空图与三维半球联动、五类 DOP、标准及 95% 误差区域、统一比例尺和 A/B 相机联动。提供独立模拟轨迹与 DOP 曲线、固定种子的测距噪声点云，以及本地 SP3-c/d 单星座位置历元导入和站点设置。

模拟轨迹属于教学构造；SP3 按文件离散历元显示，不作轨道预报或完整定位解算。项目独立维护，操作和模型约定见 [实验指南](gnss-geometry-lab/docs/EXPERIMENTS.md) 与 [数学模型](gnss-geometry-lab/docs/MODEL.md)。

![GNSS 交互实验室](gnss-geometry-lab/docs/screenshots/lab.png)

## 反馈与参与

欢迎通过 [Issues](https://github.com/HHR-ops/Maths/issues) 反馈问题或提出建议，也欢迎提交 Pull Request。计算问题请提供程序版本、复现步骤、预期结果与可公开的最小示例；开发和测试方法见各项目的 README。

## 许可证

除各项目或第三方文件另有说明外，仓库原创代码采用 [MIT 许可证](LICENSE)，版权归 HHR-ops 所有。允许使用、修改、分发及商业使用，分发时须保留版权和许可声明。

第三方组件、字体及参考界面代码遵循各自许可证，详见 [测量平差工作台](survey-adjustment-calculator/THIRD_PARTY_NOTICES.md) 和 [GNSS 交互实验室](gnss-geometry-lab/THIRD_PARTY_NOTICES.md) 的第三方许可说明。
