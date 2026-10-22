"""Create and verify the portable ZIP and SHA-256 manifest."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    version=json.loads((ROOT/'frontend/package.json').read_text(encoding='utf-8'))['version']
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    exe=dist/('GNSS交互实验室-v'+version+'.exe')
    if not exe.is_file():raise FileNotFoundError('Build the EXE before packaging.')
    archive=dist/('GNSSGeometryLab-v'+version+'-Windows-x64.zip')
    temporary=dist/('GNSSGeometryLab-v'+version+'.tmp.zip')
    files=[ROOT/n for n in ['README.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md']]
    for source in files:shutil.copyfile(source,dist/source.name)
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(exe,exe.name)
        for p in files:z.write(p,p.name)
        for p in sorted((ROOT/'docs').rglob('*')):
            if p.is_file():z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(temporary) as z:
        assert z.testzip() is None
        assert hashlib.sha256(z.read(exe.name)).hexdigest()==sha(exe)
        assert z.read('LICENSE')==(ROOT/'LICENSE').read_bytes()
        assert 'docs/MODEL.md' in z.namelist()
    temporary.replace(archive)
    (dist/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in [exe,archive]),encoding='utf-8',newline='\n')
    print(json.dumps({'exe':str(exe),'exe_bytes':exe.stat().st_size,'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive)},ensure_ascii=False))
if __name__=='__main__':main()
