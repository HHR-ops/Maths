"""Linear surveying adjustment. No files, UI, or network access in this module.

Conventions: v = adjusted - observed; Q = inv(P); Cov(L) = sigma0**2 Q.
Condition: A v + w = 0. Parametric condition: A v + B x + w = 0.
Indirect: v = B x - l. Constrained indirect additionally has C x + d = 0.
All supplied models are linear or already linearized; x is a correction when X0
is supplied. Exact deterministic constraints and fixed X0 are assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

import numpy as np

MODEL_NAMES = {
    "condition": "条件平差",
    "condition_parameters": "附有参数的条件平差",
    "indirect": "间接平差",
    "indirect_constraints": "附有限制条件的间接平差",
}
FORMULAS = {
    "condition": "A v + w = 0",
    "condition_parameters": "A v + B x + w = 0",
    "indirect": "v = B x − l",
    "indirect_constraints": "v = B x − l，C x + d = 0",
}
MAX_DIM = 500


class AdjustmentError(ValueError):
    """An actionable invalid-data/model error suitable for displaying in a UI."""


def parse_matrix(text: str, name: str = "矩阵") -> np.ndarray:
    """Parse numbers only; support Excel tabs, spaces, CSV, semicolons, comments.

    No eval, executable expressions, implicit empty cells, or NaN/Inf values.
    """
    text = text.strip().lstrip("\ufeff")
    text = text.translate(str.maketrans({"，": ",", "；": ";", "−": "-", "　": " "}))
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].replace("],", ";").replace("][", ";")
    rows = []
    for line_no, line in enumerate(text.replace(";", "\n").splitlines(), 1):
        line = line.split("#", 1)[0].strip().strip("[]").strip()
        if not line:
            continue
        if "," in line:
            parts = line.split(",")
            if any(not part.strip() for part in parts):
                raise AdjustmentError(f"{name} 第 {line_no} 行有空单元格。请填写数值。")
            tokens = [token for part in parts for token in part.split()]
        else:
            tokens = line.split()
        try:
            row = [float(token) for token in tokens]
        except ValueError as exc:
            raise AdjustmentError(f"{name} 第 {line_no} 行含非数值内容。仅支持数字和科学计数法。") from exc
        if rows and len(row) != len(rows[0]):
            raise AdjustmentError(f"{name} 各行列数不一致：第 {line_no} 行为 {len(row)} 列，应为 {len(rows[0])} 列。")
        rows.append(row)
    if not rows:
        raise AdjustmentError(f"请填写{name}。")
    return matrix(rows, name)


def matrix(value: Any, name: str) -> np.ndarray:
    try:
        a = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise AdjustmentError(f"{name} 必须是规则的数值矩阵。") from exc
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.ndim != 2 or not a.size:
        raise AdjustmentError(f"{name} 必须为非空二维矩阵。")
    if max(a.shape) > MAX_DIM:
        raise AdjustmentError(f"{name} 超出当前版本上限：每个维度最多 {MAX_DIM}。")
    if not np.isfinite(a).all():
        raise AdjustmentError(f"{name} 不允许 NaN、Inf 或超出数值范围的数。")
    return a


def vector(value: Any, length: int, name: str) -> np.ndarray:
    a = matrix(value, name)
    if 1 not in a.shape or a.size != length:
        raise AdjustmentError(f"{name} 应包含 {length} 个数，可用行向量或列向量。当前维数为 {a.shape}。")
    return a.reshape(-1)


def sym(a: np.ndarray) -> np.ndarray:
    return (a + a.T) / 2


def _svd(a: np.ndarray, name: str, warnings: list[str], full: bool = False):
    u, s, vt = np.linalg.svd(a, full_matrices=full)
    tol = (max(a.shape) * np.finfo(float).eps * s[0]) if s.size else 0.0
    rank = int(np.count_nonzero(s > tol))
    if s.size and rank == len(s) and s[-1] > 0 and s[0] / s[-1] > 1e10:
        warnings.append(f"{name} 条件数较大（{s[0] / s[-1]:.3g}），请检查单位、参数尺度和近似线性相关。")
    return u, s, vt, rank


def _full_column_inverse(a: np.ndarray, name: str, warnings: list[str]):
    u, s, vt, rank = _svd(a, name, warnings)
    if rank != a.shape[1]:
        raise AdjustmentError(f"{name} 列秩不足（秩 {rank}，列数 {a.shape[1]}），参数不能唯一确定。")
    return (vt.T / s) @ u.T if s.size else np.zeros((0, a.shape[0]))


@dataclass
class AdjustmentResult:
    model: str
    n: int
    t: int
    r: int
    dof: int
    v: np.ndarray
    x: np.ndarray | None
    observed: np.ndarray | None
    adjusted: np.ndarray | None
    x0: np.ndarray | None
    parameters: np.ndarray | None
    qll: np.ndarray
    qvv: np.ndarray
    q_adjusted: np.ndarray
    qxx: np.ndarray | None
    weighted_sum: float
    posterior_sigma: float | None
    precision_sigma: float | None
    precision_source: str
    equation_error: float
    constraint_error: float
    warnings: list[str] = field(default_factory=list)
    details: dict[str, np.ndarray] = field(default_factory=dict)

    def std(self, cofactor: np.ndarray | None):
        if cofactor is None or self.precision_sigma is None:
            return None
        return self.precision_sigma * np.sqrt(np.maximum(np.diag(cofactor), 0))

    def to_dict(self) -> dict:
        def convert(v):
            if isinstance(v, np.ndarray):
                return v.tolist()
            if isinstance(v, dict):
                return {k: convert(value) for k, value in v.items()}
            return v
        return {k: convert(v) for k, v in vars(self).items()}


def solve(model: str, *, A=None, B=None, w=None, l=None, C=None, d=None,
          P=None, observed=None, x0=None, sigma0=1.0,
          precision="posterior") -> AdjustmentResult:
    if model not in MODEL_NAMES:
        raise AdjustmentError("未知平差模型。")
    if precision not in ("posterior", "prior"):
        raise AdjustmentError("精度基准应为后验或先验。")
    try:
        sigma0 = float(sigma0)
    except (TypeError, ValueError) as exc:
        raise AdjustmentError("先验单位权中误差必须为正数。") from exc
    if not np.isfinite(sigma0) or sigma0 <= 0:
        raise AdjustmentError("先验单位权中误差必须为有限正数。")
    warnings: list[str] = []
    is_condition = model.startswith("condition")
    if is_condition:
        A = matrix(A, "A")
        r, n = A.shape
        w = vector(w, r, "w")
    else:
        B = matrix(B, "B")
        n, _ = B.shape
        l = vector(l, n, "l")

    if P is None:
        P = np.eye(n)
    else:
        P = matrix(P, "P")
        if 1 in P.shape and P.size == n:
            P = np.diag(P.reshape(-1))
        if P.shape != (n, n):
            raise AdjustmentError(f"P 应为 {n}×{n} 权阵或包含 {n} 个正权的向量。")
    pscale = max(float(np.max(np.abs(P))), np.finfo(float).tiny)
    if np.max(np.abs(P - P.T)) > 1e-12 * pscale:
        raise AdjustmentError("权阵 P 必须对称。")
    P = sym(P)
    try:
        R = np.linalg.cholesky(P).T
        T = np.linalg.solve(R, np.eye(n))
    except np.linalg.LinAlgError as exc:
        raise AdjustmentError("权阵 P 必须正定：各权须为正，且相关权阵不能奇异。") from exc
    if np.linalg.cond(R) > 1e6:
        warnings.append("权阵 P 的条件数较大，请检查权值尺度和观测相关性。")
    Q = sym(T @ T.T)
    details = {"P": P, "Q = P⁻¹": Q}
    x = qxx = None
    constraint_error = 0.0

    if is_condition:
        if model == "condition_parameters":
            B = matrix(B, "B")
            if B.shape[0] != r:
                raise AdjustmentError(f"B 应与 A 有相同的行数 {r}。")
            t = B.shape[1]
            u, s, vt, rank = _svd(B, "参数系数 B", warnings, full=True)
            if rank != t:
                raise AdjustmentError(f"参数系数 B 列秩不足（秩 {rank}，参数个数 {t}）。")
            B_plus = (vt[:t].T / s[:t]) @ u[:, :t].T
            Z = u[:, t:]
        else:
            t = 0
            Z = np.eye(r)
        F = Z.T @ A @ T
        u, s, vt, rank = _svd(F, "有效条件系数", warnings)
        dof = r - t
        if rank != dof:
            raise AdjustmentError(f"条件方程不独立（有效秩 {rank}，应为 {dof}）。请删去重复条件或修正系数。")
        if dof:
            F_plus = (vt.T / s) @ u.T
            z = -F_plus @ (Z.T @ w)
            V = vt.T
        else:
            z = np.zeros(n)
            V = np.empty((n, 0))
        v = T @ z
        correction_factor = T @ V
        qvv = sym(correction_factor @ correction_factor.T)
        # Form the complementary projection directly for stable small variances.
        adjusted_factor = T @ (np.eye(n) - V @ V.T)
        q_adjusted = sym(adjusted_factor @ adjusted_factor.T)
        check = A @ v + w
        if t:
            x = -B_plus @ check
            check = check + B @ x
            x_factor = -B_plus @ A @ adjusted_factor
            qxx = sym(x_factor @ x_factor.T)
        details.update({"A": A, "w": w, "S = A Q Aᵀ": sym(A @ Q @ A.T)})
        if t:
            details["B"] = B
            details["增广法方程系数 [S B; Bᵀ 0]"] = np.block([
                [A @ Q @ A.T, B], [B.T, np.zeros((t, t))]])
        equation_error = float(np.max(np.abs(check)))
    else:
        n, t = B.shape
        if model == "indirect_constraints":
            C = matrix(C, "C")
            if C.shape[1] != t:
                raise AdjustmentError(f"限制系数 C 应有 {t} 列。")
            c = C.shape[0]
            d = vector(d, c, "d")
            u, s, vt, rank = _svd(C, "限制系数 C", warnings, full=True)
            if rank != c:
                raise AdjustmentError(f"限制条件不独立（秩 {rank}，限制条件个数 {c}）。请删去重复或矛盾限制。")
            xp = -vt[:c].T @ ((u.T @ d) / s)
            Z = vt[c:].T
            details.update({"C": C, "d": d})
        else:
            c = 0
            xp = np.zeros(t)
            Z = np.eye(t)
        M = R @ B @ Z
        M_plus = _full_column_inverse(M, "加权后的自由参数系数", warnings)
        x = xp + Z @ M_plus @ (R @ (l - B @ xp))
        v = B @ x - l
        x_factor = Z @ M_plus
        qxx = sym(x_factor @ x_factor.T)
        adjusted_factor = B @ x_factor
        q_adjusted = sym(adjusted_factor @ adjusted_factor.T)
        residual_factor = adjusted_factor @ R - np.eye(n)
        qvv = sym(residual_factor @ Q @ residual_factor.T)
        dof = n - (t - c)
        r = c
        equation_error = float(np.max(np.abs(B @ x - l - v)))
        if c:
            constraint_error = float(np.max(np.abs(C @ x + d)))
        N, U = sym(B.T @ P @ B), B.T @ P @ l
        details.update({"B": B, "l": l, "N = Bᵀ P B": N, "u = Bᵀ P l": U})
        if c:
            details["增广法方程系数 [N Cᵀ; C 0]"] = np.block([
                [N, C.T], [C, np.zeros((c, c))]])

    L = vector(observed, n, "观测值 L") if observed is not None else None
    X0 = vector(x0, t, "参数初值 X₀") if x0 is not None and t else None
    if x0 is not None and not t:
        raise AdjustmentError("纯条件平差没有参数，不应提供 X₀。")
    weighted_sum = float((R @ v) @ (R @ v))
    posterior = float(np.sqrt(weighted_sum / dof)) if dof > 0 else None
    if dof == 0:
        warnings.append("自由度为 0，不能估计后验单位权中误差；如需中误差，请选择先验精度基准。")
    chosen_sigma = sigma0 if precision == "prior" else posterior
    arrays = [v, Q, qvv, q_adjusted] + ([x, qxx] if x is not None else [])
    if not all(np.isfinite(a).all() for a in arrays) or not np.isfinite(weighted_sum):
        raise AdjustmentError("计算出现溢出，请缩放单位、权值或矩阵系数后重试。")
    scale = 1 + (np.linalg.norm(w, ord=np.inf) if is_condition else np.linalg.norm(l, ord=np.inf))
    x_scale = 1 + np.linalg.norm(x, ord=np.inf) if x is not None else 1.0
    if equation_error > 1e-8 * scale or constraint_error > 1e-8 * x_scale:
        raise AdjustmentError("方程校核未通过，模型数值不稳定。请检查尺度或近似相关系数。")
    return AdjustmentResult(
        model=model, n=n, t=t, r=r, dof=dof, v=v, x=x, observed=L,
        adjusted=L + v if L is not None else None, x0=X0,
        parameters=X0 + x if X0 is not None else None,
        qll=Q, qvv=qvv, q_adjusted=q_adjusted, qxx=qxx,
        weighted_sum=weighted_sum, posterior_sigma=posterior,
        precision_sigma=chosen_sigma, precision_source=precision,
        equation_error=equation_error, constraint_error=constraint_error,
        warnings=warnings, details=details)


def format_array(a: np.ndarray, digits: int = 8, limit: int = 24) -> str:
    a = np.asarray(a)
    return np.array2string(a, precision=digits, suppress_small=False,
                          threshold=limit * limit, edgeitems=6, max_line_width=120,
                          formatter={"float_kind": lambda x: f"{x:.{digits}g}"})


def make_report(result: AdjustmentResult, title="未命名计算", digits=8) -> str:
    r = result
    lines = ["测量平差计算报告", title, "=" * 60,
             f"模型：{MODEL_NAMES[r.model]}", f"方程：{FORMULAS[r.model]}",
             "符号：v = 平差值 − 观测值；Q = P⁻¹；Cov(L) = σ₀² Q。",
             "本次计算使用线性 / 已线性化方程；x 为所输入方程中的未知量。",
             f"总观测数 n = {r.n}；必要观测数 t = {r.n-r.dof}；多余观测数 r = {r.dof}",
             f"待估参数个数 u = {r.t}；残差自由度 f = {r.dof}",
             f"vᵀPv = {r.weighted_sum:.{digits}g}",
             f"后验单位权中误差 = {r.posterior_sigma:.{digits}g}" if r.posterior_sigma is not None else "后验单位权中误差：无法估计（自由度为 0）",
             f"精度基准：{'先验' if r.precision_source == 'prior' else '后验'}；"
             + (f"所用标准差尺度 σ = {r.precision_sigma:.{digits}g}" if r.precision_sigma is not None else "中误差不可用"),
             f"方程校核最大绝对差 = {r.equation_error:.3e}",
             f"限制条件校核最大绝对差 = {r.constraint_error:.3e}"]
    for warning in r.warnings:
        lines.append(f"提示：{warning}")
    items = [("改正数 v", r.v), ("观测值 L", r.observed), ("平差值 L̂ = L + v", r.adjusted),
             ("参数解 x", r.x), ("参数初值 X₀", r.x0), ("参数平差值 X̂ = X₀ + x", r.parameters),
             ("观测平差值中误差", r.std(r.q_adjusted)), ("参数中误差", r.std(r.qxx)),
             ("改正数中误差", r.std(r.qvv)),
             ("Q_vv", r.qvv), ("Q_L̂L̂", r.q_adjusted), ("Q_xx", r.qxx)]
    for name, value in items:
        if value is not None:
            lines.extend(["", name, format_array(value, digits)])
    lines.extend(["", "计算中间量（便于复核；求解使用白化与 SVD）"])
    for name, value in r.details.items():
        lines.extend([name, format_array(value, digits), ""])
    lines.append("大矩阵在文本报告中可能折叠显示；完整精度数据请导出结果 JSON。")
    return "\n".join(lines)
