import { useState } from 'react'
import { Check, Trash2 } from 'lucide-react'
import type { Observation, Point, Project } from './types'
import { axes, kinds, values } from './types'
import { Button, Field, Modal } from './ui'
import { rpc } from './api'

export function PointProperties({ id, point, project, onSave, onDelete }: { id: string; point: Point; project: Project; onSave: (p: Point) => void; onDelete: () => void }) {
  const [data, setData] = useState(Object.fromEntries(['X', 'Y', 'Z', 'H'].map(a => [a, String(point[a as 'X'])])))
  const [fixed, setFixed] = useState(point.fixed)
  const [error, setError] = useState('')
  const fields = project.family === '水准网' ? ['H', 'X', 'Y'] : axes(project.family)
  return <form onSubmit={e => { e.preventDefault(); const p = { ...point, fixed }; for (const a of fields) { if (!data[a].trim() || !Number.isFinite(Number(data[a]))) { setError('坐标须为有限数值。'); return } p[a as 'X'] = Number(data[a]) } onSave(p); setError('') }}><div className="property-title"><span className="point-avatar">{id.slice(0, 2)}</span><div><strong>{id}</strong><small>{fixed.length ? '含固定分量' : '待定控制点'}</small></div></div><div className="property-fields">{fields.map(a => <Field key={a} label={a+(project.family === '水准网' && a !== 'H' ? ' / 示意坐标 m' : ' / m')}><input aria-label={'点坐标 '+a} inputMode="decimal" value={data[a]} onChange={e => setData({ ...data, [a]: e.target.value })} /></Field>)}</div><div className="property-section-label">固定坐标分量</div><div className="checkbox-row">{axes(project.family).map(a => <label key={a}><input type="checkbox" checked={fixed.includes(a)} onChange={e => setFixed(e.target.checked ? [...fixed, a] : fixed.filter(k => k !== a))} />{a}</label>)}</div><p className="muted small">固定分量作为已知值，不计入待估参数。</p>{error && <div className="inline-error" role="alert">{error}</div>}<Button type="submit" className="full-width"><Check size={14} />应用坐标</Button><Button type="button" variant="ghost" className="full-width danger-text" onClick={onDelete}><Trash2 size={14} />删除控制点</Button></form>
}

