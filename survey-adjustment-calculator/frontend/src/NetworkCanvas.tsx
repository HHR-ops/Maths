import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, CircleDot, Crosshair, Hand, Link2, LocateFixed, MousePointer2, Plus, Ruler, Triangle, ZoomIn, ZoomOut } from 'lucide-react'
import type { Point, Project, Selection, Solution } from './types'
import { kinds } from './types'
import { Button } from './ui'

const names: Record<string, string> = { height: '高差', distance: '距离', angle: '水平角', azimuth: '方位角', gnss: 'GNSS 基线', coordinate: '坐标观测' }
const hints: Record<string, string> = { select: '拖动点以调整网形 · 拖动空白处平移 · 滚轮缩放', point: '点击画布添加控制点，再在右侧填写坐标与固定分量', height: '依次点击起点、终点，添加高差观测', distance: '依次点击起点、终点，添加距离观测', angle: '依次点击后视点、测站、前视点，添加水平角', azimuth: '依次点击测站、目标点，添加方位角', gnss: '依次点击起点、终点，添加三维基线', coordinate: '点击一个控制点，添加坐标观测' }
export default function NetworkCanvas({ project, selection, onSelect, onMove, onAdd, onConnect, solution, fitVersion, showPrecision, onTogglePrecision }: { project: Project; selection: Selection; onSelect: (s: Selection) => void; onMove: (id: string, point: Point) => void; onAdd: (x: number, y: number) => void; onConnect: (kind: string, ids: string[]) => void; solution: Solution | null; fitVersion: number; showPrecision: boolean; onTogglePrecision: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 800, h: 400 })
  const [camera, setCamera] = useState({ x: 50, y: 65, scale: 2.2 })
  const [tool, setTool] = useState('select')
  const [chain, setChain] = useState<string[]>([])
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)
  const [moving, setMoving] = useState<{ id: string; point: Point } | null>(null)
  const drag = useRef<{ id?: string; px: number; py: number; cam: typeof camera; moved: boolean; initial?: Point } | null>(null)
  const suppress = useRef(false)
  const points = { ...project.points, ...(moving ? { [moving.id]: moving.point } : {}) }
  const fit = () => {
    const p = Object.values(project.points)
    if (!p.length) { setCamera({ x: 50, y: 65, scale: 2.2 }); return }
    const xs = p.map(p => p.X), ys = p.map(p => p.Y)
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
    setCamera({ x: (minX+maxX)/2, y: (minY+maxY)/2, scale: Math.min((size.w-150)/Math.max(maxY-minY, 60), (size.h-120)/Math.max(maxX-minX, 60), 8) })
  }
  useEffect(() => { const observer = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height })); if (ref.current) observer.observe(ref.current); return () => observer.disconnect() }, [])
  useEffect(() => { fit(); setChain([]); setTool('select') }, [fitVersion, size.w, size.h])
  useEffect(() => { const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { setChain([]); setTool('select') } }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [])
  const xy = (p: Point) => ({ x: size.w/2 + (p.Y-camera.y)*camera.scale, y: size.h/2 - (p.X-camera.x)*camera.scale })
  const world = (sx: number, sy: number) => ({ x: camera.x - (sy-size.h/2)/camera.scale, y: camera.y + (sx-size.w/2)/camera.scale })
  const local = (e: React.PointerEvent | React.WheelEvent) => { const r = ref.current!.getBoundingClientRect(); return { x: e.clientX-r.left, y: e.clientY-r.top } }
  const choose = (id: string) => {
    if (suppress.current) { suppress.current = false; return }
    onSelect({ type: 'point', id })
    if (!['select', 'point'].includes(tool)) {
      if (chain.includes(id)) { setChain([]); return }
      const next = [...chain, id]
      const count = tool === 'angle' ? 3 : tool === 'coordinate' ? 1 : 2
      if (next.length === count) { onConnect(tool, next); setChain([]) } else setChain(next)
    }
  }
  const changeTool = (t: string) => { setTool(t); setChain([]) }
  const gridStep = 25 * camera.scale
  const origin = xy({ X: 0, Y: 0, Z: 0, H: 0, fixed: [] })
  const precisionMax = Math.max(...(solution?.point_precision.map(p => Number(p.major || p.mH || 0)) || []), 0.00001)
  return <div className="canvas-panel">
    <div className="canvas-heading"><div><span className="live-dot" /><strong>网形画布</strong><span className="muted">{project.family === 'GNSS网' ? 'XYZ 坐标 · XY 投影' : project.family === '水准网' ? '平面示意 · H 高程' : 'X 北 / Y 东'}</span></div><div><Button size="sm" variant="ghost" onClick={onTogglePrecision} disabled={!solution} className={showPrecision ? 'is-on' : ''}><CircleDot size={14} />精度图</Button><Button size="icon" variant="ghost" title="适应画布" aria-label="适应画布" onClick={fit}><LocateFixed size={16} /></Button></div></div>
    <div className={'network-canvas tool-'+tool} ref={ref} data-testid="network-canvas" onWheel={e => {
      const pos = local(e), before = world(pos.x, pos.y), s = Math.max(.15, Math.min(100, camera.scale * (e.deltaY < 0 ? 1.12 : 1/1.12)))
      setCamera({ x: before.x+(pos.y-size.h/2)/s, y: before.y-(pos.x-size.w/2)/s, scale: s })
    }}>
      <svg width="100%" height="100%" aria-label="交互控制网画布" onContextMenu={e => e.preventDefault()} onPointerDown={e => {
        const el = e.target as Element
        if (el.closest('[data-object]') || el.closest('[data-control]')) return
        const pos = local(e)
        if (tool === 'point' && e.button === 0) { const w = world(pos.x, pos.y); onAdd(w.x, w.y); return }
        drag.current = { px: e.clientX, py: e.clientY, cam: camera, moved: false }
        e.currentTarget.setPointerCapture(e.pointerId)
      }} onPointerMove={e => {
        const pos = local(e); setCursor(world(pos.x, pos.y))
        const d = drag.current
        if (!d) return
        const dx = e.clientX-d.px, dy = e.clientY-d.py
        if (Math.abs(dx)+Math.abs(dy) > 3) d.moved = true
        if (d.id && d.initial) setMoving({ id: d.id, point: { ...d.initial, X: d.initial.X-dy/d.cam.scale, Y: d.initial.Y+dx/d.cam.scale } })
        else setCamera({ ...d.cam, x: d.cam.x+dy/d.cam.scale, y: d.cam.y-dx/d.cam.scale })
      }} onPointerUp={e => {
        const d = drag.current
        if (d?.id && moving && d.moved) { onMove(d.id, moving.point); suppress.current = true }
        else if (!d?.id && !d?.moved) onSelect(null)
        setMoving(null); drag.current = null
        if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
      }} onPointerCancel={() => { setMoving(null); drag.current = null }}>
        <defs><pattern id="dots" width={gridStep} height={gridStep} patternUnits="userSpaceOnUse" x={origin.x % gridStep} y={origin.y % gridStep}><circle cx="1" cy="1" r="1" fill="#cbd5e1" /></pattern><filter id="label-bg"><feFlood floodColor="#fcfdff" floodOpacity=".93" /><feComposite in="SourceGraphic" operator="over" /></filter></defs>
        <rect width="100%" height="100%" fill="#fcfdff" /><rect width="100%" height="100%" fill="url(#dots)" />
        {project.observations.map((o, i) => {
          const p = o.points.map(id => points[id]).filter(Boolean).map(xy)
          if (p.length !== o.points.length) return null
          const selected = selection?.type === 'observation' && selection.id === o.id
          const color = o.kind === 'gnss' ? '#7c68c6' : o.kind === 'angle' || o.kind === 'azimuth' ? '#8b9ac2' : '#328f9c'
          const a = p[0], b = p[p.length-1], mid = { x: (a.x+b.x)/2, y: (a.y+b.y)/2 }
          const path = p.map(q => `${q.x},${q.y}`).join(' ')
          return <g key={o.id} data-object="observation" className="canvas-edge" opacity={o.enabled ? 1 : .3} role="button" aria-label={'选择观测 '+o.id} onClick={e => { e.stopPropagation(); onSelect({ type: 'observation', id: o.id }) }}>
            {p.length > 1 ? <><polyline points={path} fill="none" stroke="transparent" strokeWidth="14" /><polyline points={path} fill="none" stroke={selected ? '#4f46e5' : color} strokeWidth={selected ? 2.7 : 1.65} strokeDasharray={o.kind === 'angle' ? '5 4' : undefined} /></> : <circle cx={a.x} cy={a.y} r="22" fill="none" stroke={color} strokeDasharray="4 3" />}
            <text x={mid.x+ (p.length === 1 ? 28 : 0)} y={mid.y-9-(i % 2)*4} textAnchor="middle" className={'edge-label '+(selected ? 'selected' : '')} filter="url(#label-bg)">{o.id} · {o.kind === 'height' ? 'ΔH' : o.kind === 'gnss' ? 'ΔXYZ' : o.kind === 'distance' ? 'S' : names[o.kind]}</text>
          </g>
        })}
        {chain.map((id, i) => { const p = xy(points[id]); return <g key={id} pointerEvents="none"><circle cx={p.x} cy={p.y} r="21" fill="#eef2ff" stroke="#6366f1" strokeDasharray="3 2" /><text x={p.x} y={p.y-27} textAnchor="middle" className="chain-label">{i+1}</text></g> })}
        {showPrecision && solution?.point_precision.map(item => {
          const p = points[item.point]; if (!p) return null; const at = xy(p)
          if (project.family === '水准网') { const h = Number(item.mH)/precisionMax*42; return h > 0 ? <g key={item.point} className="precision-mark" pointerEvents="none"><path d={`M${at.x+20},${at.y-h} v${2*h} m-5,0 h10 m-5,${-2*h} h-5 h10`} /></g> : null }
          return Number(item.major) > 0 ? <ellipse key={item.point} className="precision-mark" pointerEvents="none" cx={at.x} cy={at.y} rx={Number(item.major)/precisionMax*42} ry={Number(item.minor)/precisionMax*42} transform={`rotate(${Number(item.azimuth)-90} ${at.x} ${at.y})`} /> : null
        })}
        {Object.entries(points).map(([id, p]) => {
          const at = xy(p), fixed = p.fixed.length > 0, selected = selection?.type === 'point' && selection.id === id
          return <g key={id} data-object="point" data-point={id} transform={`translate(${at.x} ${at.y})`} className="canvas-point" role="button" aria-label={'选择点 '+id} onClick={e => { e.stopPropagation(); choose(id) }} onPointerDown={e => {
            if (tool !== 'select' || e.button !== 0) return
            e.stopPropagation(); onSelect({ type: 'point', id }); suppress.current = false
            drag.current = { id, px: e.clientX, py: e.clientY, cam: camera, initial: p, moved: false }
            e.currentTarget.ownerSVGElement!.setPointerCapture(e.pointerId)
          }}>
            <circle r={selected ? 19 : 14} fill={selected ? '#e4e7ff' : '#fcfdff'} stroke={selected ? '#c7d2fe' : 'none'} />
            {fixed ? <path d="M0 -7 L7 6 L-7 6 Z" fill="#475569" stroke="#fff" strokeWidth="1.5" /> : <><circle r="6" fill="white" stroke={selected ? '#4f46e5' : '#328f9c'} strokeWidth="2.2" /><circle r="1.5" fill={selected ? '#4f46e5' : '#328f9c'} /></>}
            <text x="0" y="-23" textAnchor="middle" className="point-label">{id}</text>
            {project.family === '水准网' && <text x="0" y="31" textAnchor="middle" className="point-value">H {p.H.toFixed(3)}</text>}
          </g>
        })}
        {!Object.keys(points).length && <text x="50%" y="50%" textAnchor="middle" className="canvas-placeholder">选择左侧 ＋ 工具，点击画布开始布点</text>}
      </svg>
      <div className="canvas-tools" data-control="true"><Button variant="ghost" size="icon" aria-label="选择工具" title="选择 / 移动" className={tool === 'select' ? 'active' : ''} onClick={() => changeTool('select')}><MousePointer2 size={17} /></Button><Button variant="ghost" size="icon" aria-label="添加控制点" title="添加控制点" className={tool === 'point' ? 'active' : ''} onClick={() => changeTool('point')}><Plus size={19} /></Button><span className="tool-separator" />{kinds(project.family).map(k => <Button key={k} variant="ghost" size="icon" aria-label={'绘制'+names[k]} title={names[k]} className={tool === k ? 'active' : ''} onClick={() => changeTool(k)}>{k === 'angle' ? <Triangle size={17} /> : k === 'azimuth' ? <ArrowUpRight size={18} /> : k === 'coordinate' ? <Crosshair size={18} /> : k === 'distance' ? <Ruler size={17} /> : <Link2 size={17} />}</Button>)}</div>
      <div className="canvas-compass"><span>X / N</span><ArrowUpRight size={27} style={{ transform: 'rotate(-45deg)' }} /><small>Y / E →</small></div>
      <div className="canvas-legend"><span><i className="legend-fixed" />已知点</span><span><i className="legend-point" />待定点</span>{showPrecision && <span className="precision-note">1σ {project.family === '水准网' ? '高程误差棒' : '误差椭圆'} · 放大显示</span>}</div>
      <div className="canvas-zoom"><Button size="icon" variant="ghost" aria-label="缩小" onClick={() => setCamera(c => ({ ...c, scale: Math.max(.15, c.scale/1.2) }))}><ZoomOut size={15} /></Button><span>{Math.round(camera.scale/2.2*100)}%</span><Button size="icon" variant="ghost" aria-label="放大" onClick={() => setCamera(c => ({ ...c, scale: Math.min(100, c.scale*1.2) }))}><ZoomIn size={15} /></Button></div>
    </div>
    <div className="canvas-status"><span><Hand size={12} />{hints[tool]}{chain.length ? `（已选 ${chain.join(' → ')}）` : ''}</span><span className="mono">{cursor ? `X ${cursor.x.toFixed(1)}  Y ${cursor.y.toFixed(1)} m` : '坐标单位 m'}</span></div>
  </div>
}
