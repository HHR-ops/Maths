"""Offline WebView2 desktop host. All geometry calculations run in the client."""
from __future__ import annotations
import argparse
import base64
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
MAX_DOCUMENT = 1024 * 1024

def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)

def validate_scene(value):
    if not isinstance(value, dict): raise ValueError('场景格式无效。')
    def number(n, lo, hi):
        return isinstance(n, (float, int)) and not isinstance(n, bool) and math.isfinite(n) and lo <= n <= hi
    if not isinstance(value.get('name'), str) or len(value['name']) > 80: raise ValueError('场景名称无效。')
    if not number(value.get('mask'), 0, 85) or not number(value.get('sigma'), .01, 100) or value.get('confidence') not in ('standard', '95'): raise ValueError('计算参数无效。')
    satellites = value.get('satellites')
    if not isinstance(satellites, list) or len(satellites) > 64: raise ValueError('卫星列表无效。')
    ids = set()
    clean = []
    for s in satellites:
        if not isinstance(s, dict) or not isinstance(s.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,16}', s['id']) or s['id'] in ids: raise ValueError('卫星编号无效。')
        if not number(s.get('azimuth'), 0, 360) or not number(s.get('elevation'), 0, 90) or not isinstance(s.get('enabled'), bool): raise ValueError('卫星角度或状态无效。')
        ids.add(s['id']); clean.append({k:s[k] for k in ('id', 'azimuth', 'elevation', 'enabled')})
    o = value.get('obstruction')
    if not isinstance(o, dict) or not isinstance(o.get('enabled'), bool) or not all(number(o.get(k), 0, limit) for k, limit in [('start',360),('width',360),('height',90)]): raise ValueError('遮挡参数无效。')
    return {'name':value['name'], 'satellites':clean, 'mask':value['mask'], 'sigma':value['sigma'], 'confidence':value['confidence'], 'obstruction':{k:o[k] for k in ('enabled','start','width','height')}}

def validate_project(doc):
    if not isinstance(doc, dict) or doc.get('format') != 'gnss-geometry-lab' or type(doc.get('version')) is not int or doc['version'] != 1: raise ValueError('项目格式无效。')
    snapshots = doc.get('snapshots')
    if not isinstance(snapshots, list) or len(snapshots) > 4: raise ValueError('对照场景无效。')
    scene = validate_scene(doc.get('scene')); clean = []; ids = set()
    for s in snapshots:
        if not isinstance(s, dict) or not isinstance(s.get('id'), str) or len(s['id']) > 80 or s['id'] in ids: raise ValueError('对照编号无效。')
        ids.add(s['id']); clean.append({'id':s['id'], 'scene':validate_scene(s.get('scene'))})
    return {'format':'gnss-geometry-lab', 'version':1, 'scene':scene, 'snapshots':clean}

class Api:
    def __init__(self, storage=None):
        self._window = None
        self._storage = storage
        self._lock = threading.Lock()
        self._sequence = -1
    def load(self):
        if self._storage is None: return None
        path = self._storage/'workspace.json'
        try:
            if path.stat().st_size <= MAX_DOCUMENT: return validate_project(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError, TypeError): pass
        return None
    def store(self, payload):
        if not isinstance(payload, dict) or type(payload.get('sequence')) is not int: raise ValueError('保存请求无效。')
        project = validate_project(payload.get('project'))
        if self._storage is None: return
        with self._lock:
            if payload['sequence'] <= self._sequence: return
            self._storage.mkdir(parents=True, exist_ok=True)
            temporary = self._storage/'workspace.tmp'
            temporary.write_text(dumps(project), encoding='utf-8')
            temporary.replace(self._storage/'workspace.json')
            self._sequence = payload['sequence']
    def save_file(self, content, filename, encoding='utf-8'):
        try:
            if not self._window or not isinstance(content, str) or len(content) > 32*1024*1024: raise ValueError('导出内容无效。')
            if encoding not in ('utf-8','base64') or not isinstance(filename,str): raise ValueError('导出格式无效。')
            import webview
            filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)[-120:]
            chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename)
            if not chosen: return {'ok':True, 'cancelled':True}
            target = Path(chosen[0] if isinstance(chosen,(list,tuple)) else chosen)
            if encoding == 'base64': target.write_bytes(base64.b64decode(content, validate=True))
            else: target.write_text(('\ufeff' if filename.endswith('.csv') else '')+content, encoding='utf-8')
            return {'ok':True}
        except (OSError, ValueError, TypeError):
            return {'ok':False, 'error':'文件未能保存，请检查路径与导出内容。'}

