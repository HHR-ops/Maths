"""Collect licenses of installed runtime packages without network requests."""
from pathlib import Path
import importlib.metadata as metadata
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
parts=['# Third-party notices\n\nGNSS Geometry Lab original source: MIT, Copyright (c) 2026 HHR-ops.\nSee LICENSE. Runtime components keep their own licenses below.\n']
lock=json.loads((ROOT/'frontend/package-lock.json').read_text(encoding='utf-8'))
for relative,info in lock['packages'].items():
    if not relative or info.get('dev'):continue
    folder=ROOT/'frontend'/relative
    parts.append('## '+relative.removeprefix('node_modules/')+' '+info['version']+'\n')
    licenses=[p for p in folder.iterdir() if p.is_file() and p.name.lower().startswith(('license','licence','copyright','notice'))]
    if not licenses:raise RuntimeError('Missing runtime license: '+relative)
    for p in sorted(licenses):parts.append(p.read_text(encoding='utf-8',errors='replace')+'\n')
for name in ('pywebview','pythonnet','clr_loader','proxy_tools','bottle','cffi','pycparser','typing_extensions','pyinstaller'):
    dist=metadata.distribution(name);parts.append('## Python dependency: '+name+' '+dist.version+'\n')
    for file in dist.files or []:
        if 'dist-info' in str(file) and Path(file).name.lower().startswith(('license','licence','copying','notice')):
            path=Path(dist.locate_file(file))
            if path.is_file():parts.append(path.read_text(encoding='utf-8',errors='replace')+'\n')
    if name=='pyinstaller':parts.append('The PyInstaller bootloader exception permits bundled applications to be distributed under their own license.\n')
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if not python_license.is_file():raise RuntimeError('Python license not found')
parts.append('## Python runtime\n\n'+python_license.read_text(encoding='utf-8',errors='replace'))
parts.append('## Microsoft Edge WebView2 Runtime\n\nSeparately installed Windows component.\nhttps://developer.microsoft.com/microsoft-edge/webview2/\n')
(ROOT/'THIRD_PARTY_NOTICES.md').write_text('\n'.join(parts),encoding='utf-8')
print('Runtime licenses collected.')
