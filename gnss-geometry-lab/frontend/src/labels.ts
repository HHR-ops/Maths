export interface LabelAnchor { id:string;x:number;y:number;priority?:boolean }
export interface PlacedLabel { x:number;y:number;dx:number;dy:number }
export function layoutLabels(items:LabelAnchor[],width:number,height:number,boxWidth=36,boxHeight=18) {
  const boxes:{left:number;right:number;top:number;bottom:number}[]=[],out:Record<string,PlacedLabel>={}
  const offsets=[[0,-21],[24,-16],[-24,-16],[0,23],[32,7],[-32,7],[0,-39],[40,-31],[-40,-31],[0,40]]
  for(const item of [...items].sort((a,b)=>Number(Boolean(b.priority))-Number(Boolean(a.priority)))){
    let best:{x:number;y:number;dx:number;dy:number;score:number}|null=null
    for(const [dx,dy] of offsets){
      const x=Math.max(boxWidth/2+3,Math.min(width-boxWidth/2-3,item.x+dx)),y=Math.max(boxHeight/2+3,Math.min(height-boxHeight/2-3,item.y+dy))
      const box={left:x-boxWidth/2,right:x+boxWidth/2,top:y-boxHeight/2,bottom:y+boxHeight/2}
      const overlaps=boxes.reduce((n,b)=>n+(box.left<b.right&&box.right>b.left&&box.top<b.bottom&&box.bottom>b.top?1:0),0)
      const score=overlaps*10000+Math.hypot(x-item.x,y-item.y)
      if(!best||score<best.score)best={x,y,dx:x-item.x,dy:y-item.y,score}
      if(overlaps===0)break
    }
    if(best){out[item.id]=best;boxes.push({left:best.x-boxWidth/2,right:best.x+boxWidth/2,top:best.y-boxHeight/2,bottom:best.y+boxHeight/2})}
  }
  return out
}
