"""Reviewable equation stages, preserving the actual matrices of each method."""
from __future__ import annotations

import numpy as np
from adjustment import MODEL_NAMES, FORMULAS
from network import automatic_matrices


def entry(data, rows=None, columns=None):
    out = {'data': np.asarray(data).tolist()}
    if rows is not None: out['rows'] = rows
    if columns is not None: out['columns'] = columns
    return out


def _normal(method, A=None, B=None, w=None, l=None, C=None, d=None, P=None):
    w = None if w is None else np.asarray(w).reshape(-1)
    l = None if l is None else np.asarray(l).reshape(-1)
    d = None if d is None else np.asarray(d).reshape(-1)
    Q = np.linalg.solve(P, np.eye(len(P)))
    if method.startswith('condition'):
        S = A@Q@A.T
        matrices = {'S = A Q Aᵀ': entry(S)}
        if method == 'condition_parameters':
            matrices['增广系数 [S B; Bᵀ 0]'] = entry(np.block([[S, B], [B.T, np.zeros((B.shape[1], B.shape[1]))]]))
            matrices['右端项 [−w; 0]'] = entry(np.r_[-w, np.zeros(B.shape[1])])
            formula = '[S  B; Bᵀ  0] [k; x] = [−w; 0]，v = Q Aᵀ k'
        else:
            matrices['−w'] = entry(-w)
            formula = 'S k = −w，S = A Q Aᵀ，v = Q Aᵀ k'
    else:
        N, u = B.T@P@B, B.T@P@l
        matrices = {'N = Bᵀ P B': entry(N), 'u = Bᵀ P l': entry(u)}
        formula = 'N x = u，v = B x − l'
        if C is not None and len(C):
            matrices['增广系数 [N Cᵀ; C 0]'] = entry(np.block([[N, C.T], [C, np.zeros((len(C), len(C)))]]))
            matrices['右端项 [u; −d]'] = entry(np.r_[u, -d])
            formula = '[N  Cᵀ; C  0] [x; λ] = [u; −d]，v = B x − l'
    return {'id': 'normal', 'title': '建立法方程', 'formula': formula,
            'description': '展示法方程便于逐项复核；数值求解采用白化与 SVD，不直接求逆法方程。', 'matrices': matrices}


