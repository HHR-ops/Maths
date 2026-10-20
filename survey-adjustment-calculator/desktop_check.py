"""Smoke-test the actual React window, Python bridge and native file export."""
import json
import time


def run_check(window, output):
    result = {}
    exported = output.with_suffix('.export.json')
    try:
        for _ in range(200):
            if window.evaluate_js("document.querySelector('[data-testid=stat-n]')?.textContent === '5'"): break
            time.sleep(.1)
        else: raise RuntimeError('React window did not become ready')
        result['native_bridge'] = window.evaluate_js("typeof window.pywebview.api.save_file === 'function'")
        result['no_horizontal_overflow'] = window.evaluate_js('document.documentElement.scrollWidth <= innerWidth')
        window.evaluate_js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='计算精度').click()")
        for _ in range(100):
            if window.evaluate_js("document.querySelector('.solution-summary')?.textContent.includes('设计精度已计算') || false"): break
            time.sleep(.1)
        else: raise RuntimeError('Calculation did not finish')
        result['precision_rows'] = window.evaluate_js("document.querySelectorAll('.data-panel tbody tr').length")
        # Choose a QA-owned path instead of interrupting verification with a dialog.
        window.create_file_dialog = lambda *args, **kwargs: [str(exported)]
        window.evaluate_js("window.__exportCheck=null; window.pywebview.api.save_file(JSON.stringify(window.__surveyWorkspace.project), 'test.net.json').then(r=>window.__exportCheck=r)")
        for _ in range(100):
            if window.evaluate_js('window.__exportCheck !== null'): break
            time.sleep(.1)
        result['native_export'] = exported.is_file() and json.loads(exported.read_text(encoding='utf-8'))['format'] == 'survey-network-project'
        result['ok'] = result['native_bridge'] and result['no_horizontal_overflow'] and result['precision_rows'] == 4 and result['native_export']
    except Exception as exc:
        result.update(ok=False, error=repr(exc))
    finally:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        window.destroy()