export function ObservationEditor({ project, observation, names, onClose, onSave }: { project: Project; observation: Observation | null; names: Record<string, string>; onClose: () => void; onSave: (o: Observation) => void }) {
  const defaults = () => { let i = 1; while (project.observations.some(o => o.id === 'O'+i)) i++; return { id: 'O'+i, kind: kinds(project.family)[0], points: [], value: null, sigma: project.family === '水准网' ? .001 : .003, covariance: null, components: axes(project.family), enabled: true } as Observation }
  const [o, setO] = useState(observation || defaults)
  const [value, setValue] = useState(values(o.value))
  const [sigma, setSigma] = useState(values(o.sigma))
  const [covariance, setCovariance] = useState(values(o.covariance))
  const [correlated, setCorrelated] = useState(Boolean(o.covariance))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const count = o.kind === 'angle' ? 3 : o.kind === 'coordinate' ? 1 : 2
  const angular = ['angle', 'azimuth'].includes(o.kind)
  const as = axes(project.family)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    const updated = { ...o, value: value.trim() || null, sigma, covariance: correlated ? covariance : null }
    const candidate = { ...project, observations: observation ? project.observations.map(item => item.id === observation.id ? updated : item) : [...project.observations, updated] }
    try { await rpc('validate', { project: candidate }); onSave(updated) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <Modal open title={observation ? '编辑观测 '+o.id : '添加观测'} description="角度值支持十进制度与 123:45:56.7；角度标准差使用角秒，其余长度使用米。" onClose={onClose}><form onSubmit={submit}><div className="form-grid"><Field label="观测编号"><input aria-label="观测编号" value={o.id} onChange={e => setO({ ...o, id: e.target.value })} required /></Field><Field label="观测类型"><select aria-label="观测类型" value={o.kind} onChange={e => { setO({ ...o, kind: e.target.value, points: [], components: as }); setValue(''); setSigma(['angle', 'azimuth'].includes(e.target.value) ? '2' : '.003'); setCorrelated(false) }}>{kinds(project.family).map(k => <option value={k} key={k}>{names[k]}</option>)}</select></Field></div><div className="form-grid">{Array.from({ length: count }, (_, i) => <Field key={i} label={o.kind === 'angle' ? ['后视点', '测站', '前视点'][i] : count === 1 ? '控制点' : ['起点', '终点'][i]}><select aria-label={'观测点 '+(i+1)} required value={o.points[i] || ''} onChange={e => { const p = [...o.points]; p[i] = e.target.value; setO({ ...o, points: p.slice(0, count) }) }}><option value="">选择控制点</option>{Object.keys(project.points).map(id => <option key={id}>{id}</option>)}</select></Field>)}</div>
    {o.kind === 'coordinate' && <Field label="观测坐标分量"><span className="checkbox-row">{as.map(a => <label key={a}><input type="checkbox" checked={o.components.includes(a)} onChange={e => setO({ ...o, components: e.target.checked ? as.filter(k => k === a || o.components.includes(k)) : o.components.filter(k => k !== a) })} />{a}</label>)}</span></Field>}
    <Field label={o.kind === 'gnss' ? '实测基线 ΔX, ΔY, ΔZ / m' : o.kind === 'coordinate' ? '实测坐标 '+o.components.join(', ')+' / m' : '实测值 / '+(angular ? '°' : 'm')} hint="布网设计可留空；实测平差须填写每条启用观测的实测值。"><input aria-label="实测值" value={value} onChange={e => setValue(e.target.value)} placeholder={o.kind === 'gnss' ? '例如：120.002, 80.001, 5.003' : '输入实测值'} /></Field>
    <div className="segmented weight-switch"><button type="button" className={!correlated ? 'active' : ''} onClick={() => setCorrelated(false)}>标准差 σ</button><button type="button" className={correlated ? 'active' : ''} onClick={() => setCorrelated(true)}>完整协方差阵</button></div>
    {correlated ? <Field label="协方差阵 / 各分量原始单位²" hint={angular ? '角度协方差使用 rad²；必须为对称正定阵。' : 'GNSS 使用同一 XYZ 框架的 3×3 对称正定阵，单位 m²。'}><textarea aria-label="协方差阵" className="mono" rows={4} value={covariance} onChange={e => setCovariance(e.target.value)} placeholder="0.000025  0.000004  0&#10;0.000004  0.000036  0.000002&#10;0  0.000002  0.000064" /></Field> : <Field label={'标准差 / '+(angular ? '″' : 'm')} hint={o.kind === 'gnss' || o.kind === 'coordinate' ? '可填一个公共标准差，或按分量顺序填写多个正数。' : '填写正数。各观测块之间视为不相关。'}><input aria-label="标准差" value={sigma} onChange={e => setSigma(e.target.value)} required /></Field>}
    <label className="check-label"><input type="checkbox" checked={o.enabled} onChange={e => setO({ ...o, enabled: e.target.checked })} />参与平差计算</label>{error && <div className="inline-error" role="alert">{error}</div>}<div className="modal-footer"><Button type="button" onClick={onClose}>取消</Button><Button type="submit" variant="default" disabled={busy}>{busy ? '校验中…' : '保存观测'}</Button></div></form></Modal>
}

export function ConstraintEditor({ project, onClose, onSave }: { project: Project; onClose: () => void; onSave: (p: Project) => void }) {
  const [text, setText] = useState(project.constraints.map(c => Object.entries(c.terms).map(([name, coef]) => `${name}:${coef}`).join(' ')+' = '+c.value).join('\n'))
  const [error, setError] = useState('')
  return <Modal open title="精确限制条件" description="每行填写一个线性限制；左侧为 点号.分量:系数，右侧为绝对坐标组合值。" onClose={onClose}><form onSubmit={async e => { e.preventDefault(); try { onSave(await rpc<Project>('constraints', { project, text })) } catch (e) { setError((e as Error).message) } }}><Field label="限制方程" hint="例：B.X:1 C.X:1 = 200；清空文本可删除全部限制。"><textarea aria-label="限制方程" rows={7} className="mono" placeholder="B.X:1 C.X:1 = 200" value={text} onChange={e => setText(e.target.value)} /></Field><p className="muted small">可用参数：{Object.entries(project.points).flatMap(([id, p]) => axes(project.family).filter(a => !p.fixed.includes(a)).map(a => id+'.'+a)).join(', ') || '暂无'}</p>{error && <div className="inline-error" role="alert">{error}</div>}<div className="modal-footer"><Button type="button" onClick={onClose}>取消</Button><Button type="submit" variant="default">应用限制</Button></div></form></Modal>
}
