import { useState } from 'react'
import { ArrowRight, GitCompareArrows, LoaderCircle } from 'lucide-react'
import type { CalculationStep, MethodComparison, Selection } from './types'
import { number } from './types'
import { Button } from './ui'
import MatrixViewer from './MatrixViewer'

export default function StepsPanel({ steps, notify, onSelect, onCompare }: { steps: CalculationStep[]; notify: (s: string) => void; onSelect?: (s: Selection) => void; onCompare?: () => Promise<MethodComparison> }) {
  const [active, setActive] = useState(0)
  const [comparison, setComparison] = useState<MethodComparison | null>(null)
  const [busy, setBusy] = useState(false)
  const step = steps[Math.min(active, steps.length-1)]
  return <div className="steps-panel"><div className="steps-navigation" aria-label="计算步骤">{steps.map((s, i) => <button key={s.id} className={active === i ? 'active' : ''} onClick={() => setActive(i)}><span>{i+1}</span>{s.title}</button>)}</div><div className="step-content"><div className="step-heading"><div><small>STEP {active+1} / {steps.length}</small><strong>{step.title}</strong></div>{onCompare && <Button size="sm" onClick={async () => { setBusy(true); try { setComparison(await onCompare()) } catch (e) { notify((e as Error).message) } finally { setBusy(false) } }} disabled={busy}>{busy ? <LoaderCircle size={14} className="spin" /> : <GitCompareArrows size={14} />}四法对照</Button>}</div><div className="step-formula mono">{step.formula}</div><p className="step-description">{step.description}</p>{step.metrics && <div className="step-metrics">{Object.entries(step.metrics).map(([key, value]) => <div key={key}><small>{key}</small><strong className="mono">{number(value, 8)}</strong></div>)}</div>}
      <MatrixViewer key={step.id} matrices={Object.fromEntries(Object.entries(step.matrices).map(([name, matrix]) => [name, matrix.data]))} metadata={step.matrices} onSelect={onSelect} notify={notify} />
      {step.iterations && <><div className="section-caption">迭代记录（每次线性化）</div><div className="data-scroll"><table className="data-table"><thead><tr><th>次数</th><th>最大坐标改正 / m</th><th>线性化 vᵀPv</th><th>参数改正向量 / m</th></tr></thead><tbody>{step.iterations.map(r => <tr key={r.iteration}><td>{r.iteration}</td><td className="mono">{number(r.max_correction, 10)}</td><td className="mono">{number(r.weighted_sum_linearized, 8)}</td><td className="mono">{r.corrections.slice(0, 12).map(x => number(x, 8)).join(', ')}{r.corrections.length > 12 ? ' …' : ''}</td></tr>)}</tbody></table></div></>}
      <div className="step-footer"><span>矩阵中的观测和参数标签可用于定位；无直接几何对应关系的条件基保持编号。</span>{active < steps.length-1 && <Button size="sm" variant="ghost" onClick={() => setActive(active+1)}>下一步<ArrowRight size={13} /></Button>}</div>
    </div>{comparison && <div className="method-comparison" data-testid="method-comparison"><div className="section-caption">四种等价平差模型对照 · 基准：{comparison.baseline}</div><div className="data-scroll"><table className="data-table"><thead><tr><th>方法</th><th>n / t / r</th><th>vᵀPv</th><th>最大坐标差 / m</th><th>最大残差差（内部单位）</th><th>最大 Qxx 差</th></tr></thead><tbody>{comparison.results.map(row => <tr key={row.method}><td>{row.name}</td><td>{row.n} / {row.t} / {row.r}</td><td className="mono">{number(row.weighted_sum, 8)}</td><td className="mono">{number(row.max_coordinate_difference, 10)}</td><td className="mono">{number(row.max_residual_difference, 10)}</td><td className="mono">{number(row.max_cofactor_difference, 10)}</td></tr>)}</tbody></table></div><div className="table-footnote">{comparison.note}</div></div>}</div>
}
