import { Matrix, SingularValueDecomposition, EigenvalueDecomposition } from 'ml-matrix'
import type { Scene } from './model.ts'
import { status } from './model.ts'
export const DEG = Math.PI/180
export function direction(azimuth: number, elevation: number): [number,number,number] {
  const az = azimuth*DEG, el = elevation*DEG
  return [Math.cos(el)*Math.sin(az), Math.cos(el)*Math.cos(az), Math.sin(el)]
}
export interface Result {
  valid: boolean; used: string[]; rank: number; condition: number | null; reason: string
  G: number[][]; singular: number[]; Q: number[][] | null; covariance: number[][] | null
  dop: { GDOP: number; PDOP: number; HDOP: number; VDOP: number; TDOP: number } | null
  ellipse: { major: number; minor: number; azimuth: number; factor: number } | null
  ellipsoid: { axes: number[]; vectors: number[][]; factor: number } | null
}
export function analyze(scene: Scene): Result {
  const used = scene.satellites.filter(s => status(s,scene) === 'used')
  const G = used.map(s => { const [e,n,u] = direction(s.azimuth,s.elevation); return [-e,-n,-u,1] })
  const result: Result = { valid: false, used: used.map(s => s.id), rank: 0, condition: null, reason: '', G, singular: [], Q: null, covariance: null, dop: null, ellipse: null, ellipsoid: null }
  if (!used.length) return { ...result, reason: '没有参与计算的卫星。请降低截止角、调整遮挡或启用卫星。' }
  const svd = new SingularValueDecomposition(new Matrix(G), { autoTranspose: true })
  const singular = svd.diagonal, max = singular[0] || 0
  result.singular = singular; result.rank = singular.filter(s => s > max*1e-10).length
  if (used.length < 4) return { ...result, reason: '至少需要 4 颗卫星，才能同时估计 E、N、U 与接收机钟差。' }
  if (result.rank < 4) return { ...result, reason: '几何矩阵秩为 '+result.rank+'，位置与钟差不能完全分离。请改变卫星仰角或方位分布。' }
  result.condition = singular[0]/singular[3]
  const V = svd.rightSingularVectors
  const Q = Array.from({length:4},(_,i) => Array.from({length:4},(_,j) => singular.reduce((sum,s,k) => sum+V.get(i,k)*V.get(j,k)/(s*s),0)))
  const root = (n: number) => Math.sqrt(Math.max(n,0))
  const HDOP = root(Q[0][0]+Q[1][1]), VDOP = root(Q[2][2]), TDOP = root(Q[3][3])
  const PDOP = Math.hypot(HDOP,VDOP), GDOP = Math.hypot(PDOP,TDOP)
  const covariance = Q.slice(0,3).map(row => row.slice(0,3).map(v => v*scene.sigma**2))
  const [ee,en] = covariance[0], nn = covariance[1][1]
  const mean = (ee+nn)/2, radius = Math.hypot((ee-nn)/2,en)
  const theta = .5*Math.atan2(2*en,ee-nn)
  const ellipseFactor = scene.confidence === '95' ? Math.sqrt(5.991464547107979) : 1
  const ellipsoidFactor = scene.confidence === '95' ? Math.sqrt(7.814727903251179) : 1
  const evd = new EigenvalueDecomposition(new Matrix(covariance), { assumeSymmetric: true })
  const order = [0,1,2].sort((a,b) => evd.realEigenvalues[b]-evd.realEigenvalues[a])
  return { ...result, valid: true, Q, covariance, dop: { GDOP,PDOP,HDOP,VDOP,TDOP }, reason: result.condition > 1e4 ? '几何接近退化，预测误差对方向变化非常敏感。' : '',
    ellipse: { major: root(mean+radius)*ellipseFactor, minor: root(mean-radius)*ellipseFactor, azimuth: ((90-theta/DEG)%180+180)%180, factor: ellipseFactor },
    ellipsoid: { axes: order.map(i => root(evd.realEigenvalues[i])*ellipsoidFactor), vectors: order.map(i => [0,1,2].map(j => evd.eigenvectorMatrix.get(j,i))), factor: ellipsoidFactor },
  }
}
export function format(value: number | null | undefined, digits = 2) { return value == null || !Number.isFinite(value) ? '—' : value >= 10000 ? value.toExponential(2) : value.toFixed(digits) }
export function csv(scene: Scene, result: Result) {
  const rows: (string|number)[][] = [['编号','方位角_deg','仰角_deg','状态','截止角_deg','测距标准差_m']]
  for (const sat of scene.satellites) rows.push([sat.id,sat.azimuth,sat.elevation,status(sat,scene),scene.mask,scene.sigma])
  rows.push([],['指标','值'],['参与卫星数',result.used.length],['矩阵秩',result.rank],['条件数',result.condition ?? '不可解算'])
  if(result.dop) for(const [key,v] of Object.entries(result.dop)) rows.push([key,v])
  if(result.ellipse) rows.push(['水平椭圆长半轴_m',result.ellipse.major],['水平椭圆短半轴_m',result.ellipse.minor],['长轴方位角_deg',result.ellipse.azimuth])
  rows.push(['模型','卫星方向；单一接收机钟差；等精度、不相关测距；钟差以米表示'],['误差区域',scene.confidence==='95'?'95% 高斯置信区域':'协方差标准椭圆/椭球'])
  return rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n')
}
