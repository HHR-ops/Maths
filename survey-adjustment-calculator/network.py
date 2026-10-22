"""Geometry, automatic linearization and precision analysis for local control nets.

Planar coordinates: X north, Y east; GNSS: any one consistent Cartesian XYZ
frame (including ECEF), without frame conversion. Angular equations use radians;
user angular values are degrees, angular standard deviations are arcseconds.
GNSS observations are Cartesian baseline vectors in this same declared frame.
Each observation block is independent of other blocks; a block may be correlated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import math
import re

import numpy as np

from adjustment import AdjustmentError, AdjustmentResult, MODEL_NAMES, solve, sym, format_array

FAMILIES = ["水准网", "导线网", "GNSS网", "测边网", "测角网", "边角网", "坐标观测网"]
KINDS = {"height":"高差", "distance":"距离", "angle":"水平角", "azimuth":"方位角",
         "gnss":"GNSS基线", "coordinate":"坐标观测"}
ARCSEC = math.pi / (180*3600)
ANGLES = {"angle", "azimuth"}
DEFAULT_SIGMA = {"height":.001,"distance":.003,"angle":2.,"azimuth":2.,"gnss":.005,"coordinate":.003}


def finite(value, label="数值"):
    try:
        v = float(value)
    except (ValueError, TypeError) as exc:
        raise AdjustmentError(f"{label}必须是数值。") from exc
    if not math.isfinite(v):
        raise AdjustmentError(f"{label}必须是有限数。")
    return v


def angle_degrees(text):
    if not isinstance(text, str):
        return finite(text, "角度")
    text = text.strip().replace("°", ":").replace("′", ":").replace("'", ":").replace("″", "").replace('"', "")
    if ":" not in text:
        return finite(text, "角度")
    parts = text.split(":")
    if not 2 <= len(parts) <= 3:
        raise AdjustmentError("度分秒格式应为 123:45:56.7。")
    degree, minute = finite(parts[0]), finite(parts[1])
    second = finite(parts[2]) if len(parts) == 3 and parts[2] else 0.
    if not 0 <= minute < 60 or not 0 <= second < 60:
        raise AdjustmentError("角度的分、秒应在 [0,60) 内。")
    return (-1 if parts[0].lstrip().startswith("-") else 1)*(abs(degree)+minute/60+second/3600)


def wrap(v):
    return (v + math.pi) % (2*math.pi) - math.pi


class Network:
    def __init__(self, family="水准网", name="新建控制网"):
        if family not in FAMILIES:
            raise AdjustmentError("未知控制网类型。")
        self.family, self.name = family, name
        self.points = {}
        self.observations = []
        self.constraints = []
        self.method = "indirect"

    @property
    def axes(self):
        return ("H",) if self.family == "水准网" else (("X","Y","Z") if self.family == "GNSS网" else ("X","Y"))

    @property
    def allowed_kinds(self):
        return ["height","coordinate"] if self.family == "水准网" else (["gnss","coordinate"] if self.family == "GNSS网" else ["distance","angle","azimuth","coordinate"])

    def add_point(self, name=None, X=0., Y=0., H=100., Z=0., fixed=()):
        if name is None:
            i = 1
            while f"P{i}" in self.points:
                i += 1
            name = f"P{i}"
        if not re.fullmatch(r"[A-Za-z\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*", name) or name in self.points:
            raise AdjustmentError("点名须唯一，并由字母、汉字、数字或下划线组成，不能以数字开头。")
        if len(self.points) >= 120:
            raise AdjustmentError("当前画布最多支持 120 个点。")
        fixed = list(fixed)
        if any(axis not in ("X","Y","Z","H") for axis in fixed):
            raise AdjustmentError("未知固定坐标分量。")
        self.points[name] = {"X":finite(X),"Y":finite(Y),"H":finite(H),"Z":finite(Z),"fixed":fixed}
        return name

    def add_observation(self, kind, points, value=None, sigma=None, covariance=None, components=None, name=None):
        if kind not in self.allowed_kinds:
            raise AdjustmentError("该观测类型不适用于当前坐标域。")
        needed = 3 if kind == "angle" else (1 if kind == "coordinate" else 2)
        if len(points) != needed or len(set(points)) != needed or any(p not in self.points for p in points):
            raise AdjustmentError(f"{KINDS[kind]}需要 {needed} 个不同且存在的点。")
        if name is None:
            i = 1
            existing = {o["id"] for o in self.observations}
            while f"O{i}" in existing:
                i += 1
            name = f"O{i}"
        if not isinstance(name, str) or not name or any(o["id"] == name for o in self.observations):
            raise AdjustmentError("观测编号不能为空或重复。")
        item = {"id":name,"kind":kind,"points":list(points),"value":value,
                "sigma":sigma if sigma is not None else DEFAULT_SIGMA[kind],
                "covariance":covariance,"components":list(components or self.axes),"enabled":True}
        self.observations.append(item)
        try:
            _observation(self, item, self.points, {})
        except Exception:
            self.observations.pop()
            raise
        return name

    def remove_point(self, point):
        del self.points[point]
        self.observations = [o for o in self.observations if point not in o["points"]]
        self.constraints = [c for c in self.constraints if not any(k.startswith(point+".") for k in c["terms"])]

    def to_dict(self):
        return {"format":"survey-network-project","version":1,"family":self.family,"name":self.name,
                "points":deepcopy(self.points),"observations":deepcopy(self.observations),
                "constraints":deepcopy(self.constraints),"method":self.method}

    @classmethod
    def from_dict(cls, doc):
        if not isinstance(doc, dict) or doc.get("format") != "survey-network-project" or doc.get("version") != 1:
            raise AdjustmentError("不是支持的控制网项目文件。")
        net = cls(doc.get("family"), str(doc.get("name", "控制网")))
        points = doc.get("points")
        observations = doc.get("observations")
        if not isinstance(points,dict) or not isinstance(observations,list) or len(observations)>500:
            raise AdjustmentError("点或观测数据格式错误，或观测条目超过 500。")
        for name, data in points.items():
            if not isinstance(data,dict):
                raise AdjustmentError("点数据格式错误。")
            net.add_point(name, **{k:data.get(k,100 if k=="H" else 0) for k in ("X","Y","H","Z")}, fixed=data.get("fixed",[]))
        for obs in observations:
            if not isinstance(obs,dict):
                raise AdjustmentError("观测数据格式错误。")
            net.add_observation(obs.get("kind"),obs.get("points",[]),obs.get("value"),obs.get("sigma"),
                                obs.get("covariance"),obs.get("components"),obs.get("id"))
            if not isinstance(obs.get("enabled",True),bool):
                raise AdjustmentError("观测启用状态格式错误。")
            net.observations[-1]["enabled"] = obs.get("enabled",True)
        constraints = doc.get("constraints",[])
        if not isinstance(constraints,list):
            raise AdjustmentError("限制数据格式错误。")
        for constraint in constraints:
            if not isinstance(constraint,dict) or not isinstance(constraint.get("terms"),dict):
                raise AdjustmentError("限制数据格式错误。")
            net.constraints.append({"terms":{str(k):finite(v) for k,v in constraint["terms"].items()},"value":finite(constraint.get("value"))})
        net.method = doc.get("method","indirect")
        if net.method not in MODEL_NAMES:
            raise AdjustmentError("未知平差方法。")
        # Includes constraints and scalar observation count validation.
        linearize(net)
        return net


def _observation(net, obs, points, index):
    kind, ids = obs["kind"], obs["points"]
    u = len(index)
    def row(): return np.zeros(u)
    def put(a,p,axis,v):
        if (p,axis) in index: a[index[p,axis]] += v
    def bearing(a,b):
        dx,dy = points[b]["X"]-points[a]["X"], points[b]["Y"]-points[a]["Y"]
        q=dx*dx+dy*dy
        if q < 1e-16: raise AdjustmentError(f"{obs['id']}：{a} 与 {b} 平面坐标重合。")
        z=row(); put(z,b,"X",-dy/q); put(z,b,"Y",dx/q); put(z,a,"X",dy/q); put(z,a,"Y",-dx/q)
        return math.atan2(dy,dx) % (2*math.pi),z
    if kind == "height":
        a,b=ids; z=row(); put(z,a,"H",-1); put(z,b,"H",1)
        values=[points[b]["H"]-points[a]["H"]]; rows=[z]; comps=["ΔH"]
    elif kind == "distance":
        a,b=ids; dx,dy=points[b]["X"]-points[a]["X"],points[b]["Y"]-points[a]["Y"]
        length=math.hypot(dx,dy)
        if length < 1e-8: raise AdjustmentError(f"{obs['id']}：距离端点重合。")
        z=row()
        for axis,diff in [("X",dx),("Y",dy)]: put(z,a,axis,-diff/length); put(z,b,axis,diff/length)
        values=[length]; rows=[z]; comps=["S"]
    elif kind == "azimuth":
        value,z=bearing(*ids); values=[value]; rows=[z]; comps=["α"]
    elif kind == "angle":
        back,station,fore=ids
        ab,zb=bearing(station,back); af,zf=bearing(station,fore)
        values=[(af-ab)%(2*math.pi)]; rows=[zf-zb]; comps=["β"]
    else:
        comps = ["X","Y","Z"] if kind == "gnss" else obs["components"]
        if not comps or len(set(comps)) != len(comps) or any(c not in net.axes for c in comps):
            raise AdjustmentError(f"{obs['id']}：坐标分量不属于当前坐标域。")
        values=[]; rows=[]
        for axis in comps:
            z=row()
            if kind == "gnss":
                a,b=ids; values.append(points[b][axis]-points[a][axis]); put(z,a,axis,-1); put(z,b,axis,1)
            else:
                a=ids[0]; values.append(points[a][axis]); put(z,a,axis,1)
            rows.append(z)
    size=len(values)
    raw = obs.get("value")
    if raw is None or (isinstance(raw,str) and not raw.strip()):
        measured=None
    elif kind in ANGLES:
        measured=np.array([math.radians(angle_degrees(raw))])
    else:
        if isinstance(raw,str):
            raw=re.split(r"[\s,，;；]+",raw.strip())
        measured=np.asarray([finite(x,"观测值") for x in np.asarray(raw,dtype=object).reshape(-1)])
        if measured.size != size: raise AdjustmentError(f"{obs['id']} 应填 {size} 个观测分量。")
    cov=obs.get("covariance")
    if cov is not None and not (isinstance(cov,str) and not cov.strip()):
        from adjustment import parse_matrix
        cov=parse_matrix(cov,"协方差阵") if isinstance(cov,str) else np.asarray(cov,dtype=float)
        if cov.shape != (size,size) or not np.isfinite(cov).all() or not np.allclose(cov,cov.T,rtol=1e-12,atol=0):
            raise AdjustmentError(f"{obs['id']} 的协方差阵须为 {size}×{size} 对称有限数阵。")
        try: np.linalg.cholesky(cov)
        except np.linalg.LinAlgError as exc: raise AdjustmentError(f"{obs['id']} 的协方差阵必须正定。") from exc
    else:
        s=obs.get("sigma",DEFAULT_SIGMA[kind])
        if isinstance(s,str): s=re.split(r"[\s,，]+",s.strip())
        s=np.asarray([finite(v,"标准差") for v in np.asarray(s,dtype=object).reshape(-1)])
        if s.size==1: s=np.repeat(s,size)
        if s.size!=size or np.any(s<=0): raise AdjustmentError(f"{obs['id']} 的标准差须为正，可填 1 个或 {size} 个。")
        cov=np.diag((s*(ARCSEC if kind in ANGLES else 1))**2)
    return np.asarray(values),np.asarray(rows),measured,cov,comps


@dataclass
class LinearizedNetwork:
    B: np.ndarray
    l: np.ndarray
    L: np.ndarray
    predicted: np.ndarray
    Q: np.ndarray
    P: np.ndarray
    C: np.ndarray
    d: np.ndarray
    keys: list
    labels: list
    angular: np.ndarray
    groups: list
    Z: np.ndarray
    xp: np.ndarray
    stats: dict


def linearize(net: Network, points=None, design=False, require_values=False):
    points = net.points if points is None else points
    keys=[(name,axis) for name,p in points.items() for axis in net.axes if axis not in p["fixed"]]
    if len(keys)>500: raise AdjustmentError("未知参数超过 500。")
    index={key:i for i,key in enumerate(keys)}
    rows=[]; predicted=[]; observed=[]; labels=[]; angular=[]; blocks=[]; groups=[]
    for obs in net.observations:
        if not obs.get("enabled",True): continue
        if obs["kind"] not in net.allowed_kinds: raise AdjustmentError(f"{obs['id']} 不适用于当前网型。")
        f,b,L,cov,comps=_observation(net,obs,points,index)
        if require_values and not design and L is None: raise AdjustmentError(f"{obs['id']} 尚无实测值。可先使用“布网设计”，或双击观测录入数据。")
        start=len(predicted)
        rows.extend(b); predicted.extend(f); observed.extend(f if design or L is None else L)
        angular.extend([obs["kind"] in ANGLES]*len(f)); blocks.append(cov)
        labels.extend([obs["id"]+":"+str(c) for c in comps]); groups.append((obs["id"],start,len(f)))
    n,u=len(predicted),len(keys)
    if n>500: raise AdjustmentError("标量观测数超过当前版本 500 上限。GNSS 基线按 3 个分量计数。")
    B=np.asarray(rows,dtype=float).reshape(n,u)
    f,L=np.asarray(predicted),np.asarray(observed)
    angular=np.asarray(angular,dtype=bool); l=L-f
    l[angular]=(l[angular]+math.pi)%(2*math.pi)-math.pi
    Q=np.zeros((n,n)); offset=0
    for block in blocks:
        size=len(block); Q[offset:offset+size,offset:offset+size]=block; offset+=size
    P=np.linalg.solve(Q,np.eye(n)) if n else Q.copy()
    C=[]; d=[]
    for constraint in net.constraints:
        z=np.zeros(u); actual=0.
        for name,coef in constraint["terms"].items():
            parts=name.split(".")
            if len(parts)!=2 or parts[0] not in points or parts[1] not in net.axes:
                raise AdjustmentError(f"限制中的参数 {name} 不存在或不属于当前坐标域。")
            point,axis=parts; coef=finite(coef,"限制系数")
            actual+=coef*points[point][axis]
            if (point,axis) in index: z[index[point,axis]]+=coef
        if not np.any(z): raise AdjustmentError("限制条件没有待估参数；请删去已由固定坐标确定的限制。")
        C.append(z); d.append(actual-finite(constraint["value"],"限制值"))
    c=len(C); C=np.asarray(C,dtype=float).reshape(c,u); d=np.asarray(d)
    if c:
        U,s,Vt=np.linalg.svd(C,full_matrices=True)
        rank=int(np.linalg.matrix_rank(C))
        if rank!=c: raise AdjustmentError("限制条件线性相关或矛盾，请保留独立限制。")
        Z=Vt[c:].T; xp=-Vt[:c].T@((U.T@d)/s)
    else: Z=np.eye(u); xp=np.zeros(u)
    effective=B@Z
    R=np.linalg.cholesky(P).T if n else np.zeros((0,0))
    weighted=R@effective
    rank=int(np.linalg.matrix_rank(weighted)) if weighted.size else 0
    defect=u-c-rank
    stats={"n":n,"t":rank,"r":n-rank,"parameters":u,"constraints":c,"defect":defect,
           "points":len(points),"observations":len(groups),"solvable":bool(n and defect==0)}
    return LinearizedNetwork(B,l,L,f,Q,sym(P),C,d,keys,labels,angular,groups,Z,xp,stats)


def automatic_matrices(m: LinearizedNetwork):
    effective=m.B@m.Z
    if effective.shape[1]:
        U,_,_=np.linalg.svd(effective,full_matrices=True)
        rank=m.stats["t"]
        A=U[:,rank:].T
    else: A=np.eye(len(m.L))
    l_reduced=m.l-m.B@m.xp
    result={"B · 观测方程系数":m.B,"l · 常数项":m.l,"P · 权阵":m.P,"Q · 观测协因数":m.Q,
            "N = Bᵀ P B":sym(m.B.T@m.P@m.B),"u = Bᵀ P l":m.B.T@m.P@m.l,
            "A · 条件系数（零空间基）":A,"w · 条件闭合差":A@l_reduced,
            "A_c · 附参条件观测系数":np.eye(len(m.L)),"B_c · 附参条件参数系数":-effective,
            "w_c · 附参条件常数":l_reduced}
    if len(m.C):
        result.update({"C · 限制系数":m.C,"d · 限制常数":m.d,
                       "增广法方程系数":np.block([[m.B.T@m.P@m.B,m.C.T],[m.C,np.zeros((len(m.C),len(m.C)))]])})
    return result


def _step(m, method, precision):
    n,u=m.B.shape
    if u:
        kwargs=dict(B=m.B,l=m.l,P=m.P,precision=precision)
        if len(m.C): kwargs.update(C=m.C,d=m.d)
        canonical=solve("indirect_constraints" if len(m.C) else "indirect",**kwargs)
        effective=m.B@m.Z; lred=m.l-m.B@m.xp
        if method=="condition":
            matrices=automatic_matrices(m); A=matrices["A · 条件系数（零空间基）"]
            v=solve("condition",A=A,w=A@lred,P=m.P,precision=precision).v if len(A) else np.zeros(n)
            R=np.linalg.cholesky(m.P).T
            z=np.linalg.lstsq(R@effective,R@(lred+v),rcond=None)[0] if effective.shape[1] else np.empty(0)
            dx=m.xp+m.Z@z
        elif method=="condition_parameters" and effective.shape[1]:
            selected=solve("condition_parameters",A=np.eye(n),B=-effective,w=lred,P=m.P,precision=precision)
            dx=m.xp+m.Z@selected.x; v=selected.v
        else: dx=canonical.x; v=canonical.v
        if not np.allclose(v,canonical.v,atol=1e-8,rtol=1e-6):
            raise AdjustmentError("所选模型与观测方程的残差校核不一致，请检查数值尺度。")
        canonical.x=dx
        return canonical
    v=-m.l
    omega=float(v@m.P@v); posterior=math.sqrt(omega/n)
    return AdjustmentResult("indirect",n,0,0,n,v,np.empty(0),m.L,m.L+v,None,None,
                            m.Q,m.Q,np.zeros((n,n)),np.zeros((0,0)),omega,posterior,
                            1. if precision=="prior" else posterior,precision,0.,0.,[],{})


@dataclass
class NetworkSolution:
    model: LinearizedNetwork
    initial_model: LinearizedNetwork
    points: dict
    result: AdjustmentResult
    iterations: int
    design: bool
    method: str
    corrections: np.ndarray
    matrices: dict
    point_precision: list
    relative_precision: list
    iteration_trace: list = field(default_factory=list)

    def to_dict(self):
        return {"statistics":self.model.stats,"design":self.design,"method":self.method,"iterations":self.iterations,
                "points":self.points,"parameter_order":[p+"."+a for p,a in self.model.keys],
                "observation_order":self.model.labels,"angular_rows":self.model.angular.tolist(),
                "corrections":self.corrections.tolist(),"result":self.result.to_dict(),
                "matrices":{k:v.tolist() for k,v in self.matrices.items()},
                "point_precision":self.point_precision,"relative_precision":self.relative_precision,
                "iteration_trace":self.iteration_trace}


def adjust_network(net: Network, design=True, precision="prior", max_iterations=40):
    if design: precision="prior"
    points=deepcopy(net.points)
    initial=linearize(net,points,design,require_values=True)
    if not initial.stats["n"]: raise AdjustmentError("请先布点并添加观测。")
    if initial.stats["defect"]:
        raise AdjustmentError(f"基准或几何约束不足：尚有 {initial.stats['defect']} 个不可确定的自由度。请增加固定坐标、独立限制或有效观测。")
    if design and len(initial.d) and np.max(np.abs(initial.d))>1e-8:
        raise AdjustmentError("布网设计的近似坐标尚不满足精确限制。请调整点坐标或限制值；录入实测值后也可使用实测平差求解。")
    base=np.array([points[p][a] for p,a in initial.keys])
    converged=False; trace=[]
    for iteration in range(1,max_iterations+1):
        m=linearize(net,points,design,require_values=True)
        result=_step(m,net.method,precision)
        dx=result.x
        trace.append({'iteration':iteration,'max_correction':float(np.max(np.abs(dx))) if dx.size else 0.,
                      'weighted_sum_linearized':result.weighted_sum,'corrections':dx.tolist()})
        for (p,a),change in zip(m.keys,dx): points[p][a]+=float(change)
        if design or not dx.size or np.max(np.abs(dx))<1e-8:
            converged=True; break
    if not converged: raise AdjustmentError(f"迭代 {max_iterations} 次仍未收敛，请检查近似坐标、观测值、网形或限制条件。")
    final=linearize(net,points,design,require_values=True)
    # Evaluate covariance at final geometry; report residuals in the original units.
    result=_step(final,net.method,precision)
    result.observed=initial.L
    exact=final.predicted-initial.L
    exact[final.angular]=(exact[final.angular]+math.pi)%(2*math.pi)-math.pi
    result.v=exact
    result.adjusted=final.predicted.copy()
    result.weighted_sum=float(exact@final.P@exact)
    result.posterior_sigma=math.sqrt(result.weighted_sum/result.dof) if result.dof and not design else None
    result.precision_sigma=1. if precision=="prior" else result.posterior_sigma
    result.constraint_error=float(np.max(np.abs(final.d))) if len(final.d) else 0.
    total=np.array([points[p][a] for p,a in final.keys])-base
    matrices=automatic_matrices(final)
    matrices.update({"B₀ · 首次线性化系数":initial.B,"l₀ · 首次常数项":initial.l,
                     "Qxx · 参数协因数":result.qxx,"Q_L̂ · 观测平差值协因数":result.q_adjusted,"Qvv · 改正数协因数":result.qvv})
    if result.precision_sigma is not None: matrices["CovXX · 参数协方差"]=result.qxx*result.precision_sigma**2
    solution=NetworkSolution(final,initial,points,result,iteration,design,net.method,total,matrices,[],[])
    solution.iteration_trace=trace
    _precision(net,solution)
    return solution


def _precision(net,solution):
    r,m=solution.result,solution.model
    index={key:i for i,key in enumerate(m.keys)}
    if r.precision_sigma is None: return
    cov=r.qxx*r.precision_sigma**2
    def element(p,a,q,b):
        return float(cov[index[p,a],index[q,b]]) if (p,a) in index and (q,b) in index else 0.
    for point in solution.points:
        data={"point":point}
        for axis in net.axes: data["m"+axis]=math.sqrt(max(0.,element(point,axis,point,axis)))
        if net.family=="GNSS网":data["m3D"]=math.sqrt(sum(data["m"+a]**2 for a in net.axes))
        if "X" in net.axes:
            block=np.array([[element(point,a,point,b) for b in ("X","Y")] for a in ("X","Y")])
            values,vectors=np.linalg.eigh(block); values=np.maximum(values,0)
            data.update({"mp":math.sqrt(float(values.sum())),"major":math.sqrt(float(values[1])),
                         "minor":math.sqrt(float(values[0])),"azimuth":math.degrees(math.atan2(vectors[1,1],vectors[0,1]))%180})
        solution.point_precision.append(data)
    for obs in net.observations:
        if not obs.get("enabled",True) or obs["kind"] in ("angle","azimuth","coordinate"): continue
        a,b=obs["points"][:2]
        if net.axes==("H",):
            var=element(a,"H",a,"H")+element(b,"H",b,"H")-2*element(a,"H",b,"H")
            solution.relative_precision.append({"observation":obs["id"],"sigma":math.sqrt(max(0.,var)),"quantity":"高差"})
        else:
            axes=net.axes if obs["kind"]=="gnss" else ("X","Y")
            delta=np.array([solution.points[b][axis]-solution.points[a][axis] for axis in axes])
            length=float(np.linalg.norm(delta))
            if length<1e-12: continue
            J=np.zeros(len(m.keys))
            for axis,g in zip(axes,delta/length):
                if (a,axis) in index:J[index[a,axis]]-=g
                if (b,axis) in index:J[index[b,axis]]+=g
            sigma=math.sqrt(max(0.,float(J@cov@J)))
            solution.relative_precision.append({"observation":obs["id"],"sigma":sigma,"length":length,
                                               "relative_denominator":length/sigma if sigma>0 else None,"quantity":"边长"})


def parse_constraints(text):
    """Safe explicit syntax: P1.X:1 P2.X:1 = 200 (no expression evaluation)."""
    result=[]
    for line_no,line in enumerate(text.splitlines(),1):
        line=line.split("#",1)[0].strip()
        if not line: continue
        if line.count("=")!=1: raise AdjustmentError(f"限制第 {line_no} 行应有一个等号。")
        left,right=line.split("="); terms={}
        for term in left.split():
            if term.count(":")!=1: raise AdjustmentError(f"限制第 {line_no} 行格式为 P1.X:1 P2.X:1 = 200。")
            name,coef=term.split(":"); terms[name]=terms.get(name,0)+finite(coef,"限制系数")
        if not terms: raise AdjustmentError("限制左侧不能为空。")
        result.append({"terms":terms,"value":finite(right,"限制值")})
    return result


def network_report(net,solution):
    m,r=solution.model,solution.result
    lines=["控制网自动建模与精度报告",net.name,"="*65,
           f"网型：{net.family}；方法：{MODEL_NAMES[net.method]}；模式：{'布网设计 / 先验精度' if solution.design else '实测平差'}",
           "坐标：长度为米；平面网 X 北、Y 东，水准 H 为高程；角度方程内部为弧度。",
           "GNSS 的坐标、基线及协方差必须在同一 XYZ 直角框架（可为地心框架）；不自动转换至 ENU。GNSS 椭圆仅为 XY 投影，长轴方向从 +X 向 +Y；m3D 为三维点位中误差。",
           "各观测块之间按不相关处理。",
           "标量统计："+"；".join(f"{k}={v}" for k,v in m.stats.items()),
           "t=自由参数观测系数的秩；r=n−t；基准亏损=参数个数−限制秩−t。GNSS 每条基线计 3 个标量观测。",
           f"迭代次数：{solution.iterations}；精度基准：{'先验' if r.precision_source == 'prior' else '后验'}；所用标准差尺度 σ={r.precision_sigma}；vᵀPv={r.weighted_sum:.10g}",
           "参数顺序："+", ".join(p+"."+a for p,a in m.keys),"观测顺序："+", ".join(m.labels)]
    if solution.design: lines.append("设计模式仅由网形与输入标准差预估精度，不把几何模拟值当作实测值，也不以零残差推断零误差。")
    elif r.posterior_sigma is not None: lines.append(f"后验单位权中误差：{r.posterior_sigma:.10g}（P 由实际标准差生成，参考先验 σ₀=1）")
    else: lines.append("自由度为 0，后验精度不可估计，可选择先验基准。")
    lines.extend(["","参数总改正数（相对初始近似坐标）",format_array(solution.corrections),"","点位精度（米，椭圆为 1σ 半轴，不表示联合 68% 置信区间）"])
    for item in solution.point_precision: lines.append(str(item))
    lines.extend(["","相对精度（包含参数间协方差）"]+[str(x) for x in solution.relative_precision])
    if not solution.design:
        lines.extend(["","观测改正数（角度显示角秒，其他为米）"])
        for i,label in enumerate(m.labels): lines.append(f"{label}: {r.v[i]/ARCSEC if m.angular[i] else r.v[i]:.10g} {'″' if m.angular[i] else 'm'}")
    lines.extend(["","矩阵（B、N 在最终坐标处线性化；B₀、l₀ 为首次线性化；Q=P⁻¹）"])
    for name,value in solution.matrices.items(): lines.extend([name,format_array(value),""])
    lines.extend(["条件法的 A 为左零空间生成的等价线性化条件基，其行不一定对应单一几何闭合环。",
                  "附参条件法保留全部自由参数；存在精确限制时先做零空间消元。",
                  "非线性计算依赖合理近似坐标，不进行地球曲率、投影、仪器系统误差或地心坐标转换。",
                  "文本可能折叠大矩阵，完整数值见结果 JSON。"])
    return "\n".join(lines)


def example_network(family="水准网", measured=False):
    net=Network(family,family+"示例")
    positions=[("A",0,0,100,0),("B",0,120,101.2,2),("C",90,130,102.0,5),("D",100,10,101.5,3)]
    for name,X,Y,H,Z in positions:
        fixed=net.axes if (name=="A" or (name=="B" and family not in ("水准网","GNSS网","坐标观测网"))) else ()
        net.add_point(name,X,Y,H,Z,fixed)
    edges=[("A","B"),("B","C"),("C","D"),("D","A"),("A","C"),("B","D")]
    if family=="水准网":
        for a,b in edges[:5]: net.add_observation("height",[a,b])
    elif family=="GNSS网":
        for a,b in edges[:5]: net.add_observation("gnss",[a,b],covariance=[[.000025,.000004,0],[.000004,.000036,.000002],[0,.000002,.000064]])
    elif family=="坐标观测网":
        for p in ("B","C","D"): net.add_observation("coordinate",[p])
        for a,b in edges[1:3]:net.add_observation("distance",[a,b])
    else:
        if family in ("导线网","测边网","边角网"):
            for a,b in (edges[:4] if family=="导线网" else edges):net.add_observation("distance",[a,b])
        if family in ("导线网","测角网","边角网"):
            for ids in [("B","A","C"),("A","B","C"),("B","A","D"),("A","B","D"),("B","C","D"),("A","D","C")]:net.add_observation("angle",ids)
    if measured:
        rng=np.random.default_rng(25)
        for obs in net.observations:
            f,_,_,cov,_=_observation(net,obs,net.points,{})
            values=f+rng.multivariate_normal(np.zeros(len(f)),cov)
            obs["value"]=float(math.degrees(values[0])) if obs["kind"] in ANGLES else values.tolist()
        for p,data in net.points.items():
            for axis in net.axes:
                if axis not in data["fixed"]:data[axis]+=float(rng.normal(0,.15))
    return net
