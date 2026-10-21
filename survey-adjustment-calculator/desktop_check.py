"""Smoke-test the actual React window, Python bridge and native file export."""
import json
import time
import zipfile


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
        template_path = output.with_suffix('.template.xlsx')
        window.create_file_dialog = lambda *args, **kwargs: [str(template_path if kwargs.get('save_filename', '').endswith('.xlsx') else exported)]
        window.evaluate_js("window.__exportCheck=null; window.pywebview.api.save_file(JSON.stringify(window.__surveyWorkspace.project), 'test.net.json').then(r=>window.__exportCheck=r)")
        for _ in range(100):
            if window.evaluate_js('window.__exportCheck !== null'): break
            time.sleep(.1)
        result['native_export'] = exported.is_file() and json.loads(exported.read_text(encoding='utf-8'))['format'] == 'survey-network-project'
        window.evaluate_js("window.__xlsxCheck=null; window.pywebview.api.rpc('import_template',{family:'水准网'}).then(r=>window.pywebview.api.save_file(r.data.content_base64,r.data.filename,'base64').then(()=>window.pywebview.api.rpc('import_read',r.data))).then(r=>window.__xlsxCheck=r)")
        for _ in range(100):
            if window.evaluate_js('window.__xlsxCheck !== null'): break
            time.sleep(.1)
        result['native_xlsx_roundtrip'] = template_path.is_file() and zipfile.is_zipfile(template_path) and window.evaluate_js('window.__xlsxCheck.ok && window.__xlsxCheck.data.tables.length === 3')
        window.evaluate_js("Array.from(document.querySelectorAll('[role=tab]')).find(b=>b.textContent==='计算步骤').click()")
        for _ in range(100):
            if window.evaluate_js("document.querySelectorAll('.steps-navigation button').length === 7"): break
            time.sleep(.1)
        result['calculation_steps'] = window.evaluate_js("document.querySelectorAll('.steps-navigation button').length === 7")
        result['ok'] = result['native_bridge'] and result['no_horizontal_overflow'] and result['precision_rows'] == 4 and result['native_export'] and result['native_xlsx_roundtrip'] and result['calculation_steps']
    except Exception as exc:
        result.update(ok=False, error=repr(exc))
    finally:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        window.destroy()
