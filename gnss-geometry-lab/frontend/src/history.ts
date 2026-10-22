import {useRef,useState} from 'react'
import type {Project} from './model'
import {copy} from './model'
export function useProjectHistory(initial:()=>Project) {
  const [project,render]=useState(initial),ref=useRef(project),past=useRef<Project[]>([]),future=useRef<Project[]>([]),transaction=useRef<Project|null>(null)
  const [,revision]=useState(0)
  const setProject=(update:Project|((p:Project)=>Project))=>{
    const before=ref.current,next=typeof update==='function'?update(before):update
    if(JSON.stringify(before)===JSON.stringify(next))return
    if(!transaction.current){past.current=[...past.current.slice(-39),before];future.current=[]}
    ref.current=next;render(next);revision(v=>v+1)
  }
  const begin=()=>{if(!transaction.current)transaction.current=copy(ref.current)}
  const end=()=>{
    const origin=transaction.current;transaction.current=null
    if(origin&&JSON.stringify(origin)!==JSON.stringify(ref.current)){past.current=[...past.current.slice(-39),origin];future.current=[];revision(v=>v+1)}
  }
  const undo=()=>{end();const p=past.current.pop();if(!p)return;future.current.push(ref.current);ref.current=p;render(p);revision(v=>v+1)}
  const redo=()=>{end();const p=future.current.pop();if(!p)return;past.current.push(ref.current);ref.current=p;render(p);revision(v=>v+1)}
  return {project,setProject,begin,end,undo,redo,canUndo:past.current.length>0,canRedo:future.current.length>0}
}
