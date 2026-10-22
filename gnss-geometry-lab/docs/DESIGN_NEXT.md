# 设计落实记录 · v0.2.0

2026-10-22，用户选定黑金主题，并授权落实交互可视化建议。

## 视觉

背景 #0B0B0D，面板 #161619，正文 #F2F1ED，辅助文本使用中性暖灰。金色 #D9B970 / #E1C27C 用于选择状态、关键指标、卫星与误差区域。遮挡使用珊瑚色，噪声点云使用浅蓝，与状态文字和图形共同区分。

早期黑紫草案未成为正式主题。当前截图与桌面版均为黑金。

## 已实现

- 自适应 / 固定比例，A/B 两侧使用相同物理范围和置信设置。
- A/B 三维、水平误差区域、相机联动与指标差值。
- ENU 方位、顶视图、编号避让、撤销 / 重做，一次拖动对应一次操作。
- 按需渲染、卫星几何体和材质复用、噪声点云缓冲区复用。
- 独立模拟轨迹、播放 / 暂停 / 单步、轨迹线与 DOP 曲线。
- 可复现的测距噪声仿真、散点、经验协方差与覆盖率。
- 本地 SP3-c/d 离散位置历元、WGS84 站点、单星座筛选。

RINEX、实时数据、完整定位解算、多系统钟差和观测权模型留待后续；不会借用当前单钟差的 DOP 名称表示尚未实现的复杂模型。

## 开源设计参考

- [Stanford-NavLab/gnss_lib_py](https://github.com/Stanford-NavLab/gnss_lib_py)：GNSS 解析、天空图与 DOP 数据组织；[DOP 文档](https://gnss-lib-py.readthedocs.io/en/latest/tutorials/utils/tutorials_dop_notebook.html)。
- [tomojitakasu/RTKLIB](https://github.com/tomojitakasu/RTKLIB)：GNSS 观测与结果图形分析的组织方式。
- [pmndrs/drei GizmoHelper](https://drei.docs.pmnd.rs/gizmos/gizmo-helper)：方向和相机操作的交互思路。
- [React Three Fiber 性能说明](https://r3f.docs.pmnd.rs/advanced/scaling-performance)：按需渲染和对象复用。

以上用于设计参考；本项目继续采用原有 Three.js 实现，没有复制参考项目代码或引入新依赖。静止重绘与连续编辑对象数量已检查，未宣称跨硬件帧率收益。

![黑金主题](screenshots/lab.png)
