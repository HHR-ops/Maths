import { useEffect, useMemo, useRef, useState } from 'react'
import { Orbit, FolderOpen, Download, Save, Plus, X, ChevronDown, Crosshair, Focus, Building2, CircleHelp, Trash2, Camera, Table2, BookmarkPlus, ArrowUpRight, ShieldCheck, Radio, Check, TriangleAlert, SlidersHorizontal, Copy, Layers3 } from 'lucide-react'
import type { Project, Scene, Satellite } from './model'
import { initialProject, preset, presets, status, statusNames, colors, validateProject, copy } from './model'
import { analyze, format, csv } from './math'
import type { Result } from './math'
import SkyPlot from './SkyPlot'
import Scene3D from './Scene3D'
import Ellipse from './Ellipse'
import Comparison from './Comparison'
import {MotionPanel,NoisePanel,EphemerisPanel} from './ExperimentPanels'
import {useProjectHistory} from './history'
import type {Cloud} from './experiments'
import {Undo2,Redo2} from 'lucide-react'
declare global {
  interface Window {
    __GNSS_TOKEN__?: string
    __GNSS_PROJECT__?: unknown
    __gnssLab?: { project:Project; result:Result }
    pywebview?: { api: { save_file:(content:string,filename:string,encoding:string)=>Promise<{ok:boolean;cancelled?:boolean;error?:string}> } }
  }
}
const STORAGE='gnss-geometry-lab-v1'
function load():Project {
  try { const saved=window.__GNSS_PROJECT__ || JSON.parse(localStorage.getItem(STORAGE)||'null');if(saved)return validateProject(saved) }catch{/* Invalid drafts never prevent startup. */}
  return initialProject()
}
async function saveFile(content:string,name:string,encoding='utf-8') {
  if(window.pywebview?.api){
    const r=await window.pywebview.api.save_file(content,name,encoding)
    if(!r.ok)throw Error(r.error||'保存失败。')
    return !r.cancelled
  }
  const data=encoding==='base64'?Uint8Array.from(atob(content),c=>c.charCodeAt(0)):name.endsWith('.csv')?'\uFEFF'+content:content
  const url=URL.createObjectURL(new Blob([data],{type:name.endsWith('.png')?'image/png':'text/plain;charset=utf-8'}))
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return true
}
function Modal({ title,children,onClose }: { title:string;children:React.ReactNode;onClose:()=>void }) {
  const ref=useRef<HTMLDialogElement>(null)
  useEffect(()=>{const d=ref.current!;d.showModal();return()=>d.close()},[])
  return <dialog ref={ref} className="modal" onCancel={e=>{e.preventDefault();onClose()}} onClick={e=>{if(e.target===e.currentTarget)onClose()}} aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" aria-label="关闭对话框" onClick={onClose}><X size={18}/></button></div>{children}</dialog>
}
export default function App(){
  const history=useProjectHistory(load),{setProject}=history
  const [preview,setPreview]=useState<Scene|null>(null),[trails,setTrails]=useState<Scene[]>([]),[scaleMode,setScaleMode]=useState('auto'),[fixedExtent,setFixedExtent]=useState(10),[experiment,setExperiment]=useState<{key:string;cloud:Cloud}|null>(null)
  const project=useMemo(()=>preview?{...history.project,scene:preview}:history.project,[history.project,preview])
  const [selected,setSelected]=useState('S01'),[tab,setTab]=useState('insights'),[help,setHelp]=useState(false),[toast,setToast]=useState(''),[presetId,setPresetId]=useState('balanced')
  const file=useRef<HTMLInputElement>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),saveSequence=useRef(Date.now())
  const scene=project.scene,result=useMemo(()=>analyze(scene),[scene]),sat=scene.satellites.find(s=>s.id===selected)
  const notify=(text:string)=>{setToast(text);if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>setToast(''),4200)}
  const edit=(change:Partial<Scene>)=>{setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setPresetId('');setProject(p=>({...p,scene:{...scene,...change}}))}
  const move=(id:string,az:number,el:number)=>{setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setPresetId('');setProject(p=>({...p,scene:{...scene,satellites:scene.satellites.map(s=>s.id===id?{...s,azimuth:az,elevation:el}:s)}}))}
  const extent=scaleMode==='fixed'?fixedExtent:undefined
  const cloud=experiment?.key===JSON.stringify(scene)?experiment.cloud:null
  const undo=()=>{setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setPresetId('');history.undo()}
  const redo=()=>{setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setPresetId('');history.redo()}
  const adopt=()=>{if(preview){setProject(p=>({...p,scene:copy(preview)}));setPreview(null);setTab('insights');notify('已将当前帧作为可编辑场景。')}}
  useEffect(()=>{if(!scene.satellites.some(s=>s.id===selected))setSelected(scene.satellites[0]?.id||'')},[scene.satellites,selected])
  useEffect(()=>{const end=()=>history.end();window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end);return()=>{window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end)}})
  useEffect(()=>{
    window.__gnssLab={project,result}
    const sequence=++saveSequence.current
    const timeout=setTimeout(()=>{
      try{localStorage.setItem(STORAGE,JSON.stringify(project))}catch{/* Explicit project save remains available. */}
      if(window.__GNSS_TOKEN__)void fetch('/api/workspace',{method:'POST',headers:{'Content-Type':'application/json','X-GNSS-Token':window.__GNSS_TOKEN__},body:JSON.stringify({project,sequence})}).then(r=>{if(!r.ok)throw Error('workspace')}).catch(()=>notify('草稿保存未完成，请使用“保存项目”。'))
    },350)
    return()=>clearTimeout(timeout)
  },[project,result])
  const save=async()=>{try{if(await saveFile(JSON.stringify(project,null,2),'GNSS-'+scene.name+'.gnss.json'))notify('项目已保存，可继续编辑或带到另一台电脑。')}catch(e){notify((e as Error).message)}}
  useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.ctrlKey||e.metaKey){if(e.key.toLowerCase()==='s'){e.preventDefault();void save()}else if(e.key.toLowerCase()==='z'&&!(e.target instanceof HTMLInputElement)&&!(e.target instanceof HTMLTextAreaElement)){e.preventDefault();if(e.shiftKey)redo();else undo()}}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)})
  const open=async(input:File)=>{
    try{if(input.size>1024*1024)throw Error('项目文件超过 1 MB。');const next=validateProject(JSON.parse((await input.text()).replace(/^\uFEFF/,'')));setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setProject(next);setSelected(next.scene.satellites[0]?.id||'');setPresetId('');notify('已打开 '+input.name)}
    catch(e){notify('无法打开项目：'+(e as Error).message)}
    if(file.current)file.current.value=''
  }
  const choosePreset=(id:string)=>{const next=preset(id);setPreview(null);if(tab==='motion'||tab==='ephemeris')setTab('insights');setProject(p=>({...p,scene:next}));setPresetId(id);setSelected(next.satellites[0]?.id||'');notify('已载入“'+next.name+'”。')}
  const add=()=>{
    if(scene.satellites.length>=64){notify('最多支持 64 颗卫星。');return}
    let i=1;while(scene.satellites.some(s=>s.id==='S'+String(i).padStart(2,'0')))i++
    const id='S'+String(i).padStart(2,'0'),next:Satellite={id,azimuth:(i*137.508)%360,elevation:35,enabled:true}
    edit({satellites:[...scene.satellites,next]});setSelected(id)
  }
  const capture=()=>{if(project.snapshots.length>=4){notify('最多保留四个对照场景，请先移除一个。');setTab('compare');return}setProject(p=>({...p,snapshots:[...p.snapshots,{id:crypto.randomUUID(),scene:copy(scene)}]}));setTab('compare');notify('已保存当前几何与参数，可在对照中恢复。')}
  const exportCsv=async()=>{try{if(await saveFile(csv(scene,result),'GNSS-'+scene.name+'.csv'))notify('卫星与计算指标已导出。')}catch(e){notify((e as Error).message)}}
  const exportPng=async()=>{
    try{
      const source=document.querySelector<HTMLCanvasElement>('.three-host>canvas')
      if(!source)throw Error('三维视图尚未就绪。')
      const canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height+120
      const context=canvas.getContext('2d')!;context.fillStyle='#0d0d10';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(source,0,0)
      const bounds=source.getBoundingClientRect(),scale=source.width/bounds.width
      context.font=(12*scale)+'px Segoe UI';context.textAlign='center'
      for(const label of source.parentElement!.querySelectorAll<HTMLElement>('.three-labels button,.three-cardinal')){
        if(label.style.visibility==='hidden'||label.hidden)continue
        const at=label.getBoundingClientRect();context.fillStyle=getComputedStyle(label).color;context.fillText(label.textContent||'',(at.left+at.width/2-bounds.left)*scale,(at.top+at.height/2-bounds.top)*scale)
      }
      context.textAlign='left';context.fillStyle='#eff6f9';context.font='20px Segoe UI';context.fillText('GNSS Geometry Lab · '+scene.name,24,source.height+33)
      context.font='15px Segoe UI';context.fillStyle='#b8b5ad';context.fillText('PDOP '+format(result.dop?.PDOP)+'   HDOP '+format(result.dop?.HDOP)+'   VDOP '+format(result.dop?.VDOP)+'   σρ '+format(scene.sigma)+' m',24,source.height+64);context.fillText('ENU directions · Equal uncorrelated range precision · Error scale: '+(extent?'fixed '+extent+' m':'auto')+'',24,source.height+93)
      if(await saveFile(canvas.toDataURL('image/png').split(',')[1],'GNSS-'+scene.name+'.png','base64'))notify('三维场景图已导出。')
    }catch(e){notify((e as Error).message)}
  }
  const metrics=['GDOP','PDOP','HDOP','VDOP','TDOP'] as const
  const metricNames={GDOP:'位置与钟差',PDOP:'空间位置',HDOP:'水平位置',VDOP:'高程分量',TDOP:'钟差分量'}
  return <div className="app-shell">
    <header className="app-header"><div className="brand"><div className="brand-symbol"><Orbit size={26}/></div><div><strong>GNSS<span>交互实验室</span></strong><small>GEOMETRY LAB</small></div></div><div className="header-center"><span className="status-dot"/>本地交互实验<span className="header-slash">/</span><span>v0.2</span></div><div className="header-actions"><button className="icon-button" aria-label="撤销" title="撤销 Ctrl+Z" disabled={!history.canUndo&&!preview} onClick={undo}><Undo2 size={16}/></button><button className="icon-button" aria-label="重做" title="重做 Ctrl+Shift+Z" disabled={!history.canRedo} onClick={redo}><Redo2 size={16}/></button><button className="button quiet" onClick={()=>file.current?.click()}><FolderOpen size={16}/><span>打开</span></button><button className="button quiet" onClick={()=>void save()}><Save size={16}/><span>保存项目</span></button><details className="export-menu"><summary className="button"><Download size={16}/>导出<ChevronDown size={13}/></summary><div><button onClick={()=>void exportPng()}><Camera size={15}/>三维场景 PNG</button><button onClick={()=>void exportCsv()}><Table2 size={15}/>卫星与指标 CSV</button></div></details><button className="icon-button" aria-label="实验室使用说明" title="使用说明" onClick={()=>setHelp(true)}><CircleHelp size={19}/></button></div></header>
    <input ref={file} type="file" accept=".json,.gnss.json" hidden aria-label="打开 GNSS 项目" onChange={e=>{if(e.target.files?.[0])void open(e.target.files[0])}}/>
    <div className="lab-grid">
      <aside className="left-panel">
        <div className="section-label">实验场景 <span>01 — 05</span></div>
        <div className="preset-list">{presets.map(p=>{const Icon=p.id==='balanced'?Orbit:p.id==='clustered'?Focus:p.id==='obstructed'?Building2:p.id==='four'?Crosshair:TriangleAlert;return <button key={p.id} className={'preset-card '+(presetId===p.id?'chosen':'')} aria-pressed={presetId===p.id} onClick={()=>choosePreset(p.id)}><Icon size={19}/><span><strong>{p.name}</strong><small>{p.caption}</small></span><span className="preset-indicator"/></button>})}</div>
        <div className="section-label satellite-heading">卫星 <span>{scene.satellites.length} 颗</span><button className="icon-button" aria-label="添加卫星" title="添加卫星" onClick={add}><Plus size={17}/></button></div>
        <div className="satellite-list">{scene.satellites.map(s=><div key={s.id} className={'satellite-row '+(selected===s.id?'chosen':'')}><input type="checkbox" aria-label={'启用卫星 '+s.id} checked={s.enabled} onChange={e=>edit({satellites:scene.satellites.map(p=>p.id===s.id?{...p,enabled:e.target.checked}:p)})}/><button onClick={()=>setSelected(s.id)} aria-label={'选择卫星 '+s.id}><i style={{background:colors[status(s,scene)]}}/><b>{s.id}</b><small>{s.elevation.toFixed(0)}°</small></button></div>)}</div>
        {sat&&<section className="sat-editor"><div className="sat-editor-heading"><strong>{sat.id}<small style={{color:colors[status(sat,scene)]}}>{statusNames[status(sat,scene)]}</small></strong><button className="icon-button danger" aria-label={'删除卫星 '+sat.id} title="删除卫星" onClick={()=>{edit({satellites:scene.satellites.filter(s=>s.id!==sat.id)});setSelected(scene.satellites.find(s=>s.id!==sat.id)?.id||'')}}><Trash2 size={14}/></button></div><label>方位角 <span><input type="number" aria-label="卫星方位角" min="0" max="360" step=".1" value={Number(sat.azimuth.toFixed(1))} onChange={e=>{const v=Number(e.target.value);if(Number.isFinite(v))move(sat.id,Math.max(0,Math.min(360,v)),sat.elevation)}}/>°</span></label><input onPointerDown={history.begin} onPointerUp={history.end} onBlur={history.end} type="range" aria-label="拖动方位角" min="0" max="360" step=".1" value={sat.azimuth} onChange={e=>move(sat.id,+e.target.value,sat.elevation)}/><label>高度角 <span><input type="number" aria-label="卫星高度角" min="0" max="90" step=".1" value={Number(sat.elevation.toFixed(1))} onChange={e=>{const v=Number(e.target.value);if(Number.isFinite(v))move(sat.id,sat.azimuth,Math.max(0,Math.min(90,v)))}}/>°</span></label><input onPointerDown={history.begin} onPointerUp={history.end} onBlur={history.end} type="range" aria-label="拖动高度角" min="0" max="90" step=".1" value={sat.elevation} onChange={e=>move(sat.id,sat.azimuth,+e.target.value)}/></section>}
        <div className="sidebar-note"><ShieldCheck size={15}/><span>计算与草稿留在本机<br/><small>方向可模拟，几何可复核</small></span></div>
      </aside>
      <main className="main-panel">
        <div className="page-heading"><div><span className="eyebrow">EXPLORE THE GEOMETRY</span><h1>让卫星几何，看得见。</h1><p>改变一个方向，观察整个定位空间的变化。</p></div><button className="button capture" onClick={capture}><BookmarkPlus size={16}/><span>保存对照</span></button></div>
        <div className="metric-row">{metrics.map((key,i)=><div className={'metric-card '+(key==='PDOP'?'primary-metric':'')} key={key}><div><span>{key}</span>{i===1&&<span className="metric-mark">3D</span>}</div><strong data-testid={'metric-'+key}>{format(result.dop?.[key])}</strong><small>{metricNames[key]}</small></div>)}</div>
        <div className={'geometry-status '+(!result.valid?'invalid':result.reason?'warning':'')} role="status" data-testid="geometry-status">{!result.valid?<TriangleAlert size={15}/>:<Radio size={15}/>}<span><b>{result.used.length} / {scene.satellites.length}</b> 颗卫星参与<span className="status-sep">·</span>矩阵秩 <b>{result.rank} / 4</b></span><span className="geometry-detail">{result.reason||'几何可解算 · 等精度测距模型'}</span></div>
        <Scene3D scene={scene} result={result} selected={selected} onSelect={setSelected} onMove={move} onDragStart={history.begin} onDragEnd={history.end} extent={extent} cloud={cloud?.points} trails={trails}/>
        <div className="settings-bar"><SlidersHorizontal size={16}/><label>截止高度角 <input onPointerDown={history.begin} onPointerUp={history.end} onBlur={history.end} aria-label="截止高度角" type="range" min="0" max="85" step="1" value={scene.mask} onChange={e=>edit({mask:+e.target.value})}/><b>{scene.mask.toFixed(0)}°</b></label><label>测距 σρ <input aria-label="测距标准差" type="number" min=".01" max="100" step=".1" value={scene.sigma} onChange={e=>{const v=+e.target.value;if(v>=.01&&v<=100)edit({sigma:v})}}/><span>m</span></label><label className="confidence-control"><select aria-label="误差区域类型" value={scene.confidence} onChange={e=>edit({confidence:e.target.value as Scene['confidence']})}><option value="standard">标准椭圆 / 椭球</option><option value="95">95% 置信区域</option></select></label></div>
        <div className="scale-bar"><label>误差图比例 <select aria-label="误差图比例" value={scaleMode} onChange={e=>setScaleMode(e.target.value)}><option value="auto">自适应</option><option value="fixed">统一固定比例</option></select></label>{scaleMode==='fixed'&&<label>半轴范围 <input aria-label="固定误差半轴范围" type="number" min=".01" max="100000" step="1" value={fixedExtent} onChange={e=>{const v=+e.target.value;if(v>=.01&&v<=100000)setFixedExtent(v)}}/> m</label>}<span>{scaleMode==='fixed'?'二维 / 三维 / 对照使用同一米制范围':'读数保留物理单位；A/B 对照始终使用统一比例'}</span></div>
        {preview&&<div className="preview-banner"><span>当前显示实验帧，保存项目与保存对照会保留此帧。</span><button className="button small" onClick={adopt}>采用当前帧</button><button className="button small quiet" onClick={()=>{setPreview(null);setTab('insights')}}>返回编辑场景</button></div>}
        <section className="analysis-panel"><div className="analysis-tabs" role="tablist">{[['insights','实验观察'],['matrix','几何矩阵'],['compare','场景对照'],['motion','动态轨迹'],['noise','噪声实验'],['ephemeris','SP3 历元'],['theory','原理与约定']].map(([id,label])=><button key={id} role="tab" aria-selected={tab===id} onClick={()=>setTab(id)}>{label}{id==='compare'&&project.snapshots.length>0&&<span>{project.snapshots.length}</span>}</button>)}</div>
          {tab==='insights'&&<div className="insight-grid"><div><span className="section-label">当前实验</span><h3>{scene.name}</h3><p>{result.valid?'拖动卫星时，观察椭球的方向与扁长程度。几何分布决定 DOP，测距标准差决定预测误差的尺度。':result.reason}</p><div className="insight-pills"><span>可估参数 4</span><span>条件数 {format(result.condition,1)}</span><span>单一钟差</span></div></div><div className="obstruction-controls"><label className="toggle-label"><input aria-label="启用遮挡扇区" type="checkbox" checked={scene.obstruction.enabled} onChange={e=>edit({obstruction:{...scene.obstruction,enabled:e.target.checked}})}/><Building2 size={16}/><strong>遮挡扇区</strong></label><div className="obstruction-fields">{[['start','起始方位',360],['width','扇区宽度',360],['height','遮挡高度',90]].map(([key,label,max])=><label key={key}>{label}<span><input aria-label={String(label)} type="number" min="0" max={max} disabled={!scene.obstruction.enabled} value={scene.obstruction[key as 'start'|'width'|'height']} onChange={e=>{const v=+e.target.value;if(v>=0&&v<=Number(max))edit({obstruction:{...scene.obstruction,[key]:v}})}}/>°</span></label>)}</div><p className="micro">扇区内低于遮挡高度的卫星不参与计算。</p></div></div>}
          {tab==='matrix'&&<div className="matrix-panel"><div className="matrix-intro"><p>G = [−cos(el)sin(az), −cos(el)cos(az), −sin(el), 1]</p><button className="button small quiet" onClick={()=>{void navigator.clipboard.writeText(result.G.map(row=>row.map(v=>v.toPrecision(10)).join('\t')).join('\n')).then(()=>notify('几何矩阵已复制。')).catch(()=>notify('复制未完成，可使用 CSV 导出。'))}}><Copy size={13}/>复制 G</button></div><div className="matrix-grid"><div className="table-scroll"><table><thead><tr><th>卫星</th><th>E</th><th>N</th><th>U</th><th>c·δt</th></tr></thead><tbody>{result.G.map((row,i)=><tr key={result.used[i]}><th>{result.used[i]}</th>{row.map((v,j)=><td key={j}>{v.toFixed(5)}</td>)}</tr>)}</tbody></table></div><div><h4>协因数 Q = (GᵀG)⁻¹</h4>{result.Q?<div className="table-scroll"><table><thead><tr><th></th>{['E','N','U','c·δt'].map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{result.Q.map((row,i)=><tr key={i}><th>{['E','N','U','c·δt'][i]}</th>{row.map((v,j)=><td key={j}>{format(v,5)}</td>)}</tr>)}</tbody></table></div>:<p className="micro">秩不足，协因数阵不作可逆解算。</p>}<p className="micro">采用 SVD 计算；位置协方差为 σρ² × Q 的 ENU 子阵。</p><p className="micro">奇异值：{result.singular.map(v=>v.toExponential(3)).join(' · ')}</p></div></div></div>}
          {tab==='compare'&&<Comparison scene={scene} snapshots={project.snapshots} extent={extent} remove={id=>setProject(p=>({...p,snapshots:p.snapshots.filter(s=>s.id!==id)}))} restore={next=>{setPreview(null);setProject(p=>({...p,scene:copy(next)}));setSelected(next.satellites[0]?.id||'');setPresetId('');notify('已恢复对照场景。')}}/>}
          {tab==='motion'&&<MotionPanel scene={history.project.scene} onFrame={setPreview} onTrails={setTrails}/>}
          {tab==='noise'&&<NoisePanel scene={scene} cloud={cloud} onCloud={c=>setExperiment({key:JSON.stringify(scene),cloud:c})}/>}
          <div hidden={tab!=='ephemeris'}><EphemerisPanel active={tab==='ephemeris'} scene={history.project.scene} onFrame={setPreview} saveText={(text,name)=>{void saveFile(text,name).catch(e=>notify((e as Error).message))}}/></div>
          {tab==='theory'&&<div className="theory-content"><article><h3>从方向到不确定度</h3><p>方位角从北向东顺时针计，高度角从水平面向天顶计。局部坐标采用 E 东、N 北、U 上；钟差以距离 c·δt 表示。</p><p className="formula">Q = (GᵀG)⁻¹　　Cov(ENU) = σρ² · Q₍ENU₎</p><p>HDOP² = qEE + qNN；VDOP² = qUU；PDOP² = HDOP² + VDOP²；TDOP² = qtt；GDOP² = PDOP² + TDOP²。</p></article><article><h3>怎样解读实验</h3><p>采用等精度、不相关测距和单一接收机钟差模型。DOP 是无量纲几何指标；误差区域是给定 σρ 后的精度预测。</p><p>至少四颗卫星是数量条件，G 的秩达到 4 才能解算。同仰角时，高程与钟差列相关，即使卫星很多仍可能退化。</p><p>二维标准椭圆的高斯覆盖率约 39.35%，三维标准椭球约 19.87%；95% 区域分别使用 χ²₂ 和 χ²₃ 倍率。椭圆长轴为正北起顺时针方位角，范围 0–180°；圆形时方向不唯一。</p><a href="https://gssc.esa.int/navipedia/index.php?title=Positioning_Error" target="_blank" rel="noreferrer">计算依据：ESA Navipedia · Positioning Error <ArrowUpRight size={13}/></a></article></div>}
        </section>
      </main>
      <aside className="right-panel"><section className="side-card"><div className="card-heading"><h2>天空图</h2><span>北起 · 顺时针</span></div><SkyPlot scene={scene} selected={selected} onSelect={setSelected} onMove={move} onDragStart={history.begin} onDragEnd={history.end}/><div className="sky-legend"><span><i style={{background:colors.used}}/>参与</span><span><i style={{background:colors.masked}}/>低于截止角</span><span><i style={{background:colors.blocked}}/>遮挡</span></div><p className="micro sky-hint">拖动卫星，或选中后用方向键微调。</p></section><section className="side-card ellipse-card"><div className="card-heading"><h2>水平误差区域</h2><span>{scene.confidence==='95'?'95%':'标准'}</span></div><Ellipse result={result} scene={scene} extent={extent} points={cloud?.points}/></section><div className="model-note"><Crosshair size={17}/><p>这里展示几何与精度预测。<br/><span>模拟方向与遮挡均可自由调整。</span></p></div></aside>
    </div>
    <footer className="app-footer"><span><span className="status-dot"/>GNSS GEOMETRY LAB</span><span>方向几何 · 等精度测距 · ENU 局部坐标</span><span>v0.2.0 · MIT</span></footer>
    {toast&&<div className="toast" role="status"><Check size={16}/>{toast}<button className="icon-button" aria-label="关闭通知" onClick={()=>setToast('')}><X size={13}/></button></div>}
    {help&&<Modal title="开始你的第一个几何实验" onClose={()=>setHelp(false)}><div className="help-content"><div className="help-step"><b>01</b><div><h3>拖动一个卫星</h3><p>在三维半球或天空图中拖动卫星；左侧可输入精确的方位角与高度角。三维空白处拖动可旋转，滚轮缩放。</p></div></div><div className="help-step"><b>02</b><div><h3>观察几何与误差</h3><p>DOP 随参与卫星的方向分布变化。调整测距标准差，误差半轴随之变化，而 DOP 保持不变。可切换统一固定比例；A/B 对照始终使用同一物理比例与相机视角。</p></div></div><div className="help-step"><b>03</b><div><h3>比较两个场景</h3><p>保存一组对照，再试试“集中一侧”或“同仰角退化”。截止高度角与遮挡扇区会决定哪些卫星参与计算。</p></div></div><div className="help-step"><b>04</b><div><h3>保存与分享</h3><p>保存 .gnss.json 项目可保留参数与对照；CSV 导出卫星和指标，PNG 导出三维场景。程序独立运行，资源保存在本机。动态轨迹是模拟实验；导入 SP3 后按文件历元显示，保存项目仅保留当前帧，完整文件需重新导入。</p></div></div><button className="button primary" onClick={()=>setHelp(false)}>开始实验<ArrowUpRight size={16}/></button></div></Modal>}
  </div>
}