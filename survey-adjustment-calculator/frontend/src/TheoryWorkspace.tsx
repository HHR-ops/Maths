import { useEffect, useRef, useState } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { ArrowLeft, ArrowRight, BookOpen, CheckCircle2, ExternalLink, FlaskConical, Search } from 'lucide-react'
import knowledge from './knowledge.json'
import { rpc } from './api'
import type { Project, Selection, Solution } from './types'
import { number } from './types'
import { Button, Field } from './ui'

type Section = { title: string; paragraphs?: string[]; formulas?: string[]; table?: { headers: string[]; rows: string[][] }; callout?: string; example?: { title: string; text: string } }
type Article = { id: string; chapter: string; title: string; summary: string; minutes: number; tags: string[]; sections: Section[]; lab?: string; quiz: { question: string; options: string[]; answer: number; explanation: string }; sources: string[]; related: string[] }
type LabResult = { metrics: { label: string; value: number; unit: string }[]; notes: string[]; plot: { type: string; points?: number[][]; k?: number; major?: number; minor?: number; factor?: number; azimuth?: number | null; covariance?: number[][]; terms?: number[]; weights?: number[]; residuals?: number[]; rejected?: boolean; statistic?: number; lower?: number; upper?: number } }
const articles = knowledge.articles as Article[]
const byId = Object.fromEntries(articles.map(a => [a.id, a]))

export function Formula({ value }: { value: string }) {
  return <div className="theory-formula" dangerouslySetInnerHTML={{ __html: katex.renderToString(value, { displayMode: true, throwOnError: false, trust: false, strict: 'error' }) }} />
}

const labs: Record<string, { title: string; formula: string; defaults: Record<string, string>; fields: { key: string; label: string; min?: string; max?: string; step?: string; options?: [string, string][] }[] }> = {
  normal: { title: '正态分布的区间概率', formula: 'P(-k\\leq Z\\leq k)=2\\Phi(k)-1', defaults: { k: '1' }, fields: [{ key: 'k', label: '区间半宽 k（σ 的倍数）', min: '.1', max: '4', step: '.1' }] },
  propagation: { title: '相关输入怎样影响和与差？', formula: '\\sigma_y^2=\\sigma_1^2+\\sigma_2^2+2b\\rho\\sigma_1\\sigma_2', defaults: { s1: '3', s2: '4', rho: '0', b: '1' }, fields: [{ key: 's1', label: '输入 1 标准差（mm）', min: '.000001' }, { key: 's2', label: '输入 2 标准差（mm）', min: '.000001' }, { key: 'rho', label: '相关系数 ρ', min: '-1', max: '1', step: '.1' }, { key: 'b', label: '计算关系', options: [['1', 'y = x₁ + x₂'], ['-1', 'y = x₁ − x₂']] }] },
  'weighted-mean': { title: '三次观测的加权平均', formula: '\\widehat L=\\frac{\\sum_i L_i/\\sigma_i^2}{\\sum_i1/\\sigma_i^2}', defaults: { l1: '10', l2: '12', l3: '9', s1: '1', s2: '2', s3: '1' }, fields: [1, 2, 3].flatMap(i => [{ key: 'l'+i, label: '观测 '+i+'（mm）', step: '.1' }, { key: 's'+i, label: '标准差 '+i+'（mm）', min: '.000001', step: '.1' }]) },
  'global-test': { title: '整体模型的双侧 χ² 检验', formula: 'T=v^{\\mathsf T}Pv/\\sigma_0^2\\sim\\chi_f^2', defaults: { omega: '8', dof: '5', sigma0: '1', alpha: '.05' }, fields: [{ key: 'omega', label: '残差平方和 vᵀPv', min: '0', step: '.1' }, { key: 'dof', label: '残差自由度 f', min: '1', step: '1' }, { key: 'sigma0', label: '已知先验 σ₀', min: '.000001', step: '.1' }, { key: 'alpha', label: '显著性水平 α', options: [['.01', '0.01'], ['.05', '0.05'], ['.1', '0.10']] }] },
  ellipse: { title: '从协方差到误差椭圆', formula: 'a_p=k_p\\sqrt{\\lambda_{\\max}},\\quad b_p=k_p\\sqrt{\\lambda_{\\min}}', defaults: { sx: '2', sy: '1', rho: '.3', coverage: '95', source: 'prior', dof: '10' }, fields: [{ key: 'sx', label: 'X 标准差（mm）', min: '.000001', step: '.1' }, { key: 'sy', label: 'Y 标准差（mm）', min: '.000001', step: '.1' }, { key: 'rho', label: '相关系数 ρ（绝对值 < 1）', min: '-.999999', max: '.999999', step: '.1' }, { key: 'coverage', label: '显示椭圆', options: [['standard', '1σ 标准椭圆'], ['95', '95% 联合置信椭圆'], ['99', '99% 联合置信椭圆']] }, { key: 'source', label: '精度基准', options: [['prior', '协方差已知（χ²）'], ['posterior', '后验尺度估计（F）']] }, { key: 'dof', label: '后验尺度自由度 f', min: '1', step: '1' }] }
}

