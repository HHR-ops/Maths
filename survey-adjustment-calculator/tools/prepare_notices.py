"""Collect the licenses shipped by runtime dependencies; no network access."""
import importlib.metadata as metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIT = '''Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
parts = ['# Third-party notices\n\nUI layout reference and adapted button variant pattern:\n'
         '- https://github.com/satnaing/shadcn-admin\n- https://github.com/shadcn-ui/ui\n\n'
         'Only the workspace layout and component patterns are referenced; survey workflows and canvas are implemented locally.\n']
for name, copyright in [('shadcn-admin', 'Copyright (c) 2024 Sat Naing'), ('shadcn/ui', 'Copyright (c) 2023 shadcn')]:
    parts.append(f'## {name}\n\nMIT License\n\n{copyright}\n\n{MIT}\n')

lock = json.loads((ROOT/'frontend/package-lock.json').read_text(encoding='utf-8'))
manifest = json.loads((ROOT/'frontend/package.json').read_text(encoding='utf-8'))
for section in ('dependencies', 'devDependencies'):
    for name in manifest[section]:
        manifest[section][name] = lock['packages']['node_modules/'+name]['version']
    lock['packages'][''][section] = manifest[section]
for filename, doc in [('package.json', manifest), ('package-lock.json', lock)]:
    (ROOT/'frontend'/filename).write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

for relative, info in lock['packages'].items():
    if not relative or info.get('dev'): continue
    folder = ROOT/'frontend'/relative
    licenses = [p for p in folder.iterdir() if p.is_file() and p.name.lower().startswith(('license', 'licence', 'copyright', 'notice'))]
    parts.append(f'## {relative.removeprefix("node_modules/")} {info["version"]}\n')
    for p in sorted(licenses): parts.append(p.read_text(encoding='utf-8', errors='replace')+'\n')

for name in ('pywebview', 'pythonnet', 'clr_loader', 'proxy_tools', 'bottle', 'numpy', 'cffi', 'pycparser', 'typing_extensions', 'pyinstaller'):
    dist = metadata.distribution(name)
    parts.append(f'## Python dependency: {name} {dist.version}\n')
    for file in dist.files or []:
        if 'dist-info' in str(file) and Path(file).name.lower().startswith(('license', 'licence', 'copying', 'notice')):
            path = Path(dist.locate_file(file))
            if path.is_file(): parts.append(path.read_text(encoding='utf-8', errors='replace')+'\n')
    if name == 'pyinstaller': parts.append('The PyInstaller bootloader exception permits distribution of bundled applications under the application license. See the license above.\n')
parts.append('## WebView2 Runtime\n\nThe Microsoft Edge WebView2 Runtime is a separately installed Windows component.\nhttps://developer.microsoft.com/microsoft-edge/webview2/\n')
(ROOT/'THIRD_PARTY_NOTICES.md').write_text('\n'.join(line.rstrip() for line in '\n'.join(parts).splitlines())+'\n', encoding='utf-8')
print('Pinned frontend versions and collected runtime notices.')
