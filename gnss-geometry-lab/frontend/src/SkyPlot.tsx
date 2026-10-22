import { useRef } from 'react'
import type { Scene, Satellite } from './model'
import { colors, status, statusNames } from './model'
import {layoutLabels} from './labels'
export function skyXY(s: Satellite, radius = 132) {
  const r = radius*(90-s.elevation)/90, a = s.azimuth*Math.PI/180
  return { x: 160+r*Math.sin(a), y: 160-r*Math.cos(a) }
}
export default function SkyPlot({ scene, selected, onSelect, onMove, onDragStart, onDragEnd, small = false }: { scene: Scene; selected?: string; onSelect?: (id:string)=>void; onMove?: (id:string,az:number,el:number)=>void; onDragStart?:()=>void;onDragEnd?:()=>void;small?: boolean }) {
  const svg = useRef<SVGSVGElement>(null), drag = useRef<string|null>(null)
  const move = (e: React.PointerEvent) => {
    if (!drag.current || !onMove) return
    const bounds=svg.current!.getBoundingClientRect(), scale=Math.min(bounds.width,bounds.height)/320
    const x=(e.clientX-bounds.left-(bounds.width-320*scale)/2)/scale-160
    const y=(e.clientY-bounds.top-(bounds.height-320*scale)/2)/scale-160
    const r=Math.min(132,Math.hypot(x,y)), az=(Math.atan2(x,-y)*180/Math.PI+360)%360
    onMove(drag.current,az,90-r/132*90)
  }
  const outer=132, maskR=outer*(90-scene.mask)/90, ob=scene.obstruction
  const wedge=Array.from({length:37},(_,i)=>{const a=(ob.start+ob.width*i/36)*Math.PI/180;return [160+outer*Math.sin(a),160-outer*Math.cos(a)]})
  const inner=outer*(90-ob.height)/90
  const labels=layoutLabels(scene.satellites.map(s=>({id:s.id,...skyXY(s),priority:s.id===selected})),320,320)
  const wedgeInner=Array.from({length:37},(_,i)=>{const a=(ob.start+ob.width*(36-i)/36)*Math.PI/180;return [160+inner*Math.sin(a),160-inner*Math.cos(a)]})
  return <svg ref={svg} className={'skyplot '+(small?'sky-small':'')} viewBox="0 0 320 320" role="img" aria-label="卫星天空图" data-testid={small?undefined:'skyplot'} onPointerMove={move} onPointerUp={e=>{if(drag.current)onDragEnd?.();drag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId)}} onPointerCancel={()=>{if(drag.current)onDragEnd?.();drag.current=null}}>
    <circle cx="160" cy="160" r="132" className="sky-background"/>
    <circle cx="160" cy="160" r={(outer+maskR)/2} fill="none" stroke="#7c8da5" strokeOpacity=".12" strokeWidth={outer-maskR}/>
    {ob.enabled&&<polygon points={[...wedge,...wedgeInner].map(v=>v.join(',')).join(' ')} fill="#e48d76" fillOpacity=".15" stroke="#e48d76" strokeOpacity=".25"/>}
    {[0,30,60].map(el=><g key={el}><circle cx="160" cy="160" r={outer*(90-el)/90} className="sky-ring"/>{!small&&<text x="164" y={160-outer*(90-el)/90+13} className="sky-tick">{el}°</text>}</g>)}
    {[0,45,90,135].map(a=><line key={a} x1={160+outer*Math.cos(a*Math.PI/180)} y1={160+outer*Math.sin(a*Math.PI/180)} x2={160-outer*Math.cos(a*Math.PI/180)} y2={160-outer*Math.sin(a*Math.PI/180)} className="sky-spoke"/>)}
    <circle cx="160" cy="160" r={maskR} fill="none" stroke="#91a1b5" strokeWidth="1" strokeDasharray="3 5"/>
    {[['N',160,15],['E',307,165],['S',160,312],['W',12,165]].map(([text,x,y])=><text key={text} x={x} y={y} textAnchor="middle" className="sky-cardinal">{text}</text>)}
    <circle cx="160" cy="160" r="2.5" fill="#bfd2dc"/>
    {scene.satellites.map(s=>{
      const at=skyXY(s), state=status(s,scene), active=s.id===selected
      return <g key={s.id} role={small?undefined:'button'} tabIndex={small?undefined:0} aria-label={'天空图卫星 '+s.id} data-satellite-id={s.id} transform={'translate('+at.x+','+at.y+')'} className={'sky-satellite '+(active?'selected':'')} style={{color:colors[state]}} onPointerDown={e=>{if(!onMove)return;e.preventDefault();onSelect?.(s.id);onDragStart?.();drag.current=s.id;svg.current!.setPointerCapture(e.pointerId)}} onKeyDown={e=>{if(!onMove)return;const deltas:Record<string,[number,number]>={ArrowLeft:[-2,0],ArrowRight:[2,0],ArrowUp:[0,2],ArrowDown:[0,-2]};if(deltas[e.key]){e.preventDefault();const [da,de]=deltas[e.key];onMove(s.id,(s.azimuth+da+360)%360,Math.max(0,Math.min(90,s.elevation+de)))}}} onClick={()=>onSelect?.(s.id)}>
        <title>{s.id+' · '+s.azimuth.toFixed(1)+'° / '+s.elevation.toFixed(1)+'° · '+statusNames[state]}</title>
        <circle r={small?5:13} fill="transparent"/>
        {active&&<circle r="11" fill="currentColor" fillOpacity=".12" stroke="currentColor" strokeOpacity=".5"/>}
        <circle r={small?3.5:5} fill={state==='used'?'currentColor':'#161619'} stroke="currentColor" strokeWidth="1.5"/>
        {!small&&<text x={(labels[s.id]?.x??at.x)-at.x} y={(labels[s.id]?.y??at.y)-at.y} textAnchor="middle" dominantBaseline="middle" className="sky-label" fill={active?'#fff3cc':'currentColor'}>{s.id}</text>}
      </g>
    })}
  </svg>
}