function LabPlot({ result }: { result: LabResult }) {
  const p = result.plot
  if (p.type === 'normal') {
    const points = p.points!, k = p.k!, sx = (z: number) => 36+(z+4)*41, sy = (y: number) => 190-y*370
    const line = points.map(([z, y]) => sx(z)+','+sy(y)).join(' ')
    const subset = points.filter(([z]) => z >= -k-1e-12 && z <= k+1e-12)
    const edge = Math.exp(-k*k/2)/Math.sqrt(2*Math.PI)
    const area = sx(-k)+',190 '+sx(-k)+','+sy(edge)+' '+subset.map(([z,y]) => sx(z)+','+sy(y)).join(' ')+' '+sx(k)+','+sy(edge)+' '+sx(k)+',190'
    return <svg className="lab-plot" viewBox="0 0 400 230" role="img" aria-label="标准正态分布，阴影表示所选区间概率"><line x1="36" y1="190" x2="364" y2="190" className="plot-axis" /><polygon points={area} className="normal-area" /><polyline points={line} className="plot-curve" />{[-3,-2,-1,0,1,2,3].map(z => <g key={z}><line x1={sx(z)} x2={sx(z)} y1="190" y2="195" className="plot-axis" /><text x={sx(z)} y="212" textAnchor="middle">{z}</text></g>)}<text x="200" y="25" textAnchor="middle">Z ~ N(0, 1)</text><text x="377" y="193">z</text></svg>
  }
  if (p.type === 'ellipse') {
    const a = p.major!, b = p.minor!, k = p.factor!, angle = (p.azimuth ?? 0)*Math.PI/180, scale = 75/(a*k)
    const ellipse = (factor: number) => Array.from({ length: 181 }, (_, i) => { const t = i*Math.PI/90, x = factor*(a*Math.cos(t)*Math.cos(angle)-b*Math.sin(t)*Math.sin(angle)), y = factor*(a*Math.cos(t)*Math.sin(angle)+b*Math.sin(t)*Math.cos(angle)); return (200+y*scale)+','+(122-x*scale) }).join(' ')
    return <div><svg className="lab-plot" viewBox="0 0 400 250" role="img" aria-label="误差椭圆，X 向上，Y 向右，虚线为标准椭圆"><line x1="200" y1="20" x2="200" y2="224" className="plot-axis" /><line x1="90" y1="122" x2="310" y2="122" className="plot-axis" /><text x="208" y="25">X</text><text x="310" y="115">Y</text><polyline points={ellipse(k)} className="ellipse-area" /><polyline points={ellipse(1)} className="ellipse-standard" /><circle cx="200" cy="122" r="2" fill="currentColor" /><line x1="30" x2="80" y1="220" y2="220" className="plot-axis" /><text x="55" y="242" textAnchor="middle">{number(50/scale,3)} mm</text></svg><small className="lab-legend"><i />所选椭圆 <span>┄</span>1σ 标准椭圆 · 图按比例自适应</small></div>
  }
  if (p.type === 'global-test') return <div className={'lab-test-status '+(p.rejected ? 'rejected' : '')}><CheckCircle2 size={24} /><strong>{p.rejected ? '拒绝原假设 H₀' : '未拒绝原假设 H₀'}</strong><p>双侧检验的未拒绝域 [{number(p.lower,4)}, {number(p.upper,4)}]</p><span className="mono">T = {number(p.statistic,6)}</span></div>
  if (p.type === 'weighted-mean') return <div className="theory-table-wrap"><table className="theory-table"><thead><tr><th>观测</th><th>权 1/σ²</th><th>改正数 v（mm）</th></tr></thead><tbody>{p.weights!.map((w,i) => <tr key={i}><td>{i+1}</td><td>{number(w,6)}</td><td>{number(p.residuals![i],6)}</td></tr>)}</tbody></table></div>
  return <div className="propagation-terms">{p.terms!.map((v,i) => <div key={i}><span>{['σ₁²','σ₂²','2bρσ₁σ₂'][i]}</span><b>{number(v,4)} mm²</b><div className="term-track"><i className={v<0 ? 'negative' : ''} style={{ width: Math.max(1,Math.abs(v)/Math.max(...p.terms!.map(Math.abs),1)*100)+'%' }} /></div></div>)}</div>
}

