"""Small, independent numerical experiments for the offline theory reader.

Inputs and outputs use the units displayed by each experiment (mm for lengths).
These experiments never modify the user's network or its adjustment results.
"""
from math import erf, exp, isfinite, pi, sqrt, atan2, degrees

import numpy as np
from scipy.special import fdtr, fdtri, gammainc, gammaincc, gammaincinv

from adjustment import AdjustmentError


def _number(data, key, default, low, high, *, integer=False):
    value = data.get(key, default)
    if isinstance(value, bool): raise AdjustmentError(f'{key} 必须是数值。')
    try: value = float(value)
    except (TypeError, ValueError): raise AdjustmentError(f'{key} 必须是数值。') from None
    if not isfinite(value) or not low <= value <= high or (integer and not value.is_integer()):
        raise AdjustmentError(f'{key} 应为 {low} 至 {high} 之间的'+('整数。' if integer else '有限数。'))
    return value


def experiment(kind, data):
    if not isinstance(data, dict): raise AdjustmentError('例题参数必须是对象。')
    metrics, notes, plot = [], [], None
    def metric(label, value, unit=''): metrics.append(dict(label=label, value=float(value), unit=unit))
    if kind == 'normal':
        k = _number(data, 'k', 1, .1, 4)
        probability = erf(k/sqrt(2))
        metric('区间内概率', probability*100, '%')
        metric('区间外概率', (1-probability)*100, '%')
        metric('标准化界限 k', k)
        z = np.linspace(-4, 4, 241)
        plot = dict(type='normal', k=k, points=np.column_stack((z, np.exp(-z*z/2)/sqrt(2*pi))).tolist())
        notes = ['假设误差服从正态分布；这里计算的是总体概率，不是某一组样本必然满足的比例。',
                 '正态分布无有限边界；超过 3σ 的观测仍有非零概率，不能仅凭这一点认定粗差。']
    elif kind == 'propagation':
        s1 = _number(data, 's1', 3, .000001, 1e6)
        s2 = _number(data, 's2', 4, .000001, 1e6)
        rho = _number(data, 'rho', 0, -1, 1)
        b = _number(data, 'b', 1, -1, 1)
        if b not in (-1, 1): raise AdjustmentError('第二个系数只能取 +1 或 -1。')
        covariance = rho*s1*s2
        cross = 2*b*covariance
        variance = max(0., s1*s1+s2*s2+cross)
        metric('输出标准差', sqrt(variance), 'mm')
        metric('输出方差', variance, 'mm²')
        metric('协方差', covariance, 'mm²')
        metric('交叉项', cross, 'mm²')
        plot = dict(type='propagation', terms=[s1*s1, s2*s2, cross], covariance=[[s1*s1, covariance], [covariance, s2*s2]])
        notes = ['线性模型 y = x₁ '+('+' if b == 1 else '−')+' x₂，此传播公式是精确的。长度标准差均以 mm 输入。',
                 '正相关会增大和的方差、减小差的方差。ρ = ±1 是退化边界；抵消得到零方差依赖精确的完全相关假设。']
    elif kind == 'ellipse':
        sx = _number(data, 'sx', 2, .000001, 1e6)
        sy = _number(data, 'sy', 1, .000001, 1e6)
        rho = _number(data, 'rho', .3, -.999999, .999999)
        coverage = data.get('coverage', '95')
        source = data.get('source', 'prior')
        if coverage not in ('standard', '95', '99') or source not in ('prior', 'posterior'):
            raise AdjustmentError('未知的椭圆置信水平或精度基准。')
        dof = _number(data, 'dof', 10, 1, 100000, integer=True) if source == 'posterior' else 10
        cov = np.array([[sx*sx, rho*sx*sy], [rho*sx*sy, sy*sy]])
        eigen, vectors = np.linalg.eigh(cov)
        major, minor = sqrt(eigen[1]), sqrt(max(0., eigen[0]))
        circular = (eigen[1]-eigen[0]) <= 1e-12*eigen[1]
        azimuth = None if circular else degrees(atan2(vectors[1, 1], vectors[0, 1])) % 180
        if coverage == 'standard':
            factor = 1.
            probability = 1-exp(-.5) if source == 'prior' else float(fdtr(2, dof, .5))
        else:
            probability = int(coverage)/100
            factor = sqrt(2*float(gammaincinv(1, probability))) if source == 'prior' else sqrt(2*float(fdtri(2, dof, probability)))
        metric('标准长半轴 a', major, 'mm'); metric('标准短半轴 b', minor, 'mm')
        metric('显示长半轴', major*factor, 'mm'); metric('显示短半轴', minor*factor, 'mm')
        metric('半轴倍率 k', factor); metric('联合覆盖率', probability*100, '%')
        if azimuth is not None: metric('长轴方位角', azimuth, '°')
        plot = dict(type='ellipse', major=major, minor=minor, factor=factor, azimuth=azimuth, covariance=cov.tolist())
        notes = ['X 轴向上、Y 轴向右；方位角从 +X 转向 +Y，取 [0°, 180°)。圆形时长轴方向不唯一。',
                 '已知协方差：二维正态假设，置信半轴倍率 √χ²₂(p)。' if source == 'prior' else
                 '后验尺度：假设线性正态模型成立、协因数确定，且尺度估计与参数估计独立；倍率 √[2F₂,ᶠ(p)]。输入标准差应已含后验尺度。',
                 '主工作台画布仍显示 1σ 半轴；本例题的置信椭圆不改变主画布。GNSS 的 XY 椭圆只是坐标框架中的平面投影。']
    elif kind == 'global-test':
        omega = _number(data, 'omega', 8, 0, 1e12)
        dof = _number(data, 'dof', 5, 1, 100000, integer=True)
        sigma = _number(data, 'sigma0', 1, .000001, 1e6)
        alpha = _number(data, 'alpha', .05, .0001, .5)
        statistic = omega/(sigma*sigma)
        lower = 2*float(gammaincinv(dof/2, alpha/2))
        upper = 2*float(gammaincinv(dof/2, 1-alpha/2))
        p_value = min(1., 2*min(float(gammainc(dof/2, statistic/2)), float(gammaincc(dof/2, statistic/2))))
        metric('检验统计量 T', statistic); metric('区间下限', lower); metric('区间上限', upper)
        metric('双侧 p 值', p_value); metric('后验单位权中误差', sqrt(omega/dof))
        rejected = statistic < lower or statistic > upper
        plot = dict(type='global-test', rejected=rejected, statistic=statistic, lower=lower, upper=upper)
        notes = [('拒绝 H₀：请核查精度尺度、观测或模型。' if rejected else '未拒绝 H₀：这不证明模型完全正确。'),
                 'H₀：函数模型正确，误差零均值正态，Cov(L) = σ₀²Q，先验 σ₀ 作为已知量。',
                 '不可用同一组残差估计的 σ̂₀ 代替独立先验 σ₀ 再做此检验，否则 T 恒等于自由度。']
    elif kind == 'weighted-mean':
        values = np.array([_number(data, f'l{i}', v, -1e6, 1e6) for i, v in enumerate((10., 12., 9.), 1)])
        sigmas = np.array([_number(data, f's{i}', v, .000001, 1e6) for i, v in enumerate((1., 2., 1.), 1)])
        weights = 1/(sigmas*sigmas)
        mean = float(weights@values/weights.sum())
        residuals = mean-values
        omega = float(weights@(residuals*residuals))
        metric('加权平均值', mean, 'mm'); metric('先验均值标准差', sqrt(1/weights.sum()), 'mm')
        metric('vᵀPv', omega); metric('多余观测数 r', 2)
        metric('后验单位权中误差', sqrt(omega/2))
        metric('后验均值标准差', sqrt(omega/2/weights.sum()), 'mm')
        plot = dict(type='weighted-mean', weights=weights.tolist(), residuals=residuals.tolist())
        notes = ['三个互不相关的观测测定同一个量。P = diag(1/σᵢ²)，按先验 σ₀ = 1 归一化；权的绝对单位由此约定决定。',
                 'v = 平差值 − 观测值。较小标准差得到较大权，但不能消除共同系统偏差。']
    else: raise AdjustmentError('未知的理论例题。')
    return dict(metrics=metrics, notes=notes, plot=plot)
