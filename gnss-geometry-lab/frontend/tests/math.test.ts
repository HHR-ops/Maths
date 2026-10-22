import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { analyze, direction, csv } from '../src/math.ts'
import { preset, status, validateProject, initialProject, copy } from '../src/model.ts'
import type { Scene } from '../src/model.ts'
const close=(a:number,b:number,tol=1e-8)=>assert.ok(Math.abs(a-b)<=tol*Math.max(1,Math.abs(b)),String(a)+' ≠ '+String(b))
test('ENU cardinal directions and unit length',()=>{
  const cases:[[number,number],number[]][]=[[[0,0],[0,1,0]],[[90,0],[1,0,0]],[[180,0],[0,-1,0]],[[270,0],[-1,0,0]],[[17,90],[0,0,1]]]
  for(const [[az,el],expected] of cases){const d=direction(az,el);d.forEach((v,i)=>close(v,expected[i]));close(Math.hypot(...d),1)}
})
test('five presets have explicit valid and invalid geometries',()=>{
  for(const id of ['balanced','clustered','obstructed','four']){const r=analyze(preset(id));assert.equal(r.valid,true,id);assert.equal(r.rank,4)}
  const r=analyze(preset('degenerate'));assert.equal(r.valid,false);assert.equal(r.rank,3);assert.equal(r.Q,null)
  assert.ok(analyze(preset('clustered')).dop!.PDOP>analyze(preset('balanced')).dop!.PDOP)
})
test('DOP identities and covariance are consistent',()=>{
  const s=preset('balanced'),r=analyze(s),d=r.dop!
  close(d.GDOP**2,d.PDOP**2+d.TDOP**2);close(d.PDOP**2,d.HDOP**2+d.VDOP**2)
  for(let i=0;i<3;i++)for(let j=0;j<3;j++){close(r.Q![i][j],r.Q![j][i]);close(r.covariance![i][j],s.sigma**2*r.Q![i][j])}
})
test('measurement sigma scales errors but not DOP',()=>{
  const s=preset('balanced'),a=analyze(s);s.sigma=3.5;const b=analyze(s)
  assert.deepEqual(a.dop,b.dop);close(b.ellipse!.major,a.ellipse!.major*3.5);close(b.ellipse!.minor,a.ellipse!.minor*3.5)
  b.ellipsoid!.axes.forEach((v,i)=>close(v,a.ellipsoid!.axes[i]*3.5))
})
test('95% uses distinct 2D and 3D chi-square factors',()=>{
  const s=preset('balanced'),a=analyze(s);s.confidence='95';const b=analyze(s)
  close(b.ellipse!.major/a.ellipse!.major,2.447746830680816)
  close(b.ellipsoid!.axes[0]/a.ellipsoid!.axes[0],2.795483482915108)
  assert.deepEqual(a.dop,b.dop)
})
test('four symmetric satellites match closed-form covariance',()=>{
  const s=preset('four'),r=analyze(s),e=20*Math.PI/180
  close(r.Q![0][0],2/(3*Math.cos(e)**2));close(r.Q![1][1],r.Q![0][0])
  close(r.Q![2][2],4/(3*(1-Math.sin(e))**2))
  close(r.Q![3][3],(1/3+Math.sin(e)**2)/(1-Math.sin(e))**2)
})
test('azimuth rotation preserves DOP and rotates horizontal ellipse',()=>{
  const s=preset('balanced'),a=analyze(s),angle=37
  s.satellites=s.satellites.map(s=>({...s,azimuth:(s.azimuth+angle)%360}));const b=analyze(s)
  for(const key of ['GDOP','PDOP','HDOP','VDOP','TDOP'] as const)close(a.dop![key],b.dop![key])
  close(a.ellipse!.major,b.ellipse!.major);close((a.ellipse!.azimuth+angle)%180,b.ellipse!.azimuth)
})
test('fewer than four satellites never produces an inverse',()=>{
  for(let n=0;n<4;n++){const s=preset('balanced');s.satellites=s.satellites.slice(0,n);const r=analyze(s);assert.equal(r.valid,false);assert.equal(r.dop,null);assert.equal(r.Q,null)}
})
test('identical directions are rank one',()=>{
  const s=preset('balanced');s.satellites=s.satellites.map(v=>({...v,azimuth:30,elevation:45}))
  assert.equal(analyze(s).rank,1)
})
test('removing an observation cannot improve the full geometry DOP',()=>{
  const s=preset('balanced'),a=analyze(s);s.satellites[0].enabled=false;const b=analyze(s)
  assert.equal(b.used.length,a.used.length-1);assert.ok(b.dop!.GDOP>=a.dop!.GDOP-1e-10)
})
test('mask and circular obstruction have precise inclusion boundaries',()=>{
  const s=preset('balanced');s.mask=10;s.obstruction={enabled:true,start:330,width:60,height:40}
  const p={id:'T',azimuth:0,elevation:30,enabled:true}
  assert.equal(status(p,s),'blocked');assert.equal(status({...p,azimuth:30},s),'blocked');assert.equal(status({...p,azimuth:31},s),'used')
  assert.equal(status({...p,elevation:41},s),'used');assert.equal(status({...p,elevation:9},s),'masked');assert.equal(status({...p,enabled:false},s),'disabled')
})
test('NumPy independent references match covariance, axes and orientation',()=>{
  const cases=JSON.parse(fs.readFileSync(new URL('./reference.json',import.meta.url),'utf8')) as Array<{scene:Scene;Q:number[][];ellipse:{major:number;minor:number;azimuth:number};axes:number[]}>
  assert.equal(cases.length,40)
  for(const c of cases){const r=analyze(c.scene);assert.equal(r.valid,true);r.Q!.forEach((row,i)=>row.forEach((v,j)=>close(v,c.Q[i][j],1e-7)));close(r.ellipse!.major,c.ellipse.major,1e-7);close(r.ellipse!.minor,c.ellipse.minor,1e-7);close(r.ellipse!.azimuth,c.ellipse.azimuth,1e-7);r.ellipsoid!.axes.forEach((v,i)=>close(v,c.axes[i],1e-7))}
})
test('serialized projects preserve scenes and comparisons',()=>{
  const p=initialProject();p.snapshots.push({id:'one',scene:copy(p.scene)});assert.deepEqual(validateProject(JSON.parse(JSON.stringify(p))),p)
  const next=validateProject(p);next.scene.satellites[0].elevation=70;assert.notEqual(next.scene.satellites[0].elevation,p.scene.satellites[0].elevation)
})
test('invalid imports fail atomically',()=>{
  const p=initialProject(),original=copy(p)
  for(const modify of [(v:typeof p)=>v.scene.satellites.push({...v.scene.satellites[0]}),(v:typeof p)=>{v.scene.sigma=NaN},(v:typeof p)=>{v.scene.obstruction.width=361},(v:typeof p)=>{v.scene.satellites[0].elevation=-1}]){
    const invalid=copy(p);modify(invalid);assert.throws(()=>validateProject(invalid));assert.deepEqual(p,original)
  }
})
test('CSV includes reproducible geometry and precision assumptions',()=>{
  const s=preset('balanced'),content=csv(s,analyze(s));assert.ok(content.includes('"PDOP"'));assert.ok(content.includes('单一接收机钟差'));assert.ok(content.includes(s.satellites[0].id))
})
