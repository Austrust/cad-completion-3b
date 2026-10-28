"""Download the exact accepted official ModelScope Qwen base; verify each file."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
REVISION='ac059254f4aa58c1078b15635a33f6de9b96f0fa'
BASE=f'https://modelscope.cn/models/Qwen/Qwen2.5-Coder-3B/resolve/{REVISION}/'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');p.add_argument('--destination',type=Path,default=Path(__file__).resolve().parents[1]/'v1/models/Qwen2.5-Coder-3B');a=p.parse_args()
    manifest=json.loads(Path(__file__).with_name('v1-base-files.json').read_text(encoding='utf-8'));a.destination.mkdir(parents=True,exist_ok=True)
    for name,meta in manifest['files'].items():
        if Path(name).name!=name:raise ValueError('Unsafe manifest path')
        target=a.destination/name
        if target.exists():
            if target.stat().st_size!=meta['bytes'] or digest(target)!=meta['sha256']:raise ValueError('Existing file mismatch: '+name)
            print('VERIFIED',name,flush=True);continue
        if a.verify_only:raise FileNotFoundError(target)
        part=target.with_name(target.name+'.partial');offset=part.stat().st_size if part.exists() else 0
        if offset>meta['bytes']:raise ValueError('Partial file too large: '+name)
        if offset<meta['bytes']:
            req=urllib.request.Request(BASE+name,headers={'Range':f'bytes={offset}-'} if offset else {})
            with urllib.request.urlopen(req,timeout=120) as r:
                if offset and r.status!=206:raise ValueError('Server did not honor resume; preserve partial and retry separately')
                with part.open('ab' if offset else 'wb') as f:
                    while b:=r.read(8*1024*1024):f.write(b)
        if part.stat().st_size!=meta['bytes'] or digest(part)!=meta['sha256']:raise ValueError('Download checksum mismatch: '+name)
        part.replace(target);print('VERIFIED',name,flush=True)
if __name__=='__main__':main()
