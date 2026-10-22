"""Verify the packaged native WebView2, JS geometry and native save bridge."""
import json
import time
def run_check(window, output):
    result={}
    def wait(js):
        for _ in range(160):
            if window.evaluate_js(js):return
            time.sleep(.1)
        raise RuntimeError('UI check timeout: '+js)
    def click(text):
        window.evaluate_js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes("+json.dumps(text)+")).click()")
    try:
        wait("Boolean(window.__gnssLab?.result.valid)")
        result['native_bridge']=window.evaluate_js("typeof window.pywebview.api.save_file === 'function'")
        result['webgl_canvas']=window.evaluate_js("Boolean(document.querySelector('.three-host>canvas'))")
        result['geometry_default']=window.evaluate_js("Math.abs(window.__gnssLab.result.dop.PDOP-1.8215215011714392)<1e-8")
        result['no_horizontal_overflow']=window.evaluate_js("document.documentElement.scrollWidth<=innerWidth")
        click('同仰角退化');wait("window.__gnssLab?.result.rank===3")
        result['rank_defect']=window.evaluate_js("window.__gnssLab.result.Q===null && document.querySelector('[data-testid=metric-PDOP]').textContent==='—'")
        click('最少四星');wait("window.__gnssLab?.result.used.length===4 && window.__gnssLab?.result.valid")
        result['four_satellites']=True
        click('均匀分布');wait("window.__gnssLab?.result.used.length===8")
        window.evaluate_js("window.__sigmaBefore=window.__gnssLab.result.dop.PDOP")
        window.evaluate_js("const el=document.querySelector('[aria-label=测距标准差]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'2');el.dispatchEvent(new Event('input',{bubbles:true}))")
        wait("window.__gnssLab.project.scene.sigma===2")
        result['sigma_preserves_dop']=window.evaluate_js("Math.abs(window.__gnssLab.result.dop.PDOP-window.__sigmaBefore)<1e-10")
        target=output.with_suffix('.gnss.json')
        window.create_file_dialog=lambda *a,**k:[str(target)]
        window.evaluate_js("window.__saveResult=null;window.pywebview.api.save_file(JSON.stringify(window.__gnssLab.project),'test.gnss.json','utf-8').then(r=>window.__saveResult=r)")
        wait("window.__saveResult!==null")
        result['native_export']=target.is_file() and json.loads(target.read_text(encoding='utf-8'))['format']=='gnss-geometry-lab'
        png=output.with_suffix('.png');window.create_file_dialog=lambda *a,**k:[str(png)]
        window.evaluate_js("window.__pngResult=null;window.pywebview.api.save_file(document.querySelector('.three-host>canvas').toDataURL('image/png').split(',')[1],'scene.png','base64').then(r=>window.__pngResult=r)")
        wait("window.__pngResult!==null")
        result['native_png']=png.is_file() and png.read_bytes().startswith(b'\x89PNG')
        result['black_gold_theme']=window.evaluate_js("getComputedStyle(document.documentElement).getPropertyValue('--gold').trim()==='#e1c27c'")
        click('噪声实验');click('运行噪声实验')
        wait("Boolean(document.querySelector('[data-testid=noise-results]'))")
        result['noise_experiment']=window.evaluate_js("document.querySelector('[data-testid=noise-results]').textContent.includes('2000 次')")
        window.evaluate_js("window.__editingScene=JSON.stringify(window.__gnssLab.project.scene)")
        click('动态轨迹')
        window.evaluate_js("const el=document.querySelector('[aria-label=轨迹实验进度]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'0.65');el.dispatchEvent(new Event('input',{bubbles:true}))")
        wait("JSON.stringify(window.__gnssLab.project.scene)!==window.__editingScene")
        click('采用当前帧')
        window.evaluate_js("document.querySelector('button[aria-label=撤销]').click()")
        wait("JSON.stringify(window.__gnssLab.project.scene)===window.__editingScene")
        result['trajectory_adopt_undo']=True
        click('SP3 历元');click('载入教学示例')
        wait("Boolean(document.querySelector('[data-testid=sp3-results]')) && window.__gnssLab.project.scene.satellites[0]?.id==='G01'")
        result['sp3_example']=window.evaluate_js("document.querySelector('[data-testid=sp3-results]').textContent.includes('WGS84') && window.__gnssLab.result.used.length===8")
        result['ok']=all(result.values())
    except Exception as exc:result.update(ok=False,error=repr(exc))
    finally:
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        window.destroy()
