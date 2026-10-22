import { useEffect, useRef, useState } from 'react'
import * as T from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { Scene } from './model'
import { colors, status } from './model'
import { direction, format } from './math'
import type { Result } from './math'
import { layoutLabels } from './labels'
import { RotateCcw, Move3D, Layers3 } from 'lucide-react'
export interface CameraPose { position:[number,number,number];target:[number,number,number] }
interface Props {
  scene:Scene;result:Result;selected:string;onSelect:(id:string)=>void;onMove:(id:string,az:number,el:number)=>void
  onDragStart?:()=>void;onDragEnd?:()=>void;extent?:number;cloud?:number[][];trails?:Scene[]
  pose?:CameraPose|null;onPose?:(pose:CameraPose)=>void;compact?:boolean;title?:string
}
interface SatelliteObject { group:T.Group;marker:T.Mesh;line:T.Line;halo:T.Mesh }
interface Runtime {
  world:T.Scene;camera:T.PerspectiveCamera;renderer:T.WebGLRenderer;controls:OrbitControls
  satellites:T.Group;mask:T.Group;error:T.Group;trails:T.Group;objects:Map<string,SatelliteObject>
  ball:T.Mesh;wire:T.Mesh;cloud:T.Points;octa:T.OctahedronGeometry;halo:T.SphereGeometry
  invalidate:()=>void;reset:(view?:string)=>void;applyPose:(pose:CameraPose)=>void;maskKey:string
}
const GOLD='#d9b970',WHITE='#fff3cc'
export default function Scene3D(props:Props) {
  const host=useRef<HTMLDivElement>(null),layer=useRef<HTMLDivElement>(null),runtime=useRef<Runtime|null>(null),latest=useRef(props)
  const [failed,setFailed]=useState(''),[showError,setShowError]=useState(true)
  latest.current=props
  useEffect(()=>{
    const target=host.current!,labels=layer.current!
    let renderer:T.WebGLRenderer
    try{renderer=new T.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true,powerPreference:'high-performance'})}
    catch{setFailed('当前图形环境未能创建三维视图。天空图与计算仍可使用。');return}
    renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0x101011,0)
    renderer.domElement.setAttribute('aria-label','三维卫星半球');renderer.domElement.dataset.testid='three-canvas';target.prepend(renderer.domElement)
    const world=new T.Scene(),camera=new T.PerspectiveCamera(42,1,.1,150),controls=new OrbitControls(camera,renderer.domElement)
    controls.enableDamping=true;controls.dampingFactor=.12;controls.minDistance=11;controls.maxDistance=40;controls.maxPolarAngle=Math.PI/2-.015;controls.enablePan=false
    const line=(points:T.Vector3[],color:number,opacity=1)=>new T.Line(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color,transparent:true,opacity}))
    const ring=(r:number,y:number,color:number,opacity:number)=>line(Array.from({length:129},(_,i)=>new T.Vector3(r*Math.sin(i/128*2*Math.PI),y,-r*Math.cos(i/128*2*Math.PI))),color,opacity)
    const floor=new T.Mesh(new T.CircleGeometry(8,96),new T.MeshBasicMaterial({color:0x302a20,transparent:true,opacity:.28,side:T.DoubleSide,depthWrite:false}));floor.rotation.x=-Math.PI/2;floor.position.y=-.02;world.add(floor)
    for(const el of [0,30,60])world.add(ring(8*Math.cos(el*Math.PI/180),8*Math.sin(el*Math.PI/180),0x9e9279,el===0?.6:.25))
    for(let az=0;az<360;az+=30)world.add(line(Array.from({length:49},(_,i)=>{const [e,n,u]=direction(az,i/48*90);return new T.Vector3(e*8,u*8,-n*8)}),0x93846a,.23))
    world.add(line([new T.Vector3(-9,0,0),new T.Vector3(9,0,0)],0x877c68,.45),line([new T.Vector3(0,0,-9),new T.Vector3(0,0,9)],0x877c68,.45))
    world.add(new T.AmbientLight(0xffffff,2))
    const light=new T.DirectionalLight(0xffffff,2);light.position.set(6,12,8);world.add(light)
    const base=new T.Mesh(new T.CylinderGeometry(.26,.4,.16,32),new T.MeshStandardMaterial({color:0xc8c2b6,metalness:.4,roughness:.5}));base.position.y=.08;world.add(base)
    const mast=new T.Mesh(new T.CylinderGeometry(.055,.055,.5,12),new T.MeshStandardMaterial({color:0xd9b970}));mast.position.y=.35;world.add(mast)
    const dish=new T.Mesh(new T.SphereGeometry(.2,24,12,0,Math.PI*2,0,Math.PI/2),new T.MeshStandardMaterial({color:0xfff6dc}));dish.position.y=.6;world.add(dish)
    const satellites=new T.Group(),mask=new T.Group(),error=new T.Group(),trails=new T.Group();world.add(satellites,mask,error,trails)
    const octa=new T.OctahedronGeometry(1),halo=new T.SphereGeometry(1,12,8)
    const ball=new T.Mesh(new T.SphereGeometry(1,40,24),new T.MeshBasicMaterial({color:0xe1c27c,transparent:true,opacity:.1,side:T.DoubleSide,depthWrite:false}))
    const wire=new T.Mesh(new T.SphereGeometry(1,20,12),new T.MeshBasicMaterial({color:0xe1c27c,wireframe:true,transparent:true,opacity:.28}))
    ball.position.y=wire.position.y=.16;error.add(ball,wire)
    const cloud=new T.Points(new T.BufferGeometry().setAttribute('position',new T.BufferAttribute(new Float32Array(5000*3),3)),new T.PointsMaterial({color:0x9ac9e6,size:.045,transparent:true,opacity:.55,depthWrite:false}));error.add(cloud)
    let frame=0,disposed=false,applyingPose=false,renders=0
    const invalidate=()=>{if(!disposed&&!frame)frame=requestAnimationFrame(render)}
    const reset=(view='perspective')=>{
      const views:Record<string,[number,number,number]>={perspective:[15,11,16],N:[0,8,-24],S:[0,8,24],E:[24,8,0],W:[-24,8,0],top:[0,26,.001]}
      camera.position.set(...(views[view]||views.perspective));controls.target.set(0,2,0);controls.update();invalidate()
    }
    const applyPose=(pose:CameraPose)=>{
      if(camera.position.distanceToSquared(new T.Vector3(...pose.position))<1e-10&&controls.target.distanceToSquared(new T.Vector3(...pose.target))<1e-10)return
      applyingPose=true;camera.position.set(...pose.position);controls.target.set(...pose.target);controls.update();applyingPose=false;invalidate()
    }
    function render(){
      frame=0;if(disposed)return
      const changed=controls.update()
      renderer.render(world,camera);renderer.domElement.dataset.frameCount=String(++renders);renderer.domElement.dataset.geometryCount=String(renderer.info.memory.geometries);renderer.domElement.dataset.camera=JSON.stringify(camera.position.toArray())
      const width=target.clientWidth,height=target.clientHeight
      const anchors: {id:string;x:number;y:number;priority:boolean}[]=[]
      const nodes=labels.querySelectorAll<HTMLElement>('[data-sat],[data-cardinal]')
      for(const label of nodes){
        let at:T.Vector3
        if(label.dataset.sat){
          const s=latest.current.scene.satellites.find(s=>s.id===label.dataset.sat)
          if(!s){label.hidden=true;continue}
          const [e,n,u]=direction(s.azimuth,s.elevation);at=new T.Vector3(e*8,u*8,-n*8)
        }else{
          const coordinates:Record<string,[number,number,number]>={N:[0,0,-8.8],E:[8.8,0,0],S:[0,0,8.8],W:[-8.8,0,0]};at=new T.Vector3(...coordinates[label.dataset.cardinal!])
        }
        at.project(camera)
        const x=(at.x*.5+.5)*width,y=(-at.y*.5+.5)*height,visible=Math.abs(at.x)<=1&&Math.abs(at.y)<=1&&at.z<=1
        label.hidden=!visible
        if(!visible)continue
        if(label.dataset.sat)anchors.push({id:label.dataset.sat,x,y,priority:label.dataset.sat===latest.current.selected})
        else{label.style.left=x+'px';label.style.top=y+'px'}
      }
      const placed=layoutLabels(anchors,width,height)
      for(const label of labels.querySelectorAll<HTMLElement>('[data-sat]')){
        const at=placed[label.dataset.sat!];if(!at)continue
        label.style.left=at.x+'px';label.style.top=at.y+'px';label.style.transform='translate(-50%,-50%)'
      }
      if(changed)invalidate()
    }
    const onChange=()=>{
      invalidate()
      if(!applyingPose)latest.current.onPose?.({position:camera.position.toArray() as CameraPose['position'],target:controls.target.toArray() as CameraPose['target']})
    }
    controls.addEventListener('change',onChange)
    runtime.current={world,camera,renderer,controls,satellites,mask,error,trails,objects:new Map(),ball,wire,cloud,octa,halo,invalidate,reset,applyPose,maskKey:''}
    reset()
    if(latest.current.pose)applyPose(latest.current.pose)
    const resize=()=>{const w=target.clientWidth,h=target.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();invalidate()}
    const observer=new ResizeObserver(resize);observer.observe(target);resize()
    const raycaster=new T.Raycaster(),mouse=new T.Vector2();let dragging:string|null=null,previous=new T.Vector3()
    const setRay=(e:PointerEvent)=>{const b=target.getBoundingClientRect();mouse.set((e.clientX-b.left)/b.width*2-1,-(e.clientY-b.top)/b.height*2+1);raycaster.setFromCamera(mouse,camera)}
    const begin=(e:PointerEvent)=>{
      if(e.button!==0||latest.current.compact)return
      const label=(e.target as Element).closest<HTMLElement>('[data-sat]')
      setRay(e);const hit=raycaster.intersectObjects(satellites.children,true).find(h=>h.object.userData.satellite)
      const id=label?.dataset.sat||hit?.object.userData.satellite;if(!id)return
      dragging=id;controls.enabled=false;latest.current.onDragStart?.();latest.current.onSelect(id)
      const s=latest.current.scene.satellites.find(s=>s.id===id)!,[ee,nn,uu]=direction(s.azimuth,s.elevation);previous.set(ee*8,uu*8,-nn*8)
      target.setPointerCapture(e.pointerId);e.preventDefault()
    }
    const move=(e:PointerEvent)=>{
      if(!dragging)return;setRay(e)
      const ray=raycaster.ray,b=ray.origin.dot(ray.direction),c=ray.origin.lengthSq()-64,disc=b*b-c;if(disc<0)return
      const candidates=[-b-Math.sqrt(disc),-b+Math.sqrt(disc)].filter(t=>t>0).map(t=>ray.at(t,new T.Vector3())).sort((a,b)=>a.distanceToSquared(previous)-b.distanceToSquared(previous))
      const p=candidates[0];if(!p)return;p.y=Math.max(0,p.y);p.normalize().multiplyScalar(8);previous.copy(p)
      latest.current.onMove(dragging,(Math.atan2(p.x,-p.z)*180/Math.PI+360)%360,Math.asin(Math.min(1,p.y/8))*180/Math.PI)
    }
    const end=(e:PointerEvent)=>{if(dragging)latest.current.onDragEnd?.();dragging=null;controls.enabled=true;if(target.hasPointerCapture(e.pointerId))target.releasePointerCapture(e.pointerId);invalidate()}
    target.addEventListener('pointerdown',begin);target.addEventListener('pointermove',move);target.addEventListener('pointerup',end);target.addEventListener('pointercancel',end)
    return()=>{
      disposed=true;cancelAnimationFrame(frame);observer.disconnect();controls.removeEventListener('change',onChange);controls.dispose()
      target.removeEventListener('pointerdown',begin);target.removeEventListener('pointermove',move);target.removeEventListener('pointerup',end);target.removeEventListener('pointercancel',end)
      const geometries=new Set<T.BufferGeometry>(),materials=new Set<T.Material>()
      world.traverse(o=>{const mesh=o as T.Mesh;if(mesh.geometry)geometries.add(mesh.geometry);if(mesh.material)(Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(m=>materials.add(m))})
      geometries.add(octa);geometries.add(halo);geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())
      renderer.dispose();renderer.domElement.remove();runtime.current=null
    }
  },[])
  useEffect(()=>{
    const rt=runtime.current;if(!rt)return
    const ids=new Set(props.scene.satellites.map(s=>s.id))
    for(const [id,o] of rt.objects)if(!ids.has(id)){o.line.geometry.dispose();[o.marker.material,o.line.material,o.halo.material].flat().forEach(m=>m.dispose());rt.satellites.remove(o.group);rt.objects.delete(id)}
    for(const s of props.scene.satellites){
      let o=rt.objects.get(s.id)
      if(!o){
        const group=new T.Group(),marker=new T.Mesh(rt.octa,new T.MeshStandardMaterial({transparent:true})),halo=new T.Mesh(rt.halo,new T.MeshBasicMaterial({transparent:true,opacity:.1,depthWrite:false}))
        const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(new Float32Array(6),3))
        const line=new T.Line(geometry,new T.LineBasicMaterial({transparent:true}))
        marker.userData.satellite=s.id;group.add(marker,line,halo);o={group,marker,line,halo};rt.objects.set(s.id,o);rt.satellites.add(group)
      }
      const state=status(s,props.scene),used=state==='used',selected=s.id===props.selected,color=new T.Color(selected?WHITE:colors[state])
      const [e,n,u]=direction(s.azimuth,s.elevation),at=new T.Vector3(e*8,u*8,-n*8)
      o.marker.position.copy(at);o.marker.scale.setScalar(selected?.25:.18)
      const markerMaterial=o.marker.material as T.MeshStandardMaterial;markerMaterial.color.copy(color);markerMaterial.emissive.copy(color);markerMaterial.emissiveIntensity=used?.4:.04;markerMaterial.opacity=used?1:.5
      const array=o.line.geometry.getAttribute('position') as T.BufferAttribute;array.setXYZ(0,0,.16,0);array.setXYZ(1,at.x,at.y,at.z);array.needsUpdate=true;o.line.geometry.computeBoundingSphere()
      const material=o.line.material as T.LineBasicMaterial;material.color.copy(color);material.opacity=used?.55:.12
      o.halo.position.copy(at);o.halo.scale.setScalar(.4);o.halo.visible=selected;(o.halo.material as T.MeshBasicMaterial).color.copy(color)
    }
    const key=JSON.stringify([props.scene.mask,props.scene.obstruction])
    if(key!==rt.maskKey){
      for(const o of [...rt.mask.children]){const m=o as T.Mesh;m.geometry?.dispose();(m.material as T.Material)?.dispose();rt.mask.remove(o)}
      const angle=props.scene.mask*Math.PI/180
      const ring=new T.Line(new T.BufferGeometry().setFromPoints(Array.from({length:129},(_,i)=>new T.Vector3(8*Math.cos(angle)*Math.sin(i/128*2*Math.PI),8*Math.sin(angle),-8*Math.cos(angle)*Math.cos(i/128*2*Math.PI)))),new T.LineDashedMaterial({color:0xa89e87,dashSize:.15,gapSize:.14,transparent:true,opacity:.55}));ring.computeLineDistances();rt.mask.add(ring)
      const ob=props.scene.obstruction
      if(ob.enabled){
        const vertices:number[]=[]
        for(let i=0;i<48;i++){const a=(ob.start+ob.width*i/48)*Math.PI/180,b=(ob.start+ob.width*(i+1)/48)*Math.PI/180,h=ob.height*Math.PI/180;const at=(az:number,el:number)=>[8.02*Math.cos(el)*Math.sin(az),8.02*Math.sin(el),-8.02*Math.cos(el)*Math.cos(az)];vertices.push(...at(a,0),...at(b,0),...at(a,h),...at(a,h),...at(b,0),...at(b,h))}
        const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(vertices,3));rt.mask.add(new T.Mesh(geometry,new T.MeshBasicMaterial({color:0xe48d76,transparent:true,opacity:.11,side:T.DoubleSide,depthWrite:false})))
      }
      rt.maskKey=key
    }
    rt.error.visible=showError&&Boolean(props.result.ellipsoid)
    if(props.result.ellipsoid){
      const {axes,vectors}=props.result.ellipsoid,multiplier=2.3/(props.extent??axes[0])
      const basis=vectors.map(v=>new T.Vector3(v[0],v[2],-v[1]));if(new T.Vector3().crossVectors(basis[0],basis[1]).dot(basis[2])<0)basis[2].negate()
      const matrix=new T.Matrix4().makeBasis(basis[0],basis[1],basis[2]);rt.ball.quaternion.setFromRotationMatrix(matrix);rt.ball.scale.set(...axes.map(a=>a*multiplier) as [number,number,number]);rt.wire.quaternion.copy(rt.ball.quaternion);rt.wire.scale.copy(rt.ball.scale)
      const cloud=props.cloud||[],attribute=rt.cloud.geometry.getAttribute('position') as T.BufferAttribute,positions=attribute.array as Float32Array
      cloud.forEach((p,i)=>{positions[i*3]=p[0]*multiplier;positions[i*3+1]=p[2]*multiplier+.16;positions[i*3+2]=-p[1]*multiplier})
      attribute.needsUpdate=true;rt.cloud.geometry.setDrawRange(0,cloud.length);rt.cloud.geometry.computeBoundingSphere();rt.cloud.visible=cloud.length>0
    }
    rt.invalidate()
  },[props.scene,props.result,props.selected,props.extent,props.cloud,showError])
  useEffect(()=>{
    const rt=runtime.current;if(!rt)return
    for(const o of [...rt.trails.children]){const l=o as T.Line;l.geometry.dispose();(l.material as T.Material).dispose();rt.trails.remove(o)}
    for(const sat of props.trails?.[0]?.satellites||[]){
      const points=props.trails!.flatMap(scene=>{const s=scene.satellites.find(s=>s.id===sat.id);if(!s)return[];const [e,n,u]=direction(s.azimuth,s.elevation);return [new T.Vector3(e*8,u*8,-n*8)]})
      if(points.length>1)rt.trails.add(new T.Line(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color:0xd5b770,transparent:true,opacity:.2})))
    }
    rt.invalidate()
  },[props.trails])
  useEffect(()=>{if(props.pose)runtime.current?.applyPose(props.pose)},[props.pose])
  const extent=props.extent??props.result.ellipsoid?.axes[0]
  return <div className={'scene3d '+(props.compact?'compact-scene':'')} data-testid="scene3d"><div className="scene-title"><span className="eyebrow">LOCAL SKY · ENU</span><h2>{props.title||'卫星几何空间'}</h2>{!props.compact&&<p>拖动卫星改变方向，拖动空白处旋转视角</p>}</div><div className="scene-actions"><button className={showError?'icon-button active':'icon-button'} aria-label="显示误差椭球" title="显示误差椭球" aria-pressed={showError} onClick={()=>setShowError(v=>!v)}><Layers3 size={17}/></button><button className="icon-button" aria-label="复位三维视角" title="复位三维视角" onClick={()=>runtime.current?.reset()}><RotateCcw size={16}/></button></div><div className="three-host" ref={host}><div className="three-labels" ref={layer}>{props.scene.satellites.map(s=><button key={s.id} data-sat={s.id} className={'sat-label '+(s.id===props.selected?'selected':'')} style={{color:colors[status(s,props.scene)]}} aria-label={'三维卫星 '+s.id}>{s.id}</button>)}{['N','E','S','W'].map(c=><span key={c} data-cardinal={c} className="three-cardinal">{c}</span>)}</div></div>
    <div className="view-widget" aria-label="ENU 视角控件"><button aria-label="北侧视角" onClick={()=>runtime.current?.reset('N')}>N</button><div><button aria-label="西侧视角" onClick={()=>runtime.current?.reset('W')}>W</button><button aria-label="顶视图" onClick={()=>runtime.current?.reset('top')}>顶</button><button aria-label="东侧视角" onClick={()=>runtime.current?.reset('E')}>E</button></div><button aria-label="南侧视角" onClick={()=>runtime.current?.reset('S')}>S</button></div>
    {failed&&<div className="webgl-fallback" role="status"><Move3D size={26}/>{failed}</div>}
    <div className="scene-foot"><span><i className="status-dot"/>{props.compact?'相同 ENU 观察框架':'卫星方向 · 单一接收机钟差'}</span><span>{props.extent?'统一':'自适应'}误差半轴范围 {format(extent)} m</span></div>
  </div>
}
