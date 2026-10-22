"""Independent NumPy reference for the browser's SVD/ENU implementation.
Requires NumPy only for development; the desktop program does not import it.
"""
from pathlib import Path
import json
import numpy as np

def main():
    rng=np.random.default_rng(20261022)
    cases=[]
    for i in range(40):
        count=int(rng.integers(4,24))
        az=rng.uniform(0,360,count);el=rng.uniform(5,85,count)
        a=np.radians(az);e=np.radians(el)
        g=np.column_stack((-np.cos(e)*np.sin(a),-np.cos(e)*np.cos(a),-np.sin(e),np.ones(count)))
        # Reference uses direct normal equations, independently of the JS SVD.
        q=np.linalg.inv(g.T@g)
        sigma=float(rng.uniform(.1,4))
        cov=q[:3,:3]*sigma**2
        eig,vectors=np.linalg.eigh(cov[:2,:2])
        vector=vectors[:,-1]
        azimuth=float(np.degrees(np.arctan2(vector[0],vector[1]))%180)
        scene={'name':'reference-'+str(i),'satellites':[{'id':'S'+str(j),'azimuth':float(az[j]),'elevation':float(el[j]),'enabled':True} for j in range(count)],'mask':0,'sigma':sigma,'confidence':'standard','obstruction':{'enabled':False,'start':0,'width':0,'height':0}}
        cases.append({'scene':scene,'Q':q.tolist(),'ellipse':{'major':float(np.sqrt(eig[1])),'minor':float(np.sqrt(eig[0])),'azimuth':azimuth},'axes':np.sqrt(np.linalg.eigvalsh(cov))[::-1].tolist()})
    target=Path(__file__).resolve().parents[1]/'frontend/tests/reference.json'
    target.write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('Generated 40 independent NumPy reference cases.')
if __name__=='__main__':main()
