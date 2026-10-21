import { useState } from 'react'
import { Check, Copy, Download } from 'lucide-react'
import type { Entity, Matrix, Selection, StepMatrix } from './types'
import { number } from './types'
import { Button, Empty } from './ui'
import { saveFile } from './api'

export default function MatrixViewer({ matrices, order, notify, metadata, onSelect }: { matrices: Record<string, Matrix>; order?: { parameters: string[]; observations: string[] }; notify: (message: string) => void; metadata?: Record<string, StepMatrix>; onSelect?: (s: Selection) => void }) {
  const keys = Object.keys(matrices)
  const [key, setKey] = useState(keys[0] || '')
  const [copied, setCopied] = useState(false)
  const selected = keys.includes(key) ? key : keys[0]
  const matrix = matrices[selected] || []
  const rows: number[][] = matrix.map(r => Array.isArray(r) ? r : [r])
  const meta = metadata?.[selected]
  const label = (entity: Entity | undefined, index: number) => entity?.type && entity.id && onSelect ? <button className="matrix-entity" aria-label={'定位 '+entity.label} onClick={() => onSelect({ type: entity.type!, id: entity.id! })}>{entity.label}</button> : entity?.label || index+1
  return <div className="matrix-viewer"><div className="table-actions"><select aria-label="选择矩阵" value={selected || ''} onChange={e => setKey(e.target.value)}>{keys.map(k => <option key={k}>{k}</option>)}</select><span className="matrix-dimension mono">{rows.length} × {rows[0]?.length || 0}</span><div className="spacer" /><Button size="sm" variant="ghost" disabled={!rows.length} onClick={async () => { try { await navigator.clipboard.writeText(rows.map(r => r.join('\t')).join('\n')); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { notify('剪贴板不可用，请使用导出 CSV。') } }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? '已复制' : '复制'}</Button><Button size="sm" variant="ghost" disabled={!rows.length} onClick={async () => { try { await saveFile(rows.map(r => r.join(',')).join('\n'), selected.split(' · ')[0]+'.csv') } catch (e) { notify((e as Error).message) } }}><Download size={14} />CSV</Button></div>
    {rows.length ? <div className="data-scroll matrix-scroll"><table className="data-table matrix-table"><thead><tr><th>#</th>{rows[0]?.slice(0, 40).map((_, i) => <th key={i}>{label(meta?.columns?.[i], i)}</th>)}</tr></thead><tbody>{rows.slice(0, 80).map((row, i) => <tr key={i}><th>{label(meta?.rows?.[i], i)}</th>{row.slice(0, 40).map((v, j) => <td key={j}>{number(v, 8)}</td>)}</tr>)}</tbody></table></div> : <Empty title="空矩阵" text="当前模型没有对应方程或未知参数。" />}
    <div className="table-footnote">{rows.length > 80 || (rows[0]?.length || 0) > 40 ? '预览最多 80 行 × 40 列；复制、CSV 和结果 JSON 包含完整数值。' : '矩阵按完整双精度计算，当前显示 8 位小数。'}{order && <details><summary>查看参数与观测顺序</summary><p>参数：{order.parameters.join(', ') || '无'}</p><p>观测：{order.observations.join(', ') || '无'}</p></details>}</div>
  </div>
}
