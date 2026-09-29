#!/usr/bin/env python3
"""Build reproducible, tracked-file-only distribution archives."""
import argparse
import gzip
import hashlib
import io
import re
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(out):
    if subprocess.check_output(['git','status','--porcelain'], cwd=ROOT).strip():
        raise ValueError('Commit the checked candidate before packaging')
    files = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    name = 'orchestra-1.0.0'
    paths = []
    for relative in filter(None, files):
        path = ROOT / relative
        if path.is_symlink():
            raise ValueError(f'Distribution symlinks are unsupported: {relative}')
        data = path.read_bytes()
        if re.search(rb'/Users/[^/\s]+/|gh[op]_[A-Za-z0-9]{20,}|sk-ant-api[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----', data):
            raise ValueError(f'Private content candidate: {relative}')
        paths.append((relative,data))
    tar_path = out / (name + '.tar.gz')
    with tar_path.open('wb') as stream, gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for relative,data in paths:
                info = tarfile.TarInfo(name + '/' + relative)
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info,io.BytesIO(data))
    zip_path = out / (name + '.zip')
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for relative,data in paths:
            info = zipfile.ZipInfo(name + '/' + relative, date_time=(1980,1,1,0,0,0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    sums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in [tar_path,zip_path])+'\n'
    (out/'SHA256SUMS').write_text(sums)
    return sums


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',default=str(ROOT/'dist'))
    print(build(parser.parse_args().out),end='')
