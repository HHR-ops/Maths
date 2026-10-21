import { useRef, useState } from 'react'
import { Download, FileSpreadsheet, LoaderCircle, Upload, X } from 'lucide-react'
import type { ImportPreview, ImportTable, Project } from './types'
import { axes } from './types'
import { rpc, saveBinary } from './api'
import { Button, Field, Modal } from './ui'

const labels: Record<string, string> = { name: '点号', X: 'X 坐标', Y: 'Y 坐标', Z: 'Z 坐标', H: 'H 高程', fixed: '固定分量', fixed_X: '固定 X', fixed_Y: '固定 Y', fixed_Z: '固定 Z', fixed_H: '固定 H', unit: '观测 / 坐标单位', id: '观测编号', kind: '观测类型', from: '起点 / 测站', to: '终点 / 目标', back: '后视点', fore: '前视点', points: '连接点列表', value: '观测值', value_x: 'ΔX / X', value_y: 'ΔY / Y', value_z: 'ΔZ / Z', value_h: 'H 观测值', sigma: '标准差', sigma_x: 'σX', sigma_y: 'σY', sigma_z: 'σZ', sigma_h: 'σH', covariance: '完整协方差阵', components: '坐标分量', enabled: '参与计算', sigma_unit: '标准差单位', covariance_unit: '协方差单位', cxx: 'Cxx', cxy: 'Cxy', cxz: 'Cxz', cyy: 'Cyy', cyz: 'Cyz', czz: 'Czz' }
const primaryFields = ['name', 'X', 'Y', 'Z', 'H', 'fixed', 'id', 'kind', 'from', 'to', 'back', 'fore', 'value', 'sigma']
export default function ImportWizard({ project, onClose, onImport, notify }: { project: Project; onClose: () => void; onImport: (p: Project, measured: boolean) => void; notify: (s: string) => void }) {
  const [tables, setTables] = useState<ImportTable[]>([])
  const [fields, setFields] = useState<Record<string, string[]>>({ points: [], observations: [] })
  const [selected, setSelected] = useState(0)
  const [policy, setPolicy] = useState('append')
  const [units, setUnits] = useState({ length: 'm', length_sigma: 'm', angle: 'deg', angle_sigma: 'arcsec', covariance: 'auto' })
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [previewKey, setPreviewKey] = useState('')
  const [measured, setMeasured] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const current = useRef('')
  const fingerprint = JSON.stringify({ tables, policy, units })
  current.current = fingerprint
  const fresh = preview && previewKey === fingerprint ? preview : null
  const table = tables[selected]
  const updateTable = (data: Partial<ImportTable>) => setTables(v => v.map((t, i) => i === selected ? { ...t, ...data } : t))
  const readFiles = async (files: FileList) => {
    setBusy(true); setError('')
    try {
      const added: ImportTable[] = []
      for (const file of Array.from(files)) {
        if (file.size > 4*1024*1024) throw new Error(file.name+' 超过 4 MB。')
        const content = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file) })
        const result = await rpc<{ tables: ImportTable[]; fields: Record<string, string[]> }>('import_read', { filename: file.name, content_base64: content })
        added.push(...result.tables); setFields(result.fields)
      }
      setTables(v => [...v, ...added]); setSelected(tables.length)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false); if (input.current) input.current.value = '' }
  }
  const check = async () => {
    setBusy(true); setError(''); const key = fingerprint
    try {
      const options = { ...units } as Record<string, string>; if (options.covariance === 'auto') delete options.covariance
      const result = await rpc<ImportPreview>('import_preview', { project, tables, policy, units: options })
      if (current.current === key) { setPreview(result); setPreviewKey(key) }
    } catch (e) { if (current.current === key) setError((e as Error).message) } finally { setBusy(false) }
  }
  const download = async (kind: string) => { try { const file = await rpc<{ filename: string; content_base64: string }>('import_template', { family: project.family, kind }); await saveBinary(file.content_base64, file.filename) } catch (e) { notify((e as Error).message) } }
  const mappingField = (key: string) => <Field key={key} label={(labels[key] || key)+(table?.type === 'points' && (key === 'name' || axes(project.family).includes(key)) ? ' *' : '')}><select aria-label={'映射 '+key} value={table.mapping[key] ?? ''} onChange={e => { const maps = { ...table.mapping }; if (e.target.value === '') delete maps[key]; else maps[key] = Number(e.target.value); updateTable({ mapping: maps }) }}><option value="">不导入此列</option>{table.headers.map((h, i) => <option value={i} key={i}>{h || '未命名列 '+(i+1)}</option>)}</select></Field>
  return <Modal open title="批量导入控制网数据" description="支持 XLSX、CSV、TSV；先匹配列与检查数据，再一次性写入项目。长度单位与标准差单位可以分别设置。" onClose={onClose} wide><div className="import-wizard"><div className="import-toolbar"><Button onClick={() => input.current?.click()} disabled={busy}><Upload size={15} />选择数据文件</Button><span className="muted">可同时选择控制点表和观测表</span><div className="spacer" /><Button size="sm" variant="ghost" onClick={() => download('xlsx')}><Download size={14} />Excel 模板</Button><Button size="sm" variant="ghost" onClick={() => download('points')}>点表 CSV</Button><Button size="sm" variant="ghost" onClick={() => download('observations')}>观测 CSV</Button></div><input type="file" accept=".xlsx,.csv,.tsv,.xls" multiple hidden ref={input} aria-label="批量数据文件" onChange={e => { if (e.target.files?.length) void readFiles(e.target.files) }} />
      <div className="form-grid import-options"><Field label="导入方式"><select aria-label="批量导入方式" value={policy} onChange={e => setPolicy(e.target.value)}><option value="append">追加到当前控制网（点号不可重复）</option><option value="replace">替换当前控制网的点、观测与限制</option></select></Field><Field label="当前网型"><input value={project.family} disabled /></Field></div>
      {!tables.length && <div className="import-dropzone"><FileSpreadsheet size={35} /><strong>从 Excel 或 CSV 开始</strong><span>每个文件最大 4 MB，每次最多 2000 行。模板中的示例可直接导入试算。</span></div>}
      {tables.length > 0 && <><div className="import-table-tabs">{tables.map((t, i) => <button key={i} className={selected === i ? 'active' : ''} onClick={() => setSelected(i)}><FileSpreadsheet size={13} />{t.name}<span>{t.rows.length} 行</span></button>)}<Button size="icon" variant="ghost" aria-label="移除当前导入表" onClick={() => { setTables(v => v.filter((_, i) => i !== selected)); setSelected(0) }}><X size={14} /></Button></div>{table && <><div className="form-grid"><Field label="表格用途"><select aria-label="导入表格用途" value={table.type} onChange={e => updateTable({ type: e.target.value, mapping: table.mappings[e.target.value] || {} })}><option value="points">控制点表</option><option value="observations">观测表</option><option value="ignore">忽略此表</option></select></Field><Field label="文件与工作表"><input value={table.filename+' / '+table.name} disabled /></Field></div>{table.type !== 'ignore' && <><div className="mapping-grid">{(fields[table.type] || []).filter(key => primaryFields.includes(key)).map(mappingField)}</div><details className="import-more"><summary>分量、协方差与单位列映射</summary><div className="mapping-grid">{(fields[table.type] || []).filter(key => !primaryFields.includes(key)).map(mappingField)}</div></details><div className="data-scroll import-preview-table"><table className="data-table"><thead><tr><th>原表行</th>{table.headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead><tbody>{table.rows.slice(0, 6).map((row, i) => <tr key={i}><td>{table.source_rows[i]}</td>{row.map((v, j) => <td key={j}>{String(v ?? '')}</td>)}</tr>)}</tbody></table></div><div className="table-footnote">预览前 6 行；实际检查全部选中数据。含公式的单元格需要先粘贴为值。</div></>}</>}
      <details className="import-more"><summary>默认单位（原表单位列和列名括号内的单位优先）</summary><div className="mapping-grid">{Object.entries({ length: ['坐标与长度', 'm', 'mm', 'cm'], length_sigma: ['长度标准差', 'm', 'mm', 'cm'], angle: ['角度值', 'deg', 'rad', 'dms'], angle_sigma: ['角度标准差', 'arcsec', 'deg', 'rad'], covariance: ['协方差', 'auto', 'm2', 'mm2', 'cm2', 'rad2', 'deg2', 'arcsec2'] }).map(([key, [label, ...options]]) => <Field key={key} label={label}><select aria-label={'默认单位 '+key} value={units[key as keyof typeof units]} onChange={e => setUnits({ ...units, [key]: e.target.value })}>{options.map(v => <option key={v} value={v}>{v === 'auto' ? '按观测类型：长度 m² / 角度 rad²' : v}</option>)}</select></Field>)}</div></details>
      <label className="check-label"><input type="checkbox" checked={measured} onChange={e => setMeasured(e.target.checked)} />导入后切换到实测平差（需全部启用观测都有实测值）</label></>}
      {error && <div className="inline-error" role="alert">{error}</div>}
      {fresh && <div className={'import-result '+(fresh.ok ? 'import-ok' : 'import-error')} data-testid="import-validation"><strong>{fresh.ok ? '数据校验通过' : `发现 ${fresh.error_count} 项错误，尚未写入项目`}</strong><p>新增 {fresh.added_points} 个点，{fresh.added_observations} 条观测{fresh.statistics ? `；n=${fresh.statistics.n}，t=${fresh.statistics.t}，r=${fresh.statistics.r}` : ''}。</p>{fresh.statistics?.defect ? <p>基准尚有 {fresh.statistics.defect} 个自由度未确定，可导入后设置固定分量或限制。</p> : null}{fresh.errors.length > 0 && <div className="import-errors"><table className="data-table"><thead><tr><th>文件 / 表</th><th>原表行</th><th>问题</th></tr></thead><tbody>{fresh.errors.slice(0, 50).map((e, i) => <tr key={i}><td>{e.file} / {e.table}</td><td>{e.row ?? '—'}</td><td>{e.message}</td></tr>)}</tbody></table></div>}{fresh.warnings.length > 0 && <details><summary>{fresh.warnings.length} 项精度提示</summary>{fresh.warnings.map((w, i) => <p key={i}>{w}</p>)}</details>}</div>}
      <div className="modal-footer"><Button onClick={onClose}>取消</Button><Button onClick={check} disabled={busy || !tables.length}>{busy ? <LoaderCircle size={14} className="spin" /> : null}检查并预览</Button><Button variant="default" disabled={busy || !fresh?.ok} onClick={() => { if (fresh?.project) onImport(fresh.project, measured) }}>{policy === 'replace' ? '替换并导入' : '确认导入'}</Button></div></div></Modal>
}
