import {useMemo,useState} from 'react'
import type {Scene,Snapshot} from './model'
import {analyze,format} from './math'
import Scene3D from './Scene3D'
import type {CameraPose} from './Scene3D'
import Ellipse from './Ellipse'
import SkyPlot from './SkyPlot'
export default function Comparison({scene,snapshots,restore,remove,extent}:{scene:Scene;snapshots:Snapshot[];restore:(s:Scene)=>void;remove:(id:string)=>void;extent?:number}){
  const [reference,setReference]=useState(''),[pose,setPose]=useState<CameraPose>({position:[15,11,16],target:[0,2,0]})
  const ref=snapshots.find(s=>s.id===reference)||snapshots[0]
  const b=useMemo(()=>ref?{...ref.scene,confidence:scene.confidence}:scene,[ref,scene.confidence])
  const aResult=useMemo(()=>analyze(scene),[scene]),bResult=useMemo(()=>analyze(b),[b])
  const shared=extent??Math.max(aResult.ellipsoid?.axes[0]??0,bResult.ellipsoid?.axes[0]??0,.01)
  if(!ref)return <div className="empty-state"><strong>留下一个几何，比较另一个。</strong><p>点击上方“保存对照”，最多保留四组完整场景。</p></div>
  return <div className="comparison-panel"><div className="experiment-toolbar"><strong>A / B 同屏对照</strong><label>B 参考 <select aria-label="对照参考场景" value={ref.id} onChange={e=>setReference(e.target.value)}>{snapshots.map((s,i)=><option key={s.id} value={s.id}>{i+1} · {s.scene.name}</option>)}</select></label></div><p className="micro">相机联动 · 统一误差半轴范围 {format(shared)} m · 两侧均使用{scene.confidence==='95'?'95% 区域':'标准区域'}。σρ 保留各自数值。</p>
    <div className="ab-grid" data-testid="ab-comparison">{[[scene,aResult,'A · 当前场景'],[b,bResult,'B · 参考场景']].map(([s,r,title],i)=><section key={i}><Scene3D scene={s as Scene} result={r as ReturnType<typeof analyze>} selected="" onSelect={()=>{}} onMove={()=>{}} extent={shared} compact title={String(title)} pose={pose} onPose={setPose}/><Ellipse scene={s as Scene} result={r as ReturnType<typeof analyze>} extent={shared}/></section>)}</div>
    <div className="difference-strip">{(['PDOP','HDOP','VDOP'] as const).map(key=>{const a=aResult.dop?.[key],v=bResult.dop?.[key];return <span key={key}>{key} A − B <b>{a!==undefined&&v!==undefined?((a-v)>0?'+':'')+format(a-v):'—'}</b></span>})}<span>水平长半轴 A − B <b>{aResult.ellipse&&bResult.ellipse?format(aResult.ellipse.major-bResult.ellipse.major)+' m':'—'}</b></span></div>
    <div className="comparison-grid">{snapshots.map((s,i)=>{const r=analyze(s.scene);return <article className="comparison-card" key={s.id}><div><strong>{String(i+1).padStart(2,'0')} · {s.scene.name}</strong><button className="icon-button" aria-label={'移除对照 '+(i+1)} onClick={()=>remove(s.id)}>×</button></div><SkyPlot scene={s.scene} small/><dl><dt>PDOP</dt><dd>{format(r.dop?.PDOP)}</dd><dt>参与 / 总数</dt><dd>{r.used.length} / {s.scene.satellites.length}</dd><dt>σρ</dt><dd>{format(s.scene.sigma)} m</dd><dt>长半轴</dt><dd>{format(r.ellipse?.major)} m</dd></dl><button className="button small" onClick={()=>restore(s.scene)}>恢复场景 ↗</button></article>})}</div>
  </div>
}
