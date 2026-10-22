export interface Satellite { id: string; azimuth: number; elevation: number; enabled: boolean }
export interface Obstruction { enabled: boolean; start: number; width: number; height: number }
export interface Scene { name: string; satellites: Satellite[]; mask: number; sigma: number; confidence: 'standard' | '95'; obstruction: Obstruction }
export interface Snapshot { id: string; scene: Scene }
export interface Project { format: 'gnss-geometry-lab'; version: 1; scene: Scene; snapshots: Snapshot[] }
export type Status = 'used' | 'disabled' | 'masked' | 'blocked'
export const colors = { used: '#d9b970', disabled: '#716f76', masked: '#8e9299', blocked: '#e48d76' }
export const statusNames: Record<Status,string> = { used: '参与计算', disabled: '已停用', masked: '低于截止角', blocked: '被遮挡' }
export const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value))
const sat = (azimuth: number, elevation: number, i: number): Satellite => ({ id: 'S'+String(i+1).padStart(2,'0'), azimuth, elevation, enabled: true })
const base: Array<[number,number]> = [[0,25],[60,55],[120,25],[180,55],[240,25],[300,55],[90,75],[275,12]]
export const presets = [
  { id: 'balanced', name: '均匀分布', caption: '多方向、多仰角', icon: 'orbit' },
  { id: 'clustered', name: '集中一侧', caption: '观察方向不均的影响', icon: 'focus' },
  { id: 'obstructed', name: '局部遮挡', caption: '模拟建筑遮挡扇区', icon: 'building' },
  { id: 'four', name: '最少四星', caption: '三个位置分量与钟差', icon: 'crosshair' },
  { id: 'degenerate', name: '同仰角退化', caption: '卫星够多，仍不能解算', icon: 'alert' },
]
export function preset(id: string): Scene {
  let directions = base
  if (id === 'clustered') directions = [[15,15],[22,35],[30,55],[38,25],[46,45],[55,65],[65,20],[75,40]]
  if (id === 'degenerate') directions = Array.from({ length: 8 }, (_,i) => [i*45,35])
  if (id === 'four') directions = [[0,20],[120,20],[240,20],[0,90]]
  if (id === 'obstructed') directions = [...base,[35,45],[165,35],[215,65],[335,40]]
  return { name: presets.find(p => p.id === id)?.name || '自定义场景', satellites: directions.map(([az,el],i) => sat(az,el,i)), mask: 10, sigma: 1, confidence: 'standard', obstruction: { enabled: id === 'obstructed', start: 60, width: 145, height: 65 } }
}
export function initialProject(): Project { return { format: 'gnss-geometry-lab', version: 1, scene: preset('balanced'), snapshots: [] } }
export function status(s: Satellite, scene: Scene): Status {
  if (!s.enabled) return 'disabled'
  if (s.elevation < scene.mask) return 'masked'
  const o = scene.obstruction, delta = (s.azimuth-o.start+360)%360
  if (o.enabled && delta <= o.width && s.elevation <= o.height) return 'blocked'
  return 'used'
}
function finite(v: unknown, min: number, max: number) { return typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max }
function validateScene(v: unknown): Scene {
  if (!v || typeof v !== 'object') throw Error('场景格式无效。')
  const s = v as Scene
  if (typeof s.name !== 'string' || s.name.length > 80 || !Array.isArray(s.satellites) || s.satellites.length > 64) throw Error('场景名称或卫星列表无效（最多 64 颗）。')
  if (!finite(s.mask,0,85) || !finite(s.sigma,.01,100) || !['standard','95'].includes(s.confidence)) throw Error('截止高度角、测距标准差或置信设置无效。')
  const ids = new Set<string>()
  for (const p of s.satellites) {
    if (!p || typeof p.id !== 'string' || !/^[A-Za-z0-9_-]{1,16}$/.test(p.id) || ids.has(p.id) || !finite(p.azimuth,0,360) || !finite(p.elevation,0,90) || typeof p.enabled !== 'boolean') throw Error('卫星编号须唯一，方位角为 0–360°，仰角为 0–90°。')
    ids.add(p.id)
  }
  const o = s.obstruction
  if (!o || typeof o.enabled !== 'boolean' || !finite(o.start,0,360) || !finite(o.width,0,360) || !finite(o.height,0,90)) throw Error('遮挡扇区参数无效。')
  return copy(s)
}
export function validateProject(value: unknown): Project {
  if (!value || typeof value !== 'object') throw Error('项目格式无效。')
  const p = value as Project
  if (p.format !== 'gnss-geometry-lab' || p.version !== 1 || !Array.isArray(p.snapshots) || p.snapshots.length > 4) throw Error('请选择 GNSS 实验室的 .gnss.json 项目。')
  const scene = validateScene(p.scene), ids = new Set<string>()
  const snapshots = p.snapshots.map(s => {
    if (!s || typeof s.id !== 'string' || s.id.length > 80 || ids.has(s.id)) throw Error('对照场景编号无效。')
    ids.add(s.id); return { id: s.id, scene: validateScene(s.scene) }
  })
  return { format: 'gnss-geometry-lab', version: 1, scene, snapshots }
}
