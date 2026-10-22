import {useId} from 'react'
import type { Result } from './math'
import { format } from './math'
import type { Scene } from './model'
export default function Ellipse({result,scene,extent,points=[]}:{result:Result;scene:Scene;extent?:number;points?:number[][]}) {
  const id=useId().replace(/:/g,''),ellipse=result.ellipse
  if(!ellipse)return <div className="ellipse-empty"><span>等待可解算的几何构型</span><small>改变卫星分布后，误差区域将在这里显示。</small></div>
  const limit=Math.max(extent??ellipse.major,.00001),scale=78/limit,angle=ellipse.azimuth-90
  return <><svg viewBox="0 0 300 210" className="ellipse-svg" aria-label="水平误差椭圆" data-testid="error-ellipse" data-extent={limit}>
    <defs><radialGradient id={id}><stop offset="0" stopColor="#d9b970" stopOpacity=".18"/><stop offset="1" stopColor="#d9b970" stopOpacity=".03"/></radialGradient><clipPath id={id+'clip'}><rect x="20" y="18" width="260" height="172"/></clipPath></defs>
    {[39,78].map(r=><circle key={r} cx="150" cy="103" r={r} fill="none" stroke="#39362f" strokeDasharray="3 5"/>)}
    <path d="M35 103 H265 M150 14 V192" stroke="#58534a" strokeWidth="1"/>
    <text x="271" y="107" className="sky-cardinal">E</text><text x="146" y="12" className="sky-cardinal">N</text>
    <g clipPath={'url(#'+id+'clip)'}>
      {points.map((p,i)=><circle key={i} cx={150+p[0]*scale} cy={103-p[1]*scale} r=".9" fill="#b2cfeb" opacity=".32"/>)}
      <g transform={'translate(150 103) rotate('+angle+')'}>
        <ellipse rx={ellipse.major*scale} ry={ellipse.minor*scale} fill={'url(#'+id+')'} stroke="#e1c27c" strokeWidth="1.8"/>
        <line x1={-ellipse.major*scale} x2={ellipse.major*scale} stroke="#d9b970" strokeDasharray="4 4"/>
        <line y1={-ellipse.minor*scale} y2={ellipse.minor*scale} stroke="#d9b970" strokeOpacity=".5"/>
      </g>
    </g><circle cx="150" cy="103" r="3" fill="#fff3cc"/>
    <text x="150" y="206" textAnchor="middle" className="sky-tick">{extent?'统一比例':'自适应比例'} · 外圈 {format(limit)} m</text>
  </svg><div className="ellipse-values"><span>长半轴 <b data-testid="ellipse-major">{format(ellipse.major)} <small>m</small></b></span><span>短半轴 <b>{format(ellipse.minor)} <small>m</small></b></span><span>方位角 <b>{format(ellipse.azimuth,1)}<small>°</small></b></span></div><p className="micro">{scene.confidence==='95'?'二维高斯 95% 置信椭圆':'标准椭圆 · 二维高斯覆盖率约 39.35%'}{ellipse.major>limit?' · 椭圆超出当前比例范围':''}{points.length>0?' · 蓝点为噪声实验样本，视窗外样本未显示':''}</p></>
}
