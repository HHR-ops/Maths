import { Matrix, SingularValueDecomposition } from 'ml-matrix'
import type { Scene } from './model.ts'
import { analyze, direction } from './math.ts'
export function trajectoryScene(base:Scene, t:number):Scene {
  return {...base,satellites:base.satellites.map((s,i)=>{
    const phase=(i*2.399963)%6.283185307
    const az=s.azimuth+(26+i%5*11)*t+12*(Math.sin(2*Math.PI*t+phase)-Math.sin(phase))
    const el=s.elevation+(11+i%4*5)*(Math.sin(Math.PI*t+phase)-Math.sin(phase))
    return {...s,azimuth:(az%360+360)%360,elevation:Math.max(0,Math.min(90,el))}
  })}
}
export interface SeriesPoint { t:number; PDOP:number|null; HDOP:number|null; VDOP:number|null; used:number }
export function trajectorySeries(base:Scene):SeriesPoint[] {
  return Array.from({length:101},(_,i)=>{const r=analyze(trajectoryScene(base,i/100));return {t:i/100,PDOP:r.dop?.PDOP??null,HDOP:r.dop?.HDOP??null,VDOP:r.dop?.VDOP??null,used:r.used.length}})
}
export interface Cloud { points:[number,number,number][];mean:number[];covariance:number[][];coverage2:number;coverage3:number;estimatedPDOP:number;count:number;seed:number }
export function simulate(scene:Scene,count=2000,seed=2026):Cloud {
  if(!Number.isInteger(count)||count<100||count>5000||!Number.isInteger(seed)||seed<0||seed>4294967295)throw Error('样本数为 100–5000，种子为 32 位非负整数。')
  const r=analyze(scene)
  if(!r.valid||!r.ellipse||!r.ellipsoid)throw Error('请先选择可解算的卫星几何。')
  if((r.condition??Infinity)>1e6)throw Error('几何过于病态，请调整方向后再进行噪声实验。')
  const k=new SingularValueDecomposition(new Matrix(r.G),{autoTranspose:true}).inverse().to2DArray()
  let state=seed>>>0
  const uniform=()=>{state+=0x6d2b79f5;let t=state;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296}
  const normal=()=>Math.sqrt(-2*Math.log(Math.max(uniform(),1e-15)))*Math.cos(2*Math.PI*uniform())
  const points:[number,number,number][]=[],mean=[0,0,0]
  let inside2=0,inside3=0
  const c=r.covariance!,det=c[0][0]*c[1][1]-c[0][1]**2
  for(let n=0;n<count;n++){
    const noise=r.used.map(()=>normal()*scene.sigma)
    const point=k.slice(0,3).map(row=>row.reduce((sum,v,i)=>sum+v*noise[i],0)) as [number,number,number]
    points.push(point);point.forEach((v,i)=>{mean[i]+=v/count})
    const [e,north]=point
    const m2=(c[1][1]*e*e-2*c[0][1]*e*north+c[0][0]*north*north)/det
    const m3=r.ellipsoid.vectors.reduce((sum,v,i)=>{
      const std=r.ellipsoid!.axes[i]/r.ellipsoid!.factor
      return sum+(v.reduce((s,x,j)=>s+x*point[j],0)/std)**2
    },0)
    if(m2<=r.ellipse.factor**2)inside2++
    if(m3<=r.ellipsoid.factor**2)inside3++
  }
  const covariance=Array.from({length:3},(_,i)=>Array.from({length:3},(_,j)=>points.reduce((sum,p)=>sum+(p[i]-mean[i])*(p[j]-mean[j]),0)/(count-1)))
  return {points,mean,covariance,coverage2:inside2/count,coverage3:inside3/count,estimatedPDOP:Math.sqrt(covariance.reduce((s,row,i)=>s+row[i],0))/scene.sigma,count,seed}
}
export interface Station { latitude:number;longitude:number;height:number }
export interface Epoch { label:string;time:number;positions:Record<string,[number,number,number]> }
export interface Ephemeris { filename:string;timeSystem:string;frame:string;systems:string[];epochs:Epoch[];skipped:number }
export const defaultStation:Station={latitude:30,longitude:114,height:50}
export function ecef(station:Station):[number,number,number] {
  const {latitude,longitude,height}=station
  if(![latitude,longitude,height].every(Number.isFinite)||Math.abs(latitude)>90||Math.abs(longitude)>180||height< -500||height>10000)throw Error('站点纬度为 ±90°，经度为 ±180°，椭球高为 −500–10000 m。')
  const p=latitude*Math.PI/180,l=longitude*Math.PI/180,f=1/298.257223563,e2=f*(2-f),N=6378137/Math.sqrt(1-e2*Math.sin(p)**2)
  return [(N+height)*Math.cos(p)*Math.cos(l),(N+height)*Math.cos(p)*Math.sin(l),(N*(1-e2)+height)*Math.sin(p)]
}
export function topocentric(position:number[],station:Station) {
  const at=ecef(station),[dx,dy,dz]=position.map((v,i)=>v-at[i]),p=station.latitude*Math.PI/180,l=station.longitude*Math.PI/180
  const east=-Math.sin(l)*dx+Math.cos(l)*dy,north=-Math.sin(p)*Math.cos(l)*dx-Math.sin(p)*Math.sin(l)*dy+Math.cos(p)*dz,up=Math.cos(p)*Math.cos(l)*dx+Math.cos(p)*Math.sin(l)*dy+Math.sin(p)*dz
  return {azimuth:(Math.atan2(east,north)*180/Math.PI+360)%360,elevation:Math.atan2(up,Math.hypot(east,north))*180/Math.PI}
}
export function parseSP3(text:string,filename='orbit.sp3'):Ephemeris {
  if(text.length>12*1024*1024)throw Error('SP3 文件超过 12 MB。')
  const lines=text.replace(/^\uFEFF/,'').split(/\r?\n/),head=lines[0]||''
  if(!/^#[cd][PV]/i.test(head))throw Error('请选择 SP3-c 或 SP3-d 文本文件（不是压缩文件）。')
  const epochs:Epoch[]=[],systems=new Set<string>()
  let current:Epoch|null=null,timeSystem='未声明',skipped=0
  for(const [i,line] of lines.entries()){
    if(line.startsWith('%c')){
      const match=line.match(/\b(GPS|UTC|TAI|GAL|BDT|QZS|GLO|IRN)\b/);if(match)timeSystem=match[1]
    }
    if(line.startsWith('*')){
      const parts=line.slice(1).trim().split(/\s+/).map(Number)
      const [y,m,d,h,min,sec]=parts
      if(parts.length!==6||!parts.every(Number.isFinite)||!parts.slice(0,5).every(Number.isInteger)||y<1980||y>2100||m<1||m>12||d<1||d>31||h<0||h>23||min<0||min>59||sec<0||sec>=60)throw Error('第 '+(i+1)+' 行历元无效；闰秒 60 尚不支持。')
      const date=new Date(Date.UTC(y,m-1,d,h,min,Math.floor(sec),Math.round(sec%1*1000))),time=date.getTime()
      if(date.getUTCFullYear()!==y||date.getUTCMonth()!==m-1||date.getUTCDate()!==d)throw Error('SP3 历元日期无效。')
      if(epochs.length&&time<=epochs.at(-1)!.time)throw Error('SP3 历元必须按时间严格递增。')
      if(epochs.length>=4096)throw Error('单次支持最多 4096 个历元。')
      current={label:date.toISOString().replace('T',' ').replace('Z',''),time,positions:{}};epochs.push(current)
    }else if(line.startsWith('P')){
      if(!current)throw Error('位置记录出现在历元之前。')
      const id=line.slice(1,4).trim().toUpperCase()
      if(!/^[GRECJIS]\d{2}$/.test(id))throw Error('第 '+(i+1)+' 行卫星编号无效。')
      const p=[line.slice(4,18),line.slice(18,32),line.slice(32,46)].map(s=>s.trim()?Number(s):NaN)
      if(!p.every(Number.isFinite))throw Error('第 '+(i+1)+' 行坐标不是有限数值。')
      if(p.every(v=>v===0)||p.some(v=>Math.abs(v)>=999999)){skipped++;continue}
      if(Math.hypot(...p)<6000||Math.hypot(...p)>100000){skipped++;continue}
      if(current.positions[id])throw Error('同一历元出现重复卫星 '+id+'。')
      current.positions[id]=p.map(v=>v*1000) as [number,number,number];systems.add(id[0])
      if(Object.keys(current.positions).length>256)throw Error('单历元最多支持 256 颗卫星。')
    }
  }
  if(!epochs.length||!systems.size)throw Error('文件没有有效的卫星位置历元。')
  return {filename,timeSystem,frame:head.slice(46,51).trim()||'文件未标明',systems:[...systems].sort(),epochs,skipped}
}
export function ephemerisScene(data:Ephemeris,index:number,system:string,station:Station,settings:Scene):Scene {
  const epoch=data.epochs[Math.max(0,Math.min(data.epochs.length-1,Math.round(index)))]
  ecef(station)
  const satellites=Object.entries(epoch.positions).filter(([id])=>id[0]===system).map(([id,p])=>({id,...topocentric(p,station),enabled:true})).filter(s=>s.elevation>= -1e-8).map(s=>({...s,elevation:Math.max(0,s.elevation)}))
  if(satellites.length>64)throw Error('所选系统的地平线上卫星超过 64 颗。')
  return {...settings,name:('SP3 '+system+' '+epoch.label+' '+data.timeSystem).slice(0,80),satellites}
}
export function sampleSP3(base:Scene):string {
  const station=defaultStation,at=ecef(station),p=station.latitude*Math.PI/180,l=station.longitude*Math.PI/180
  const lines=['#dP2026 10 22  0  0  0.00000000       5 ORBIT WGS84 SIM  LAB','%c M  cc GPS ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc','/* SYNTHETIC TEACHING DATA, NOT ACTUAL SATELLITE ORBITS.']
  for(let i=0;i<5;i++){
    lines.push('*  2026 10 22  '+String(Math.floor(i/4)).padStart(2)+' '+String(i%4*15).padStart(2)+'  0.00000000')
    const scene=trajectoryScene(base,i/4)
    scene.satellites.forEach((sat,j)=>{
      const [e,n,u]=direction(sat.azimuth,sat.elevation).map(v=>v*26000000)
      const delta=[-Math.sin(l)*e-Math.sin(p)*Math.cos(l)*n+Math.cos(p)*Math.cos(l)*u,Math.cos(l)*e-Math.sin(p)*Math.sin(l)*n+Math.cos(p)*Math.sin(l)*u,Math.cos(p)*n+Math.sin(p)*u]
      lines.push('PG'+String(j+1).padStart(2,'0')+delta.map((v,k)=>((v+at[k])/1000).toFixed(6).padStart(14)).join('')+'      0.000000')
    })
  }
  lines.push('EOF')
  return lines.join('\n')
}
