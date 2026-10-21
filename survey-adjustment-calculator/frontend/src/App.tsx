import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, ArrowDownToLine, ArrowRight, BookOpen, Braces, Calculator, Check, CheckCircle2, ChevronRight, CircleHelp, Compass, FilePlus2, FileSpreadsheet, FlaskConical, FolderOpen, Layers3, LoaderCircle, Network as NetworkIcon, PanelLeftClose, PanelLeftOpen, Play, Redo2, Save, Settings2, ShieldCheck, Sigma, SlidersHorizontal, Trash2, Undo2, X } from 'lucide-react'
import type { Analysis, Bootstrap, Draft, Observation, Point, Project, RecalculationComparison, Selection, Solution } from './types'
import { axes, number, values } from './types'
import { json, rpc, saveFile } from './api'
import { Button, Field, Modal } from './ui'
import NetworkCanvas from './NetworkCanvas'
import DataPanels from './DataPanels'
import { ConstraintEditor, ObservationEditor, PointProperties } from './Editors'
import MatrixWorkspace from './MatrixWorkspace'
import ImportWizard from './ImportWizard'
import TheoryWorkspace from './TheoryWorkspace'

const shortNames: Record<string, string> = { condition: '条件平差', condition_parameters: '附参条件平差', indirect: '间接平差', indirect_constraints: '附限间接平差' }

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null)
  const [history, setHistory] = useState<{ past: Project[]; present: Project | null; future: Project[] }>({ past: [], present: null, future: [] })
  const project = history.present
  const [mode, setMode] = useState('network')
  const [theoryOpen, setTheoryOpen] = useState(false)
  const [theoryTopic, setTheoryTopic] = useState('sources')
  const switchMode = (next: string) => { setMode(next); setTheoryOpen(false) }
  const openTheory = (topic = theoryTopic) => { setTheoryTopic(topic); setTheoryOpen(true) }
  const [model, setModel] = useState('indirect')
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [solution, setSolution] = useState<Solution | null>(null)
  const [design, setDesign] = useState(true)
  const [precision, setPrecision] = useState('prior')
  const [selection, setSelection] = useState<Selection>(null)
  const [tab, setTab] = useState('observations')
  const [fitVersion, setFitVersion] = useState(0)
  const [showPrecision, setShowPrecision] = useState(false)
  const [busy, setBusy] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [startupError, setStartupError] = useState('')
  const [toast, setToast] = useState('')
  const [help, setHelp] = useState(false)
  const [bulkImport, setBulkImport] = useState(false)
  const [comparison, setComparison] = useState<RecalculationComparison | null>(null)
  const [about, setAbout] = useState(false)
  const [constraints, setConstraints] = useState(false)
  const [editingObs, setEditingObs] = useState<Observation | null | undefined>(undefined)
  const [confirm, setConfirm] = useState<{ title: string; text: string; action: () => void } | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [calculateTick, setCalculateTick] = useState(0)
  const [saved, setSaved] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const revision = useRef(0)
  const requestId = useRef(0)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const saveSequence = useRef(0)
  const notify = useCallback((message: string) => { setToast(message); if (toastTimer.current) clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(''), 4200) }, [])
  const invalidate = () => { revision.current++; setSolution(null); setShowPrecision(false); setError(''); setComparison(null) }
  const commit = (next: Project, reset = false) => {
    invalidate()
    setHistory(h => ({ past: reset || !h.present ? [] : [...h.past.slice(-39), h.present], present: next, future: [] }))
    if (reset) { setSelection(null); setFitVersion(v => v+1) }
  }
  const undo = () => { if (!history.past.length) return; invalidate(); setSelection(null); setHistory(h => ({ past: h.past.slice(0, -1), present: h.past[h.past.length-1], future: h.present ? [h.present, ...h.future] : h.future })) }
  const redo = () => { if (!history.future.length) return; invalidate(); setSelection(null); setHistory(h => ({ past: h.present ? [...h.past, h.present] : h.past, present: h.future[0], future: h.future.slice(1) })) }
  useEffect(() => {
    let disposed = false
    void (async () => {
      try {
        const data = await rpc<Bootstrap>('bootstrap'); let initial = data.project; let restored = false
        let initialDrafts = data.examples
        try {
          const stored = await rpc<unknown>('load_workspace') || JSON.parse(localStorage.getItem('survey-react-workspace-v04') || 'null')
          if (stored) { const parsed = stored as { project: Project; drafts: Record<string, Draft> }; initial = await rpc<Project>('validate', { project: parsed.project }); if (parsed.drafts && Object.values(parsed.drafts).every(d => d && typeof d === 'object' && Object.values(d).every(v => typeof v === 'string'))) initialDrafts = { ...data.examples, ...parsed.drafts }; restored = true }
        } catch { /* An invalid old draft must never block startup. */ }
        if (disposed) return
        setBootstrap(data); setDrafts(initialDrafts); setHistory({ past: [], present: initial, future: [] }); setFitVersion(1); setSaved(json(initial)); if (restored) notify('已恢复上次的本地工作草稿。')
      } catch (e) { if (!disposed) setStartupError((e as Error).message) }
    })()
    return () => { disposed = true }
  }, [notify])
  useEffect(() => {
    if (!project) return
    const id = ++requestId.current
    setAnalysis(null); setAnalyzing(true)
    const timer = setTimeout(async () => {
      try { const data = await rpc<Analysis>('analyze', { project, design }); if (id === requestId.current) { setAnalysis(data); setError('') } }
      catch (e) { if (id === requestId.current) setError((e as Error).message) }
      finally { if (id === requestId.current) setAnalyzing(false) }
    }, 150)
    return () => { clearTimeout(timer); requestId.current++ }
  }, [project, design])
  useEffect(() => {
    if (!project || !bootstrap) return
    const workspace = { project, drafts }
    window.__surveyWorkspace = workspace
    try { localStorage.setItem('survey-react-workspace-v04', json(workspace)) } catch { /* Explicit save remains available if storage is full. */ }
    const sequence = ++saveSequence.current
    const timer = setTimeout(() => { void rpc('save_workspace', { workspace, sequence }).catch(() => notify('自动保存草稿未完成，请使用“保存项目”保留当前内容。')) }, 300)
    return () => clearTimeout(timer)
  }, [project, drafts, bootstrap, notify])
  const currentDocument = project ? mode === 'network' ? project : { format: 'survey-adjustment-project', version: 1, model, data: drafts[model] } : null
  const dirty = Boolean(currentDocument && json(currentDocument) !== saved)
  useEffect(() => { window.__surveyDirty = dirty }, [dirty])
  const loadExample = async (family: string) => { try { const next = await rpc<Project>('example', { family, measured: !design }); commit(next, true); setTab('observations'); notify('已载入'+family+(design ? '设计示例。' : '实测示例。')) } catch (e) { notify((e as Error).message) } }
  const requestReplace = (action: () => void, text: string) => { if (project && (history.past.length || dirty)) setConfirm({ title: '替换当前控制网？', text: text+'当前内容可先通过“保存项目”保留。', action }); else action() }
  const calculate = async () => {
    if (theoryOpen) return
    if (mode === 'matrix') { setCalculateTick(v => v+1); return }
    if (!project) return
    setBusy(true); setError(''); const rev = revision.current
    try { const result = await rpc<Solution>('solve', { project, design, precision }); if (revision.current === rev) { setSolution(result); setShowPrecision(true); setTab('precision'); notify(design ? '设计精度计算完成。' : '平差完成，成果与精度已更新。') } }
    catch (e) { if (revision.current === rev) setError((e as Error).message) }
    finally { setBusy(false) }
  }
  const save = async () => { if (!currentDocument) return; const snapshot = json(currentDocument); try { if (await saveFile(snapshot, (mode === 'network' ? project!.name : drafts[model].title || '矩阵平差')+(mode === 'network' ? '.net.json' : '.sap.json'))) { setSaved(snapshot); notify('项目已保存。') } } catch (e) { notify((e as Error).message) } }
  const open = async (file: File) => {
    try {
      if (file.size > 8*1024*1024) throw new Error('项目文件超过 8 MB。')
      const doc = await rpc<Project | { format: 'survey-adjustment-project'; model: string; data: Draft }>('validate', { project: JSON.parse((await file.text()).replace(/^\uFEFF/, '')) })
      const apply = () => { if (doc.format === 'survey-network-project') { commit(doc, true); switchMode('network') } else { setModel(doc.model); setDrafts(d => ({ ...d, [doc.model]: doc.data })); switchMode('matrix') } setSaved(json(doc)); notify('已打开 '+file.name) }
      if (dirty) setConfirm({ title: '打开项目文件？', text: '将载入“'+file.name+'”。如需保留当前内容，请先保存项目。', action: apply }); else apply()
    } catch (e) { notify('无法打开项目：'+(e as Error).message) }
    if (fileInput.current) fileInput.current.value = ''
  }
  const deleteSelection = () => {
    if (!selection || !project) return
    const id = selection.id
    const remove = () => { if (selection.type === 'point') { const points = { ...project.points }; delete points[id]; commit({ ...project, points, observations: project.observations.filter(o => !o.points.includes(id)), constraints: project.constraints.filter(c => !Object.keys(c.terms).some(k => k.startsWith(id+'.'))) }) } else commit({ ...project, observations: project.observations.filter(o => o.id !== id) }); setSelection(null) }
    setConfirm({ title: '删除'+(selection.type === 'point' ? '控制点 ' : '观测 ')+id+'？', text: selection.type === 'point' ? '关联的观测和限制条件会一并删除，可使用撤销恢复。' : '删除后可使用撤销恢复。', action: remove })
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (theoryOpen) return
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName) || editingObs !== undefined || constraints || help || about || confirm || bulkImport) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); void save() }
      if (mode === 'network' && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo() }
      if (mode === 'network' && e.key === 'Delete') deleteSelection()
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  })
  const addPoint = (x: number, y: number) => {
    if (!project) return
    if (Object.keys(project.points).length >= 120) { notify('最多支持 120 个控制点。'); return }
    let i = 1; while (project.points['P'+i]) i++
    const id = 'P'+i
    commit({ ...project, points: { ...project.points, [id]: { X: Math.round(x*1000)/1000, Y: Math.round(y*1000)/1000, H: 100, Z: 0, fixed: [] } } }); setSelection({ type: 'point', id })
  }
  const connect = async (kind: string, ids: string[]) => {
    if (!project) return
    let i = 1; while (project.observations.some(o => o.id === 'O'+i)) i++
    const o: Observation = { id: 'O'+i, kind, points: ids, value: null, sigma: ['angle', 'azimuth'].includes(kind) ? 2 : kind === 'height' ? .001 : .003, covariance: null, components: axes(project.family), enabled: true }
    const next = { ...project, observations: [...project.observations, o] }, rev = revision.current
    try { await rpc('validate', { project: next }); if (revision.current !== rev) return; commit(next); setSelection({ type: 'observation', id: o.id }); if (!design) setEditingObs(o); else notify('已添加'+bootstrap!.kinds[kind]+' '+o.id+'。') } catch (e) { notify((e as Error).message) }
  }
  const extract = async () => {
    if (!analysis || !project) return
    const rev = revision.current
    try {
      const doc = await rpc<{ model: string; data: Draft }>('extract', { project, design, precision })
      if (rev !== revision.current) return
      setDrafts(d => ({ ...d, [doc.model]: doc.data })); setModel(doc.model); switchMode('matrix'); notify('已提取当前线性化矩阵。')
    } catch (e) { notify((e as Error).message) }
  }
  const disableAndRecalculate = async (id: string) => {
    if (!project || !solution || busy || solution.design) return
    const next = { ...project, observations: project.observations.map(o => o.id === id ? { ...o, enabled: false } : o) }
    const before = solution
    commit(next); setComparison({ before, excluded: [id] }); setTab('diagnostics'); setBusy(true)
    const rev = revision.current
    try {
      const after = await rpc<Solution>('solve', { project: next, design: false, precision })
      if (revision.current === rev) { setSolution(after); setShowPrecision(true); setComparison({ before, after, excluded: [id] }); notify('已停用 '+id+' 并复算，可查看前后比较。') }
    } catch (e) { if (revision.current === rev) setError((e as Error).message) }
    finally { setBusy(false) }
  }
  if (!bootstrap || !project) return <div className="startup"><Compass size={38} /><h2>测量平差工作台</h2>{startupError ? <><p role="alert">{startupError}</p><Button onClick={() => location.reload()}>重新加载</Button></> : <p><LoaderCircle className="spin" size={16} />正在连接本地计算服务…</p>}</div>
  const stats = analysis?.statistics
  const selectedPoint = selection?.type === 'point' ? project.points[selection.id] : null
  const selectedObs = selection?.type === 'observation' ? project.observations.find(o => o.id === selection.id) : null
  return <div className={'app-shell '+(collapsed ? 'sidebar-collapsed' : '')}>
    <aside className="sidebar"><button className="brand" onClick={() => switchMode('network')} title="测量平差工作台"><span className="brand-icon"><Compass size={24} strokeWidth={1.7} /></span><span className="brand-word"><strong>测量平差</strong><small>SURVEY WORKBENCH</small></span></button><div className="sidebar-content"><div className="nav-label">工作空间</div><button className={'nav-item '+(!theoryOpen && mode === 'network' ? 'active' : '')} onClick={() => switchMode('network')} title="控制网布设"><NetworkIcon size={18} /><span>控制网布设</span><ChevronRight size={14} className="nav-arrow" /></button><div className="nav-label matrix-label">矩阵计算</div>{Object.entries(shortNames).map(([key, name]) => <button key={key} className={'nav-item '+(!theoryOpen && mode === 'matrix' && model === key ? 'active' : '')} onClick={() => { setModel(key); switchMode('matrix') }} title={bootstrap.methods[key]}>{key.startsWith('condition') ? <Braces size={17} /> : <Sigma size={17} />}<span>{name}</span></button>)}<div className="nav-divider" /><button className={'nav-item '+(theoryOpen ? 'active' : '')} onClick={() => openTheory()} title="理论与知识"><BookOpen size={18} /><span>理论与知识</span><ChevronRight size={14} className="nav-arrow" /></button><div className="nav-label">项目工具</div><button className="nav-item" onClick={() => fileInput.current?.click()} title="打开项目"><FolderOpen size={17} /><span>打开项目</span></button><button className="nav-item" onClick={() => { switchMode('network'); requestReplace(() => void loadExample(project.family), '示例将替换当前控制网。') }} title="载入示例"><FlaskConical size={17} /><span>示例控制网</span></button><button className="nav-item" onClick={() => setHelp(true)} title="使用指南"><BookOpen size={17} /><span>使用指南</span></button></div><div className="sidebar-footer"><button className="local-status" onClick={() => setAbout(true)} title="关于此程序"><span className="local-icon"><ShieldCheck size={17} /></span><span><strong>本地工作空间</strong><small><i />离线计算 · 数据留在本机</small></span></button><div className="sidebar-version"><span>v0.6.1 · React</span><button aria-label="关于此程序" onClick={() => setAbout(true)}><CircleHelp size={15} /></button></div></div></aside>
    <main className="main"><header className="topbar"><div className="breadcrumb"><Button size="icon" variant="ghost" aria-label="切换侧栏" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</Button><span className="vertical-separator" /><span>工作空间</span><ChevronRight size={13} /><strong>{theoryOpen ? '理论与知识' : mode === 'network' ? '控制网布设' : shortNames[model]}</strong></div><div className="topbar-right"><span className="offline-pill"><i />本地运行</span><Button size="icon" variant="ghost" aria-label="打开使用指南" onClick={() => setHelp(true)}><CircleHelp size={18} /></Button></div></header>
      <div className="page-content"><div className="page-heading"><div><div className="eyebrow">{theoryOpen ? 'ADJUSTMENT KNOWLEDGE' : mode === 'network' ? 'NETWORK ADJUSTMENT' : 'MATRIX ADJUSTMENT'}</div><h1>{theoryOpen ? '理论与知识' : mode === 'network' ? '控制网工作台' : bootstrap.methods[model]}</h1><p>{theoryOpen ? '从误差基础到成果检验，把公式与实际计算联系起来。' : mode === 'network' ? '从网形布设到平差计算，让每一个观测都有据可循。' : bootstrap.formulas[model]+'  ·  最小二乘平差与精度评定'}</p></div><div className="heading-actions">{theoryOpen ? <Button onClick={() => setTheoryOpen(false)}><ArrowRight size={15} />返回计算工作台</Button> : <>{mode === 'network' && <Button onClick={() => setBulkImport(true)}><FileSpreadsheet size={15} />批量导入</Button>}<Button onClick={() => fileInput.current?.click()}><FolderOpen size={15} />打开</Button><Button onClick={() => void save()}><Save size={15} />保存项目</Button><Button variant="default" onClick={() => void calculate()} disabled={busy || (mode === 'network' && analyzing)}>{busy ? <LoaderCircle size={15} className="spin" /> : <Play size={15} fill="currentColor" strokeWidth={1.5} />}{busy ? '计算中…' : mode === 'network' && design ? '计算精度' : '计算平差'}</Button></>}</div></div>
      <div hidden={theoryOpen}>{mode === 'network' ? <><section className="project-bar panel"><div className="project-identity"><span className="project-icon"><Layers3 size={18} /></span><div><input aria-label="控制网名称" value={project.name} onChange={e => commit({ ...project, name: e.target.value })} /><small>{dirty ? <><i className="unsaved-dot" />未保存更改</> : <><Check size={11} />项目已保存</>}</small></div></div><div className="project-options"><select aria-label="控制网类型" value={project.family} onChange={e => { const family = e.target.value; requestReplace(() => void loadExample(family), '切换网型会载入对应示例。') }}>{bootstrap.families.map(f => <option key={f}>{f}</option>)}</select><div className="segmented" aria-label="计算模式"><button className={design ? 'active' : ''} onClick={() => { if (!design) { invalidate(); setDesign(true) } }}>布网设计</button><button className={!design ? 'active' : ''} onClick={() => { if (design) { invalidate(); setDesign(false); setPrecision('posterior') } }}>实测平差</button></div><span className="vertical-separator" /><Button size="sm" variant="ghost" onClick={() => requestReplace(() => void loadExample(project.family), '示例将替换当前控制网。')}><FlaskConical size={15} />示例</Button><Button size="sm" variant="ghost" onClick={() => requestReplace(() => commit({ format: 'survey-network-project', version: 1, family: project.family, name: '未命名'+project.family, method: 'indirect', points: {}, observations: [], constraints: [] }, true), '将创建空白控制网。')}><FilePlus2 size={15} />新建</Button></div></section>
      <div className="stats-row">{[['n', '总观测数', 'n', '标量观测分量'], ['t', '必要观测数', 't', '自由参数系数的秩'], ['r', '多余观测数', 'r', 'r = n − t'], ['parameters', '待估参数', 'u', '未固定的坐标分量'], ['constraints', '独立限制', 'c', '精确限制条件的秩']].map(([key, label, symbol, hint]) => <div className="stat-card" key={key} title={hint}><div><span>{label}</span><i>{symbol}</i></div><strong data-testid={'stat-'+key}>{stats ? stats[key as keyof typeof stats] : '—'}</strong><small>{key === 'constraints' ? (stats?.defect ? '基准亏损 '+stats.defect : '基准'+(stats ? '已确定' : '检查中')) : hint}</small></div>)}</div>
      {error && <div className="error-banner" role="alert"><Activity size={17} /><span>{error}</span><Button size="icon" variant="ghost" aria-label="关闭错误提示" onClick={() => setError('')}><X size={15} /></Button></div>}
      <div className="workspace-grid"><div className="workspace-main"><div className="canvas-actions"><span><NetworkIcon size={14} />{Object.keys(project.points).length} 个控制点<span className="dot-divider">·</span>{project.observations.filter(o => o.enabled).length} 条有效观测</span><div><Button size="icon" variant="ghost" aria-label="撤销" title="撤销 Ctrl+Z" disabled={!history.past.length} onClick={undo}><Undo2 size={16} /></Button><Button size="icon" variant="ghost" aria-label="重做" title="重做 Ctrl+Shift+Z" disabled={!history.future.length} onClick={redo}><Redo2 size={16} /></Button><span className="vertical-separator" /><Button size="sm" variant="ghost" onClick={() => setConstraints(true)}><SlidersHorizontal size={14} />限制条件{project.constraints.length > 0 && <span className="count">{project.constraints.length}</span>}</Button></div></div>
        <NetworkCanvas project={project} selection={selection} onSelect={setSelection} onMove={(id, p) => commit({ ...project, points: { ...project.points, [id]: p } })} onAdd={addPoint} onConnect={(kind, ids) => void connect(kind, ids)} solution={solution} fitVersion={fitVersion} showPrecision={showPrecision} onTogglePrecision={() => setShowPrecision(!showPrecision)} />
        <DataPanels project={project} analysis={analysis} solution={solution} tab={tab} setTab={setTab} kinds={bootstrap.kinds} select={selection} onSelect={setSelection} onEditObs={id => setEditingObs(project.observations.find(o => o.id === id))} onAddObs={() => setEditingObs(null)} notify={notify} onDisable={id => void disableAndRecalculate(id)} comparison={comparison} busy={busy} onTheory={openTheory} />
      </div><aside className="inspector panel"><div className="section-heading"><strong><Settings2 size={15} />{selection ? '对象属性' : '计算设置'}</strong>{selection && <Button size="icon" variant="ghost" aria-label="取消选择" onClick={() => setSelection(null)}><X size={14} /></Button>}</div><div className="inspector-body">{selectedPoint && selection ? <PointProperties key={selection.id+json(selectedPoint)} id={selection.id} point={selectedPoint} project={project} onSave={p => { commit({ ...project, points: { ...project.points, [selection.id]: p } }); notify('控制点已更新。') }} onDelete={deleteSelection} /> : selectedObs ? <><div className="property-title"><span className="point-avatar"><Activity size={20} /></span><div><strong>{selectedObs.id}</strong><small>{bootstrap.kinds[selectedObs.kind]}</small></div></div><dl className="property-list"><dt>连接点</dt><dd>{selectedObs.points.join(' → ')}</dd><dt>实测值</dt><dd className="mono">{values(selectedObs.value) || '未录入'}</dd><dt>标准差</dt><dd className="mono">{selectedObs.covariance ? '完整协方差阵' : values(selectedObs.sigma)}</dd><dt>状态</dt><dd>{selectedObs.enabled ? '参与计算' : '已停用'}</dd></dl><Button className="full-width" onClick={() => setEditingObs(selectedObs)}><Settings2 size={14} />编辑观测</Button><Button variant="ghost" className="full-width danger-text" onClick={deleteSelection}><Trash2 size={14} />删除观测</Button></> : <div className="inspector-intro"><span className="intro-icon"><Compass size={23} strokeWidth={1.5} /></span><p>选中画布中的控制点或观测，<br />在这里编辑它的属性。</p></div>}
      <div className="inspector-divider" /><Field label="平差方法"><select aria-label="平差方法" value={project.method} onChange={e => commit({ ...project, method: e.target.value })}>{Object.entries(bootstrap.methods).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field><div className="inspector-formula mono">{bootstrap.formulas[project.method]}</div><Field label="精度基准"><select aria-label="精度基准" value={design ? 'prior' : precision} disabled={design} onChange={e => { invalidate(); setPrecision(e.target.value) }}><option value="prior">先验标准差 · σ₀ = 1</option><option value="posterior">后验单位权中误差</option></select></Field><div className={'model-status '+(stats?.defect ? 'has-defect' : '')}>{analyzing ? <LoaderCircle size={15} className="spin" /> : stats?.defect ? <Activity size={15} /> : <CheckCircle2 size={15} />}<div><strong>{analyzing ? '正在更新模型' : stats?.defect ? '基准尚未确定' : stats?.n ? '模型已就绪' : '等待布网'}</strong><small>{stats?.defect ? `还需确定 ${stats.defect} 个自由度` : design ? '由网形与标准差预估精度' : '由录入的实测值进行平差'}</small></div></div><Button className="full-width" size="sm" disabled={!analysis || !stats?.n} onClick={extract}><Calculator size={14} />提取至矩阵工作台<ArrowRight size={13} /></Button>{solution && <div className="solution-summary"><strong><CheckCircle2 size={14} />{solution.design ? '设计精度已计算' : '平差已完成'}</strong><span>迭代次数 <b>{solution.iterations}</b></span><span>后验 σ̂₀ <b className="mono">{number(solution.result.posterior_sigma)}</b></span><span>vᵀPv <b className="mono">{solution.design ? '设计模式' : number(solution.result.weighted_sum)}</b></span><Button size="sm" variant="ghost" onClick={() => setTab('report')}><ArrowDownToLine size={14} />查看报告与导出</Button></div>}</div><div className="inspector-tip"><CircleHelp size={14} /><span>拖动点可调整近似坐标。标准差与协方差在观测属性中设置。</span></div></aside></div>
      </> : <MatrixWorkspace bootstrap={bootstrap} model={model} draft={drafts[model]} setDraft={d => setDrafts(prev => ({ ...prev, [model]: d }))} calculateTick={calculateTick} notify={notify} onTheory={openTheory} key={model} />}</div>{theoryOpen && <TheoryWorkspace active={theoryTopic} onNavigate={setTheoryTopic} project={project} solution={solution} selection={selection} onReturn={() => setTheoryOpen(false)} />}
      <footer className="page-footer"><span><ShieldCheck size={12} />计算与项目文件均在本机处理</span><span>长度 m<span className="dot-divider">·</span>角度 °<span className="dot-divider">·</span>测角标准差 ″</span></footer></div>
    </main><input ref={fileInput} type="file" accept=".json" hidden aria-label="导入项目文件" onChange={e => { const file = e.target.files?.[0]; if (file) void open(file) }} />
    {toast && <div className="toast" role="status"><CheckCircle2 size={17} /><span>{toast}</span><button aria-label="关闭消息" onClick={() => setToast('')}><X size={14} /></button></div>}
    {bulkImport && <ImportWizard project={project} notify={notify} onClose={() => setBulkImport(false)} onImport={(p, measured) => { commit(p); switchMode('network'); setDesign(!measured); setPrecision(measured ? 'posterior' : 'prior'); setSelection(null); setFitVersion(v => v+1); setTab('observations'); setBulkImport(false); notify('批量数据已导入，可撤销恢复导入前状态。') }} />}
    {editingObs !== undefined && <ObservationEditor key={editingObs?.id || 'new'} project={project} observation={editingObs} names={bootstrap.kinds} onClose={() => setEditingObs(undefined)} onSave={o => { const old = editingObs; commit({ ...project, observations: old ? project.observations.map(item => item.id === old.id ? o : item) : [...project.observations, o] }); setSelection({ type: 'observation', id: o.id }); setEditingObs(undefined); notify('观测已保存。') }} />}
    {constraints && <ConstraintEditor project={project} onClose={() => setConstraints(false)} onSave={p => { commit(p); setConstraints(false); notify('限制条件已更新。') }} />}
    <Modal open={Boolean(confirm)} title={confirm?.title || '确认操作'} description={confirm?.text} onClose={() => setConfirm(null)}><div className="modal-footer"><Button onClick={() => setConfirm(null)}>取消</Button><Button variant="default" onClick={() => { const action = confirm?.action; setConfirm(null); action?.() }}>继续</Button></div></Modal>
    <Modal open={help} title="使用指南" description="布网、录入观测、计算和导出，都可以在这个本地工作空间中完成。" onClose={() => setHelp(false)} wide><div className="help-content"><ol><li><strong>选择网型与计算模式</strong><p>布网设计根据近似坐标和观测标准差预估精度，不产生实测残差。实测平差须录入所有启用观测的实测值；可在实测模式中载入对应示例。</p></li><li><strong>布点与添加观测</strong><p>画布左侧 ＋ 添加控制点，连线工具按顺序选择端点。水平角按“后视点 → 测站 → 前视点”。右侧设置坐标、固定分量和标准差；表格编辑按钮可录入观测值。</p></li><li><strong>检查基准和实时统计</strong><p>n 按标量分量计数；t 为考虑精确限制后观测系数的秩；r = n − t。未知参数 u 不含固定分量，独立限制数 c 按秩计。基准亏损 u − c − t 应为 0。</p></li><li><strong>计算并查看精度</strong><p>四种方法共享观测、权和精确限制。计算后查看点位中误差、相对精度、误差椭圆、法方程和协因数。椭圆为 1σ 半轴，画布放大显示；GNSS 椭圆仅为 XY 投影。</p></li><li><strong>保存与导出</strong><p>项目保存为 .net.json 或 .sap.json，可兼容旧版项目。报告页导出 TXT、CSV 和完整 JSON。Ctrl+S 保存；Ctrl+Z 撤销；Ctrl+Shift+Z 重做；Delete 删除选中对象。</p></li></ol><div className="help-note"><strong>坐标与单位</strong><p>平面 X 北、Y 东。GNSS 使用同一 XYZ 直角坐标框架中的 ΔX、ΔY、ΔZ，支持标准差或 3×3 协方差阵；不自动做 ENU、投影或地心坐标转换。各观测块之间按不相关处理。角度输入为度，标准差为角秒，角度方程内部为弧度。</p></div></div></Modal>
    <Modal open={about} title="关于测量平差工作台" description="v0.6.1 · 本地桌面版" onClose={() => setAbout(false)}><div className="about-content"><div className="about-brand"><Compass size={40} /><div><strong>测量平差</strong><span>Survey Adjustment Workbench</span></div></div><p>React + TypeScript 界面，Radix 交互组件与 Lucide 图标；由本机 Python / NumPy 内核完成平差与精度计算。</p><p>界面布局与按钮组件参考 shadcn-admin / shadcn/ui，按 MIT 协议保留许可说明。完整来源见程序目录 THIRD_PARTY_NOTICES.md。</p><p className="muted">计算不依赖云端，不加载在线字体或外部服务。</p></div></Modal>
  </div>
}