function Experiment({ kind }: { kind: string }) {
  const definition = labs[kind]
  const [inputs, setInputs] = useState(definition.defaults)
  const [result, setResult] = useState<LabResult | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(true)
  const request = useRef(0)
  useEffect(() => {
    const id = ++request.current
    setPending(true); setResult(null); setError('')
    const timer = setTimeout(() => {
      void rpc<LabResult>('theory_experiment', { kind, inputs }).then(data => { if (id === request.current) setResult(data) }).catch(e => { if (id === request.current) setError((e as Error).message) }).finally(() => { if (id === request.current) setPending(false) })
    }, 180)
    return () => { clearTimeout(timer); request.current++ }
  }, [inputs, kind])
  return <section className="theory-experiment" aria-label="交互例题"><div className="theory-section-heading"><FlaskConical size={18} /><div><small>动手算一算</small><h3>{definition.title}</h3></div><Button size="sm" variant="ghost" onClick={() => setInputs({ ...definition.defaults })}>恢复例题</Button></div><Formula value={definition.formula} /><div className="lab-inputs">{definition.fields.filter(f => !(kind === 'ellipse' && f.key === 'dof' && inputs.source !== 'posterior')).map(f => <Field key={f.key} label={f.label}>{f.options ? <select aria-label={f.label} value={inputs[f.key]} onChange={e => setInputs({ ...inputs, [f.key]: e.target.value })}>{f.options.map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select> : <input aria-label={f.label} type="number" min={f.min} max={f.max} step={f.step || 'any'} value={inputs[f.key]} onChange={e => setInputs({ ...inputs, [f.key]: e.target.value })} />}</Field>)}</div><div aria-live="polite" aria-busy={pending}>{error && <p className="lab-error" role="alert">{error}</p>}{pending && <p className="muted">正在更新例题…</p>}{result && <><div className="lab-output"><LabPlot result={result} /><div className="lab-metrics">{result.metrics.map(m => <div key={m.label}><span>{m.label}</span><strong data-metric={m.label}>{number(m.value,6)}<small>{m.unit}</small></strong></div>)}</div></div><ul className="lab-notes">{result.notes.map(n => <li key={n}>{n}</li>)}</ul></>}</div><p className="lab-scope">例题独立计算，不修改当前项目或平差成果。</p></section>
}

function CurrentResult({ solution, project, selection, onNavigate }: { solution: Solution | null; project: Project; selection: Selection; onNavigate: (id: string) => void }) {
  if (!solution) return <div className="theory-context"><small>当前项目</small><strong>{project.name}</strong><p>当前控制网尚未计算。计算后，可在这里查看观测数、精度基准与检验结果。</p></div>
  const chosen = solution.point_precision.find(p => p.point === (selection?.type === 'point' ? selection.id : '')) || solution.point_precision.find(p => Number(p.major ?? p.mH ?? 0)>0)
  const g = solution.diagnostics.global_test
  return <div className="theory-context"><small>当前控制网 · {solution.design ? '设计预测' : '实测平差'}</small><strong>{project.name}</strong><dl><dt>n / t / r</dt><dd>{solution.statistics.n} / {solution.statistics.t} / {solution.statistics.r}</dd><dt>精度尺度</dt><dd>{solution.result.precision_source === 'prior' ? '先验' : '后验'} · {number(solution.result.precision_sigma)}</dd></dl>{g && <p>整体检验 T = {number(g.statistic,4)}，f = {g.dof}，p = {number(g.p_value,4)}。{g.rejected ? '拒绝原假设。' : '未拒绝原假设。'}</p>}{chosen && <p>{chosen.point}：{typeof chosen.major === 'number' ? <>1σ 半轴 {number(chosen.major*1000,3)} / {number(Number(chosen.minor)*1000,3)} mm；{project.family === 'GNSS网' ? 'XYZ 框架的 XY 投影。' : 'X 北、Y 东。'}</> : <>高程标准差 {number(Number(chosen.mH)*1000,3)} mm。</>}</p>}<button onClick={() => onNavigate('precision')}>精度指标说明 <ArrowRight size={13} /></button><button onClick={() => onNavigate('diagnostics')}>检验结果说明 <ArrowRight size={13} /></button></div>
}

export default function TheoryWorkspace({ active, onNavigate, project, solution, selection, onReturn }: { active: string; onNavigate: (id: string) => void; project: Project; solution: Solution | null; selection: Selection; onReturn: () => void }) {
  const article = byId[active] || articles[0]
  const [query, setQuery] = useState('')
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [glossary, setGlossary] = useState(false)
  const articleRef = useRef<HTMLElement>(null)
  useEffect(() => { articleRef.current?.scrollIntoView({ block: 'start' }) }, [active])
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  const matches = (a: Article) => terms.every(term => JSON.stringify(a).toLocaleLowerCase().includes(term))
  const visible = articles.filter(matches)
  const index = articles.indexOf(article)
  const chapter = knowledge.chapters.find(c => c.id === article.chapter)!
  return <div className="theory-workspace"><aside className="theory-toc"><label className="theory-search"><Search size={16} /><input aria-label="搜索理论知识" placeholder="搜索：权阵、误差椭圆…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button aria-label="清除理论搜索" onClick={() => setQuery('')}>×</button>}</label><div className="theory-toc-heading"><span>六章 · 十三篇</span><button onClick={() => setGlossary(!glossary)}>符号速查</button></div>{query && <p className="search-count" role="status">找到 {visible.length} 篇；点击条目阅读全文</p>}{knowledge.chapters.map((c, i) => { const children = visible.filter(a => a.chapter === c.id); return children.length ? <div className="theory-chapter" key={c.id}><h3><span>0{i+1}</span>{c.title}</h3>{children.map(a => <button key={a.id} onClick={() => onNavigate(a.id)} className={a.id === article.id ? 'active' : ''} aria-current={a.id === article.id ? 'page' : undefined}>{a.title}<small>{a.minutes} 分钟{a.lab ? ' · 交互例题' : ''}</small></button>)}</div> : null })}{!visible.length && <p className="theory-search-empty">没有匹配内容。可尝试“协方差”“残差”或“正态”。</p>}<CurrentResult solution={solution} project={project} selection={selection} onNavigate={onNavigate} /><Button className="full-width" size="sm" onClick={onReturn}><ArrowLeft size={14} />返回计算工作台</Button></aside><article className="theory-article panel" ref={articleRef}><header className="theory-article-header"><div className="theory-breadcrumb"><BookOpen size={15} /><span>{chapter.title}</span><span>·</span><span>约 {article.minutes} 分钟</span><span className="theory-offline">离线可读</span></div><h2>{article.title}</h2><p>{article.summary}</p><div className="theory-tags">{article.tags.map(t => <span key={t}>{t}</span>)}</div></header>{glossary && <section className="theory-glossary"><h3>符号及含义</h3><dl>{knowledge.symbols.map(([symbol,description]) => <div key={symbol}><dt>{symbol}</dt><dd>{description}</dd></div>)}</dl></section>}<div className="theory-reading">{article.sections.map((s,i) => <section key={s.title} className="theory-section"><h3><span>{i+1}</span>{s.title}</h3>{s.paragraphs?.map(p => <p key={p}>{p}</p>)}{s.formulas?.map(f => <Formula key={f} value={f} />)}{s.table && <div className="theory-table-wrap"><table className="theory-table"><thead><tr>{s.table.headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{s.table.rows.map((row,j) => <tr key={j}>{row.map((cell,k) => <td key={k}>{cell}</td>)}</tr>)}</tbody></table></div>}{s.example && <div className="theory-example"><small>算例</small><strong>{s.example.title}</strong><p>{s.example.text}</p></div>}{s.callout && <div className="theory-callout">{s.callout}</div>}</section>)}{article.lab && <Experiment key={article.id} kind={article.lab} />}<section className="theory-quiz" aria-label="理解自测"><small>理解自测</small><h3>{article.quiz.question}</h3><div>{article.quiz.options.map((o,i) => <button key={o} onClick={() => setAnswers({ ...answers, [article.id]: i })} className={answers[article.id] === i ? (i === article.quiz.answer ? 'correct' : 'incorrect') : ''} aria-pressed={answers[article.id] === i}><span>{String.fromCharCode(65+i)}</span>{o}</button>)}</div>{answers[article.id] !== undefined && <p role="status">{answers[article.id] === article.quiz.answer ? '回答正确。' : '再想一想。'}{article.quiz.explanation}</p>}</section><section className="theory-related"><h3>接着阅读</h3>{article.related.map(id => <button key={id} onClick={() => onNavigate(id)}>{byId[id].title}<ArrowRight size={14} /></button>)}</section><section className="theory-sources"><h3>参考资料</h3><p>正文与例题在本机完整保存；以下原始资料链接需联网。公式采用本程序的符号与改正数约定。</p>{article.sources.map(id => { const source = knowledge.sources.find(s => s.id === id)!; return <a key={id} href={source.url} target="_blank" rel="noopener noreferrer"><span><strong>{source.title}</strong><small>{source.note}</small></span><ExternalLink size={14} /></a> })}</section><nav className="theory-pagination" aria-label="章节翻页"><Button disabled={index === 0} onClick={() => onNavigate(articles[index-1].id)}><ArrowLeft size={14} />上一篇</Button><span>{index+1} / {articles.length}</span><Button disabled={index === articles.length-1} onClick={() => onNavigate(articles[index+1].id)}>下一篇<ArrowRight size={14} /></Button></nav></div></article></div>
}
