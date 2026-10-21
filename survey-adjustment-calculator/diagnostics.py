"""Prior-covariance tests with Holm correction, including correlated blocks.

Tests assume Gaussian observations and a correct prior covariance model. For
nonlinear networks these are local linearization diagnostics, not proof of a
blunder. We never use the fitted posterior scale as an independent prior.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.special import gammainc, gammaincc, gammaincinv

from adjustment import AdjustmentError


def holm(p_values):
    """Adjusted p-values; None means a residual has no testable variance."""
    output = [None] * len(p_values)
    ordered = sorted((p, i) for i, p in enumerate(p_values) if p is not None)
    previous = 0.
    for rank, (p, i) in enumerate(ordered):
        previous = max(previous, min(1., (len(ordered)-rank)*p))
        output[i] = previous
    return output


def diagnose(result, *, sigma0=1., labels=None, groups=None, angular=None,
             alpha=.05, design=False):
    if not math.isfinite(float(alpha)) or not 0 < float(alpha) < 1:
        raise AdjustmentError('显著性水平须在 0 与 1 之间。')
    if not math.isfinite(float(sigma0)) or float(sigma0) <= 0:
        raise AdjustmentError('检验的先验单位权中误差须为正数。')
    alpha, sigma0 = float(alpha), float(sigma0)
    base = {'alpha': alpha, 'sigma0': sigma0, 'scale': 'prior',
            'multiplicity': 'Holm', 'rows': [], 'groups': [], 'flagged_observations': [],
            'notes': ['检验以输入的先验协方差及先验 σ₀ 为参考；后验 σ̂₀ 不替代先验基准。',
                      '若输入仅为相对权，应先给出合理的先验 σ₀，检验结论依赖该先验误差尺度。',
                      '假定误差服从正态分布，非线性网使用最终坐标处的局部线性化。',
                      '分量与观测块分别进行 Holm 多重检验校正；标记为疑似异常，须结合原始记录核查。']}
    if design:
        return {**base, 'available': False, 'reason': '布网设计没有实测残差，不能进行粗差检验。', 'global_test': None}
    n, dof = result.n, result.dof
    if dof <= 0:
        return {**base, 'available': False, 'reason': '无多余观测，无法进行残差统计检验。', 'global_test': None}
    labels = labels or [f'L{i+1}' for i in range(n)]
    angular = np.zeros(n, dtype=bool) if angular is None else np.asarray(angular, dtype=bool)
    groups = groups or [(labels[i], i, 1) for i in range(n)]
    group_ids = [None]*n
    for identity, start, count in groups:
        for i in range(start, start+count): group_ids[i] = identity
    v, qvv, qll = np.asarray(result.v), np.asarray(result.qvv), np.asarray(result.qll)
    test = max(0., float(result.weighted_sum)/sigma0**2)
    cdf = float(gammainc(dof/2, test/2))
    sf = float(gammaincc(dof/2, test/2))
    low, high = [float(2*gammaincinv(dof/2, p)) for p in (alpha/2, 1-alpha/2)]
    global_test = {'statistic': test, 'dof': dof, 'lower': low, 'upper': high,
                   'p_value': min(1., 2*min(cdf, sf)), 'rejected': not low <= test <= high,
                   'status': '偏大' if test > high else '偏小' if test < low else '区间内'}
    rows = []
    for i, label in enumerate(labels):
        q = max(0., float(qvv[i, i])); q_input = float(qll[i, i])
        # Scale-relative threshold: do not classify tiny-but-valid angular
        # variances as zero merely because their physical units are radians.
        testable = q > max(np.finfo(float).tiny, q_input*1e-12)
        z = float(v[i]/(sigma0*math.sqrt(q))) if testable else None
        p = math.erfc(abs(z)/math.sqrt(2)) if z is not None else None
        rows.append({'label': label, 'observation': group_ids[i], 'index': i,
                     'residual': float(v[i]), 'display_residual': float(v[i]/(math.pi/(180*3600)) if angular[i] else v[i]*1000),
                     'unit': '″' if angular[i] else 'mm', 'testable': testable,
                     'standardized': z, 'p_value': p, 'variance_ratio': min(1., max(0., q/q_input)) if q_input > 0 else None})
    adjusted = holm([row['p_value'] for row in rows])
    for row, p in zip(rows, adjusted): row.update(p_adjusted=p, rejected=p is not None and p <= alpha)
    blocks = []
    for identity, start, count in groups:
        idx = slice(start, start+count)
        raw = qvv[idx, idx]
        scales = np.sqrt(np.maximum(np.diag(qll[idx, idx]), np.finfo(float).tiny))
        standardized_cov = (raw/scales[:, None])/scales[None, :]
        eigen, vectors = np.linalg.eigh((standardized_cov+standardized_cov.T)/2)
        active = eigen > 1e-12
        rank = int(active.sum())
        if rank:
            projected = vectors[:, active].T@(v[idx]/scales/sigma0)
            stat = max(0., float(np.sum(projected**2/eigen[active])))
            p = float(gammaincc(rank/2, stat/2))
        else: stat = p = None
        blocks.append({'observation': identity, 'components': count, 'rank': rank,
                       'statistic': stat, 'p_value': p,
                       'variance_ratio': float(np.trace(standardized_cov)),
                       'correlated': bool(count > 1 and np.any(np.abs(qll[idx, idx]-np.diag(np.diag(qll[idx, idx]))) > 0))})
    adjusted = holm([block['p_value'] for block in blocks])
    for block, p in zip(blocks, adjusted): block.update(p_adjusted=p, rejected=p is not None and p <= alpha)
    flagged = sorted({row['observation'] for row in rows if row['rejected']} |
                     {block['observation'] for block in blocks if block['rejected']})
    return {**base, 'available': True, 'reason': '', 'global_test': global_test,
            'rows': rows, 'groups': blocks, 'flagged_observations': flagged}


def diagnostic_report(data):
    lines = ['统计检验与疑似粗差诊断', f"先验 σ₀={data['sigma0']}；α={data['alpha']}；多重检验：Holm"]
    if not data['available']: lines.append(data['reason'])
    else:
        g = data['global_test']
        lines.append(f"整体检验 T={g['statistic']:.8g}，f={g['dof']}，接受区间=[{g['lower']:.8g}, {g['upper']:.8g}]，双侧 p={g['p_value']:.8g}，{g['status']}")
        lines.append('疑似异常观测：'+(', '.join(data['flagged_observations']) or '未检出'))
        for row in data['rows']:
            lines.append(f"{row['label']}: v={row['display_residual']:.8g} {row['unit']}, z={row['standardized']}, p_Holm={row['p_adjusted']}, 疑似异常={row['rejected']}")
        for block in data['groups']:
            lines.append(f"观测块 {block['observation']}: T={block['statistic']}, 有效秩={block['rank']}, p_Holm={block['p_adjusted']}")
    return '\n'.join(lines+data['notes'])