class NativeBridge:
    def __init__(self, api): self._api = api
    def save_file(self, content, filename, encoding='utf-8'):
        return self._api.save_file(content, filename, encoding)

def start_server(api, port=0, assets=None):
    token = secrets.token_urlsafe(32)
    assets = Path(assets) if assets else ROOT/'frontend/web-dist'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def reply(self, code, content, mime='application/json; charset=utf-8'):
            self.send_response(code)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers();self.wfile.write(content)
        def do_GET(self):
            if not self.valid_host(): self.reply(403,b'{}');return
            path = urlsplit(self.path).path
            if path in ('/','/index.html'):
                try:
                    html = (assets/'index.html').read_text(encoding='utf-8')
                    boot = 'window.__GNSS_TOKEN__='+dumps(token)+';window.__GNSS_PROJECT__='+dumps(api.load()).replace('<',r'\u003c')+';'
                    html = html.replace('<head>','<head><script>'+boot+'</script>',1)
                    self.reply(200,html.encode('utf-8'),'text/html; charset=utf-8')
                except OSError: self.reply(503,b'Build the frontend first.','text/plain')
                return
            target = (assets/path.lstrip('/')).resolve()
            if not target.is_relative_to(assets.resolve()) or not target.is_file(): self.reply(404,b'{}');return
            self.reply(200,target.read_bytes(),mimetypes.guess_type(target)[0] or 'application/octet-stream')
        def do_POST(self):
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.path != '/api/workspace' or not secrets.compare_digest(self.headers.get('X-GNSS-Token',''),token) or self.headers.get('Origin',expected) != expected:
                self.reply(403,b'{"ok":false}');return
            try:
                size = int(self.headers.get('Content-Length',0))
                if not 0 < size <= MAX_DOCUMENT: raise ValueError('size')
                payload = json.loads(self.rfile.read(size))
                api.store(payload)
                self.reply(200,b'{"ok":true}')
            except (ValueError,TypeError,KeyError,OSError):
                self.reply(400,b'{"ok":false}')
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server, f'http://127.0.0.1:{server.server_port}'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true');parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--ui-self-test',metavar='OUTPUT')
    args=parser.parse_args()
    storage=Path(os.environ.get('GNSS_LAB_DATA_DIR',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'GnssGeometryLab')))
    api=Api(None if args.serve or args.ui_self_test else storage)
    server,url=start_server(api,args.port)
    try:
        if args.serve:
            print(url,flush=True);threading.Event().wait()
        else:
            import webview
            webview.settings['ALLOW_DOWNLOADS'] = False
            api._window=webview.create_window('GNSS 交互实验室 v0.2.0',url,js_api=NativeBridge(api),width=1440,height=960,min_size=(1060,740),background_color='#0b0b0d')
            if args.ui_self_test:
                from desktop_check import run_check
                webview.start(run_check,(api._window,Path(args.ui_self_test)),gui='edgechromium')
            else:webview.start(gui='edgechromium')
    finally: server.shutdown()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if not getattr(sys,'frozen',False):raise
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'启动失败。请确认已安装 Microsoft Edge WebView2 Runtime。\n\n'+str(exc),'GNSS 交互实验室',0x10)
