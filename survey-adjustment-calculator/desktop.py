"""React desktop host and a JSON-only boundary around the existing solver.

All calculation state belongs to each request. The loopback server serves only
the built UI and requires an unpredictable header token for every API request.
Native file exports always go through a user-chosen save dialog.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np

from adjustment import AdjustmentError, MODEL_NAMES, FORMULAS, make_report, parse_matrix, solve
from examples import EXAMPLES
from bulk_import import read_tables, preview_import, template
from calculation_steps import matrix_steps, network_steps
from diagnostics import diagnose, diagnostic_report
from network import (Network, FAMILIES, KINDS, ARCSEC, adjust_network,
                     automatic_matrices, example_network, linearize,
                     network_report, parse_constraints)

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
FIELDS = {'condition': ['A', 'w'], 'condition_parameters': ['A', 'B', 'w'],
          'indirect': ['B', 'l'], 'indirect_constraints': ['B', 'l', 'C', 'd']}


def _json(value):
    def convert(v):
        if isinstance(v, np.ndarray): return v.tolist()
        if isinstance(v, np.generic): return v.item()
        raise TypeError(type(v).__name__)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=convert)


def _matrix_solution(payload):
    model, data = payload['model'], payload['data']
    if model not in FIELDS: raise AdjustmentError('未知平差方法。')
    values = {key: parse_matrix(str(data.get(key, '')), key) for key in FIELDS[model]}
    weight = data.get('weight_mode', '等权 P = I')
    if weight != '等权 P = I':
        p = parse_matrix(str(data.get('P', '')), 'P')
        if weight == '对角权' and 1 not in p.shape:
            raise AdjustmentError('对角权请填写一行或一列正数。')
        if weight == '完整权阵' and p.shape[0] != p.shape[1]:
            raise AdjustmentError('完整权阵请填写 n×n 方阵。')
        if weight not in ('对角权', '完整权阵'): raise AdjustmentError('未知权阵类型。')
        values['P'] = p
    for key in ('observed', 'x0'):
        if str(data.get(key, '')).strip(): values[key] = parse_matrix(str(data[key]), key)
    precision = data.get('precision', '后验')
    if precision not in ('先验', '后验'): raise AdjustmentError('未知精度基准。')
    result = solve(model, **values, sigma0=data.get('sigma0', 1),
                   precision='prior' if precision == '先验' else 'posterior')
    out = result.to_dict()
    out['std_adjusted'] = result.std(result.q_adjusted)
    out['std_v'] = result.std(result.qvv)
    out['std_x'] = result.std(result.qxx)
    out['steps'] = matrix_steps(model, values, result)
    out['diagnostics'] = diagnose(result, sigma0=float(data.get('sigma0', 1)), alpha=payload.get('alpha', .05))
    out['report'] = make_report(result, str(data.get('title', '矩阵平差')))+'\n\n'+diagnostic_report(out['diagnostics'])
    return out


def dispatch(op, payload):
    if op == 'bootstrap':
        return {'families': FAMILIES, 'kinds': KINDS, 'methods': MODEL_NAMES,
                'formulas': FORMULAS, 'examples': EXAMPLES,
                'project': example_network('水准网').to_dict()}
    if op == 'import_read': return read_tables(payload['filename'], payload['content_base64'])
    if op == 'import_preview': return preview_import(payload['project'], payload['tables'], policy=payload.get('policy', 'append'), units=payload.get('units'))
    if op == 'import_template': return template(payload.get('family', '水准网'), payload.get('kind', 'xlsx'))
    if op == 'example':
        return example_network(payload.get('family', '水准网'), bool(payload.get('measured'))).to_dict()
    if op == 'validate':
        doc = payload['project']
        if doc.get('format') == 'survey-network-project': return Network.from_dict(doc).to_dict()
        if (doc.get('format') == 'survey-adjustment-project' and doc.get('version') == 1
                and doc.get('model') in FIELDS and isinstance(doc.get('data'), dict)):
            if any(not isinstance(v, str) for v in doc['data'].values()):
                raise AdjustmentError('矩阵项目字段须为文本。')
            return doc
        raise AdjustmentError('请选择 .net.json 控制网项目或 .sap.json 矩阵项目。')
    if op == 'matrix_solve': return _matrix_solution(payload)
    net = Network.from_dict(payload['project'])
    if op == 'constraints':
        net.constraints = parse_constraints(payload.get('text', ''))
        linearize(net)
        return net.to_dict()
    design = bool(payload.get('design', True))
    if op == 'analyze':
        m = linearize(net, design=design)
        missing = [o['id'] for o in net.observations if o['enabled'] and (o['value'] is None or (isinstance(o['value'], str) and not o['value'].strip()))]
        predicted = {}
        for obs_id, start, count in m.groups:
            values = m.predicted[start:start+count].copy()
            mask = m.angular[start:start+count]
            values[mask] = np.degrees(values[mask])
            predicted[obs_id] = values.tolist()
        matrices = automatic_matrices(m)
        if not design and missing:
            matrices = {key: value for key, value in matrices.items() if not key.startswith(('l ·', 'u =', 'w ·', 'w_c ·'))}
        return {'statistics': m.stats, 'matrices': matrices, 'missing_observations': [] if design else missing,
                'parameter_order': [p+'.'+a for p,a in m.keys],
                'observation_order': m.labels, 'predicted': predicted}
    if op == 'extract':
        m = linearize(net, design=design, require_values=True)
        if m.stats['defect']: raise AdjustmentError('请先确定控制网基准，再提取矩阵。')
        method = net.method
        if method == 'indirect' and len(m.C): method = 'indirect_constraints'
        matrices = automatic_matrices(m)
        def text(value):
            value = np.asarray(value)
            if value.ndim == 1: return '\n'.join(format(float(v), '.17g') for v in value)
            return '\n'.join(' '.join(format(float(v), '.17g') for v in row) for row in value)
        data = {'title': net.name+' · 自动提取', 'weight_mode': '完整权阵',
                'precision': '先验' if design or payload.get('precision') == 'prior' else '后验', 'sigma0': '1',
                'P': text(m.P), 'observed': text(m.L), 'x0': '', 'A': '', 'B': '', 'w': '', 'l': '', 'C': '', 'd': ''}
        if method == 'condition':
            A = matrices['A · 条件系数（零空间基）']
            if not len(A): raise AdjustmentError('当前没有多余观测，无法提取非空条件方程；请使用间接平差。')
            data.update(A=text(A), w=text(matrices['w · 条件闭合差']))
        elif method == 'condition_parameters':
            if not m.Z.shape[1]: raise AdjustmentError('当前没有自由参数，请使用不附参数的条件平差。')
            data.update(A=text(np.eye(len(m.L))), B=text(-m.B@m.Z), w=text(m.l-m.B@m.xp))
            if not len(m.C): data['x0'] = text([net.points[p][a] for p,a in m.keys])
        else:
            if not len(m.keys): raise AdjustmentError('当前坐标全部固定，请使用条件平差。')
            data.update(B=text(m.B), l=text(m.l), x0=text([net.points[p][a] for p,a in m.keys]))
            if method == 'indirect_constraints':
                if not len(m.C): raise AdjustmentError('请先添加精确限制条件，再提取附限间接平差模型。')
                data.update(C=text(m.C), d=text(m.d))
        data['note'] = '这是当前近似坐标处的一次线性化；非线性网的最终成果请在控制网工作台计算。角度方程与观测使用弧度。参数顺序：'+', '.join(p+'.'+a for p,a in m.keys)
        if method == 'condition_parameters' and len(m.C):
            data['note'] += '。已消去精确限制，当前参数为零空间坐标 z，原坐标改正数为 xp + Zz，不能直接将 z 当作各点坐标。'
        return {'format': 'survey-adjustment-project', 'version': 1, 'model': method, 'data': data}
    if op == 'solve':
        sol = adjust_network(net, design=design, precision=payload.get('precision', 'prior'))
        out = sol.to_dict()
        out['steps'] = network_steps(net, sol)
        out['diagnostics'] = diagnose(sol.result, labels=sol.model.labels, groups=sol.model.groups,
                                      angular=sol.model.angular, alpha=payload.get('alpha', .05), design=design)
        out['report'] = network_report(net, sol)+'\n\n'+diagnostic_report(out['diagnostics'])
        out['std_adjusted'] = sol.result.std(sol.result.q_adjusted)
        return out
    if op == 'compare_methods':
        results = []
        baseline = None
        for method, name in MODEL_NAMES.items():
            net.method = method
            sol = adjust_network(net, design=design, precision=payload.get('precision', 'prior'))
            if baseline is None: baseline = sol
            results.append({'method': method, 'name': name, 'weighted_sum': sol.result.weighted_sum,
                            'iterations': sol.iterations, 'max_coordinate_difference': float(np.max(np.abs(sol.corrections-baseline.corrections))) if sol.corrections.size else 0.,
                            'max_residual_difference': float(np.max(np.abs(sol.result.v-baseline.result.v))) if sol.result.v.size else 0.,
                            'max_cofactor_difference': float(np.max(np.abs(sol.result.qxx-baseline.result.qxx))) if sol.result.qxx.size else 0.,
                            'n': sol.model.stats['n'], 't': sol.model.stats['t'], 'r': sol.model.stats['r']})
        return {'results': results, 'baseline': MODEL_NAMES['condition'],
                'note': '对同一观测模型、权和精确限制进行等价转换。比较坐标总改正数、残差和参数协因数；条件法的坐标通过自由参数恢复。无自由参数的附参模型按等价退化模型处理。'}
    raise AdjustmentError('未知操作。')


class Api:
    def __init__(self, storage_dir=None):
        self._window = None
        self._storage_dir = Path(storage_dir) if storage_dir else None
        self._save_lock = threading.Lock()
        self._save_sequence = -1

    def rpc(self, op, payload=None):
        try:
            if op == 'load_workspace':
                doc = None
                if self._storage_dir and (self._storage_dir/'workspace.json').is_file():
                    try:
                        doc = json.loads((self._storage_dir/'workspace.json').read_text(encoding='utf-8'))
                    except (OSError, ValueError): pass
                return {'ok': True, 'data': doc}
            if op == 'save_workspace':
                if self._storage_dir:
                    doc = payload['workspace']
                    Network.from_dict(doc['project'])
                    encoded = _json(doc)
                    if len(encoded.encode('utf-8')) > 16*1024*1024:
                        raise AdjustmentError('本地草稿过大，请通过保存项目保留。')
                    with self._save_lock:
                        if payload['sequence'] > self._save_sequence:
                            self._storage_dir.mkdir(parents=True, exist_ok=True)
                            temporary = self._storage_dir/'workspace.tmp'
                            temporary.write_text(encoded, encoding='utf-8')
                            temporary.replace(self._storage_dir/'workspace.json')
                            self._save_sequence = payload['sequence']
                return {'ok': True, 'data': None}
            result = dispatch(op, payload or {})
            # The same strict JSON conversion is used by both transports.
            return json.loads(_json({'ok': True, 'data': result}))
        except (AdjustmentError, ValueError, TypeError, KeyError, np.linalg.LinAlgError) as exc:
            return {'ok': False, 'error': str(exc)}
        except Exception:
            return {'ok': False, 'error': '计算未完成，请检查输入数据和矩阵维数。'}

    def save_file(self, content, filename, encoding='text'):
        if not isinstance(content, str) or len(content.encode('utf-8')) > 32*1024*1024:
            return {'ok': False, 'error': '导出内容超过 32 MB。'}
        if not self._window: return {'ok': False, 'error': '桌面窗口尚未就绪。'}
        import webview
        filename = Path(str(filename)).name
        if not filename.endswith(('.json', '.txt', '.csv', '.xlsx')):
            return {'ok': False, 'error': '不支持的导出类型。'}
        if encoding not in ('text', 'base64') or (filename.endswith('.xlsx') and encoding != 'base64'):
            return {'ok': False, 'error': '不支持的文件编码。'}
        paths = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename)
        if not paths: return {'ok': True, 'cancelled': True}
        try:
            target = Path(paths if isinstance(paths, str) else paths[0])
            if encoding == 'base64': target.write_bytes(base64.b64decode(content, validate=True))
            else: target.write_text(content, encoding='utf-8-sig' if filename.endswith('.csv') else 'utf-8')
            return {'ok': True}
        except OSError as exc:
            return {'ok': False, 'error': f'无法保存文件：{exc}'}


def start_server(api, port=0):
    token = secrets.token_urlsafe(32)
    assets = ROOT / 'frontend' / 'web-dist'
    if not (assets/'index.html').is_file(): raise RuntimeError('请先在 frontend 中运行 npm run build。')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass

        def _local_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def _respond(self, status, data, content_type='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store' if content_type.startswith('text/html') else 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._local_host():
                self._respond(403, b'Forbidden', 'text/plain'); return
            path = urlsplit(self.path).path
            if path in ('/', '/index.html'):
                html = (assets/'index.html').read_text(encoding='utf-8')
                html = html.replace('<head>', '<head><script>window.__SURVEY_TOKEN__='+json.dumps(token)+';</script>', 1)
                self._respond(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                return
            target = (assets/path.lstrip('/')).resolve()
            if not target.is_relative_to(assets.resolve()) or not target.is_file():
                self._respond(404, b'Not found', 'text/plain'); return
            self._respond(200, target.read_bytes(), mimetypes.guess_type(target)[0] or 'application/octet-stream')

        def do_POST(self):
            if not self._local_host() or self.path != '/api' or not secrets.compare_digest(self.headers.get('X-Survey-Token', ''), token):
                self._respond(403, b'{"ok":false,"error":"Forbidden"}'); return
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Origin', expected) != expected:
                self._respond(403, b'{"ok":false,"error":"Origin"}'); return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 8*1024*1024: raise ValueError('请求大小无效。')
                doc = json.loads(self.rfile.read(size))
                result = api.rpc(doc['op'], doc.get('payload', {}))
                self._respond(200, _json(result).encode('utf-8'))
            except (ValueError, KeyError, TypeError):
                self._respond(400, b'{"ok":false,"error":"Invalid request"}')

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true', help='仅启动本地浏览器测试服务')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--self-test', metavar='OUTPUT')
    parser.add_argument('--ui-self-test', metavar='OUTPUT')
    args = parser.parse_args()
    storage = Path(os.environ.get('SURVEY_DATA_DIR', Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'SurveyAdjustmentWorkbench'))
    api = Api(None if args.serve or args.self_test or args.ui_self_test else storage)
    if args.self_test:
        checks = {}
        for family in FAMILIES:
            project = dispatch('example', {'family': family, 'measured': True})
            for method in MODEL_NAMES:
                project['method'] = method
                result = api.rpc('solve', {'project': project, 'design': False, 'precision': 'posterior'})
                checks[family+'/'+method] = result['ok']
        for model, data in EXAMPLES.items():
            checks[model] = api.rpc('matrix_solve', {'model': model, 'data': data})['ok']
        for family in FAMILIES:
            file = dispatch('import_template', {'family': family})
            tables = dispatch('import_read', file)['tables']
            preview = dispatch('import_preview', {'project': example_network(family).to_dict(), 'tables': tables, 'policy': 'replace'})
            checks['xlsx/'+family] = preview['ok']
        diagnostic_net = Network()
        diagnostic_net.add_point('A', H=100, fixed=['H']); diagnostic_net.add_point('B', H=100)
        for index in range(10): diagnostic_net.add_observation('height', ['A', 'B'], 1.010 if index == 9 else 1., sigma=.001)
        diagnostic = dispatch('solve', {'project': diagnostic_net.to_dict(), 'design': False})
        checks['diagnostics/known_blunder'] = diagnostic['diagnostics']['flagged_observations'] == ['O10']
        Path(args.self_test).write_text(_json({'ok': all(checks.values()), 'checks': checks}), encoding='utf-8')
        return
    server, url = start_server(api, args.port)
    try:
        if args.serve:
            print(url, flush=True)
            threading.Event().wait()
        else:
            import webview
            webview.settings['ALLOW_DOWNLOADS'] = False
            api._window = webview.create_window('测量平差工作台 v0.5 · React', url, js_api=api,
                                               width=1440, height=960, min_size=(1060, 740),
                                               background_color='#f8fafc')
            if args.ui_self_test:
                from desktop_check import run_check
                webview.start(run_check, (api._window, Path(args.ui_self_test)), gui='edgechromium')
            else:
                webview.start(gui='edgechromium')
    finally:
        server.shutdown()


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        if not getattr(sys, 'frozen', False): raise
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, '无法启动测量平差工作台。\n\n'+str(exc)+'\n\n请确认已安装 Microsoft Edge WebView2 Runtime。', '启动提示', 0x10)
