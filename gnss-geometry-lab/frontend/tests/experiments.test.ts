import test from 'node:test'
import assert from 'node:assert/strict'
import {preset} from '../src/model.ts'
import {analyze} from '../src/math.ts'
import {trajectoryScene,trajectorySeries,simulate,ecef,topocentric,parseSP3,sampleSP3,ephemerisScene,defaultStation} from '../src/experiments.ts'
import {layoutLabels} from '../src/labels.ts'
const close=(a:number,b:number,tolerance=1e-8)=>assert.ok(Math.abs(a-b)<=tolerance,String(a)+' != '+String(b))
test('independent teaching trajectories start at the editing scene and change DOP',()=>{
  const s=preset('balanced'),frame=trajectoryScene(s,0)
  for(let i=0;i<s.satellites.length;i++){close(frame.satellites[i].azimuth,s.satellites[i].azimuth);close(frame.satellites[i].elevation,s.satellites[i].elevation)}
  const series=trajectorySeries(s);assert.equal(series.length,101)
  assert.ok(series.some(p=>p.PDOP!==null&&Math.abs(p.PDOP-series[0].PDOP!)>.2))
  for(const t of [0,.25,.5,.75,1])for(const sat of trajectoryScene(s,t).satellites){assert.ok(sat.azimuth>=0&&sat.azimuth<360);assert.ok(sat.elevation>=0&&sat.elevation<=90)}
})
test('rank failure is represented by null time series values',()=>{
  const s=preset('degenerate');assert.equal(trajectorySeries(s)[0].PDOP,null)
})
test('seeded range-noise solutions reproduce analytic covariance and coverage',()=>{
  const s=preset('balanced'),r=analyze(s),c=simulate(s,5000,2026),again=simulate(s,5000,2026)
  assert.deepEqual(c,again)
  for(let i=0;i<3;i++)close(c.covariance[i][i]/r.covariance![i][i],1,.06)
  close(c.estimatedPDOP,r.dop!.PDOP,.06)
  close(c.coverage2,.3934693403,.025);close(c.coverage3,.1987480431,.025)
  const ninety=simulate({...s,confidence:'95'},5000,2026)
  assert.deepEqual(c.points,ninety.points);close(ninety.coverage2,.95,.018);close(ninety.coverage3,.95,.018)
  const doubled=simulate({...s,sigma:2},5000,2026)
  for(let i=0;i<3;i++)close(doubled.covariance[i][i],c.covariance[i][i]*4,1e-8)
  assert.notDeepEqual(c.points,simulate(s,5000,42).points)
})
test('noise experiments reject insufficient geometry and invalid counts',()=>{
  assert.throws(()=>simulate(preset('degenerate')),/几何/)
  for(const count of [0,99,5001,100.5,NaN])assert.throws(()=>simulate(preset('balanced'),count))
})
test('WGS84 and ENU match analytic equatorial directions',()=>{
  assert.deepEqual(ecef({latitude:0,longitude:0,height:0}),[6378137,0,0])
  const station={latitude:0,longitude:0,height:0},up=topocentric([26378137,0,0],station),east=topocentric([6378137,20000000,0],station),north=topocentric([6378137,0,20000000],station)
  close(up.elevation,90);close(east.azimuth,90);close(east.elevation,0);close(north.azimuth,0);close(north.elevation,0)
  assert.throws(()=>ecef({...station,latitude:91}))
})
test('SP3 fixed-width kilometres convert to metres and preserve time-system labels',()=>{
  const text='#dP2026 10 22  0  0  0.00000000       1 ORBIT WGS84 SIM  LAB\n%c M  cc GPS ccc\n*  2026 10 22  0  0  0.00000000\nPG01  26378.137000      0.000000      0.000000      0.000000\nEOF'
  const data=parseSP3(text);assert.equal(data.timeSystem,'GPS');assert.equal(data.frame,'WGS84');assert.deepEqual(data.epochs[0].positions.G01,[26378137,0,0])
  assert.equal(data.epochs[0].label,'2026-10-22 00:00:00.000')
  const scene=ephemerisScene(data,0,'G',{latitude:0,longitude:0,height:0},preset('balanced'));close(scene.satellites[0].elevation,90)
})
test('SP3 teaching sample round trips directions, epochs and single-constellation selection',()=>{
  const base=preset('balanced'),text=sampleSP3(base),data=parseSP3(text)
  assert.equal(data.epochs.length,5);close(data.epochs[1].time-data.epochs[0].time,900000)
  const scene=ephemerisScene(data,0,'G',defaultStation,base)
  assert.equal(scene.satellites.length,8)
  scene.satellites.forEach((s,i)=>{close(s.azimuth,base.satellites[i].azimuth,1e-7);close(s.elevation,base.satellites[i].elevation,1e-7)})
  const multi=parseSP3(text.replaceAll('PG01','PE01'));assert.deepEqual(multi.systems,['E','G'])
  assert.equal(ephemerisScene(multi,0,'E',defaultStation,base).satellites.length,1)
  assert.equal(ephemerisScene(multi,0,'G',defaultStation,base).satellites.length,7)
})
test('SP3 rejects duplicates, invalid epochs, missing positions and unsupported formats',()=>{
  const text=sampleSP3(preset('balanced')),lines=text.split('\n'),record=lines.find(l=>l.startsWith('PG01'))!
  assert.throws(()=>parseSP3(text.replace(record,record+'\n'+record)),/重复/)
  const epoch=lines.find(l=>l.startsWith('*'))!
  assert.throws(()=>parseSP3(text.replace(epoch,'*  2026 10 22 0 0 60')),/历元/)
  assert.throws(()=>parseSP3(text.replace(epoch,'*  2026 10 22 0 0.5 0')),/历元/)
  assert.throws(()=>parseSP3(text.replace(epoch,'*  2026 2 30 0 0 0')),/日期/)
  assert.throws(()=>parseSP3(text.replace('#dP','#aP')),/SP3/)
  assert.throws(()=>parseSP3('#dP\n* 2026 10 22 0 0 0\nEOF'),/有效/)
  assert.throws(()=>parseSP3(text.replace('PG02','PG01')),/重复/)
})
test('label layout keeps selected labels inside the viewport and avoids simple collisions',()=>{
  const placed=layoutLabels([{id:'A',x:5,y:5,priority:true},{id:'B',x:5,y:5},{id:'C',x:5,y:5}],320,320)
  for(const p of Object.values(placed)){assert.ok(p.x>=21&&p.x<=299);assert.ok(p.y>=12&&p.y<=308)}
  assert.notDeepEqual(placed.A,placed.B)
})