def network_steps(net, solution):
    m, first, r = solution.model, solution.initial_model, solution.result
    obs = [{'label': label, 'type': 'observation', 'id': identity}
           for identity, start, count in m.groups for label in m.labels[start:start+count]]
    params = [{'label': p+'.'+a, 'type': 'point', 'id': p} for p, a in m.keys]
    all_m = automatic_matrices(m)
    steps = [
        {'id': 'data', 'title': '整理观测与参数', 'formula': 'l₀ = L − f(X₀)',
         'description': '点坐标与长度为米；角度方程内使用弧度。固定分量已从未知参数中消去。设计模式的 L 为名义几何值。',
         'matrices': {'L · 方程中的观测向量': entry(first.L, obs), 'f(X₀) · 初始几何值': entry(first.predicted, obs),
                      'X₀ · 初始待估坐标': entry([net.points[p][a] for p, a in first.keys], params)}},
        {'id': 'linearize', 'title': '线性化与限制条件', 'formula': 'v = B₀ x − l₀；C x + d = 0',
         'description': 'B₀ 是观测函数在初始坐标处的雅可比。点击带观测标签的矩阵行，可以定位画布中的观测。',
         'matrices': {'B₀ · 初始观测系数': entry(first.B, obs, params), 'l₀ · 初始常数项': entry(first.l, obs),
                      'C · 精确限制系数': entry(first.C, columns=params), 'd₀ · 初始限制常数': entry(first.d)}},
        {'id': 'weights', 'title': '由精度生成权阵', 'formula': 'Cov(L) = σ₀² Q，P = Q⁻¹，网络先验 σ₀ = 1',
         'description': '不同观测块按不相关处理；GNSS 基线块可使用完整协方差阵描述分量间的相关性。P 与角度导数采用一致的内部单位。',
         'matrices': {'Q · 观测协因数': entry(m.Q, obs, obs), 'P · 权阵': entry(m.P, obs, obs)}}]
    method = net.method
    if method == 'condition':
        A, w, B = all_m['A · 条件系数（零空间基）'], all_m['w · 条件闭合差'], None
        models = {'A · 等价线性化条件基': entry(A, columns=obs), 'w · 闭合差': entry(w)}
    elif method == 'condition_parameters':
        A, B, w = np.eye(len(m.L)), -m.B@m.Z, m.l-m.B@m.xp
        models = {'A_c': entry(A, obs, obs), 'B_c · 自由参数系数': entry(B, obs), 'w_c': entry(w, obs),
                  'Z · 限制零空间': entry(m.Z, params), 'xp · 限制特解': entry(m.xp, params)}
    else:
        A = w = None; B = m.B
        models = {'B · 最终坐标处系数': entry(B, obs, params), 'l · 最终常数项': entry(m.l, obs)}
        if len(m.C): models.update({'C': entry(m.C, columns=params), 'd': entry(m.d)})
    steps.append({'id': 'model', 'title': '列出'+MODEL_NAMES[method], 'formula': FORMULAS[method],
                  'description': '条件基由左零空间生成。附参条件模型含限制时参数为 z，原坐标改正数 dx = xp + Z z。矩阵在最终线性化位置评定。', 'matrices': models})
    steps.append(_normal(method, A=A, B=B, w=w, l=m.l, C=m.C if len(m.C) else None, d=m.d, P=m.P))
    if method.startswith('condition') and ((method == 'condition' and not len(A)) or (method == 'condition_parameters' and B.shape[1] == 0)):
        steps[-1]['description'] += ' 当前为无条件行或无自由参数的退化情形，按等价观测模型处理。'
    steps.extend([
        {'id': 'solution', 'title': '求解与迭代校核', 'formula': 'X̂ = X₀ + ΔX；v = f(X̂) − L',
         'description': 'ΔX 为相对最初坐标的总改正数；迭代表给出每次线性化的改正量，最终成果按精确观测函数复核。',
         'iterations': solution.iteration_trace,
         'matrices': {'ΔX · 坐标总改正数': entry(solution.corrections, params), 'X̂ · 最终待估坐标': entry([solution.points[p][a] for p, a in m.keys], params),
                      'v · 观测改正数': entry(r.v, obs), 'L̂ · 观测平差值': entry(r.adjusted, obs)}},
        {'id': 'precision', 'title': '精度评定与统计检验', 'formula': 'σ̂₀ = √(vᵀ P v / f)，CovXX = σ² Qxx',
         'description': '中误差按所选先验或后验精度基准计算；统计诊断使用先验模型。设计模式不估计后验单位权中误差。',
         'matrices': {'Qxx': entry(r.qxx, params, params), 'Qvv': entry(r.qvv, obs, obs), 'Q_L̂': entry(r.q_adjusted, obs, obs)},
         'metrics': {'n': m.stats['n'], 't': m.stats['t'], 'r': m.stats['r'], 'vᵀPv': r.weighted_sum, '所用 σ': r.precision_sigma, 'σ̂₀': r.posterior_sigma}}])
    return steps


def matrix_steps(method, values, result):
    r = result
    A, B = values.get('A'), values.get('B')
    p = r.details['P']; q = r.qll
    return [
        {'id': 'model', 'title': '核对输入模型', 'formula': FORMULAS[method],
         'description': '按输入顺序列式；x 为参数本身，或在填写 X₀ 时表示参数改正数。',
         'matrices': {name: entry(value) for name, value in values.items() if name not in ('P',)}},
        {'id': 'weights', 'title': '权阵与协因数', 'formula': 'Q = P⁻¹，Cov(L) = σ₀² Q',
         'description': '输入的是权 P。权阵须对称正定，向量输入代表对角权。', 'matrices': {'P': entry(p), 'Q': entry(q)}},
        _normal(method, A=A, B=B, w=values.get('w'), l=values.get('l'), C=values.get('C'), d=values.get('d'), P=p),
        {'id': 'solution', 'title': '求解与方程校核', 'formula': 'v = L̂ − L，X̂ = X₀ + x',
         'description': '未提供 L 或 X₀ 的项目不生成对应的绝对平差值。',
         'matrices': {k: entry(v) for k, v in {'v': r.v, 'x': r.x, 'L̂': r.adjusted, 'X̂': r.parameters}.items() if v is not None},
         'metrics': {'方程校核': r.equation_error, '限制校核': r.constraint_error, 'vᵀPv': r.weighted_sum}},
        {'id': 'precision', 'title': '协因数传播与精度评定', 'formula': 'σ̂₀ = √(vᵀ P v / f)，Cov = σ² Q',
         'description': '自由度 f 为多余观测数；整体统计检验使用先验 σ₀，而非由本次残差估计的 σ̂₀。',
         'matrices': {k: entry(v) for k, v in {'Qxx': r.qxx, 'Qvv': r.qvv, 'Q_L̂': r.q_adjusted}.items() if v is not None},
         'metrics': {'n': r.n, 't = n − f': r.n-r.dof, 'r = f': r.dof, '所用 σ': r.precision_sigma, 'σ̂₀': r.posterior_sigma}}]
