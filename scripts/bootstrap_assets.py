"""Fetch the separately licensed, checksum-pinned OPBP image release."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()

def validate_manifest(manifest, root):
    if manifest.get('schemaVersion') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported asset manifest')
    if manifest['fileCount'] != len(manifest['files']) or not manifest['files']:
        raise ValueError('Asset file count mismatch')
    base = (root/'static').resolve()
    for name, record in manifest['files'].items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or path.parts[0] != 'static' or len(path.parts) < 3:
            raise ValueError('Unsafe asset path')
        target = root/Path(*path.parts)
        if not target.resolve().is_relative_to(base) or target.is_symlink():
            raise ValueError('Asset points outside the static directory')
        if not isinstance(record.get('bytes'), int) or record['bytes'] < 1 or len(record.get('sha256', '')) != 64:
            raise ValueError('Invalid asset size or digest')
    if sum(record['bytes'] for record in manifest['files'].values()) != manifest['uncompressedBytes']:
        raise ValueError('Asset size total mismatch')

def assets_ready(manifest, root, verify=False):
    for name, record in manifest['files'].items():
        target = root/name
        if not target.is_file() or target.stat().st_size != record['bytes']:
            return False
        if verify and sha256(target) != record['sha256']:
            return False
    return True

def install_archive(archive, manifest, root):
    validate_manifest(manifest, root)
    archive = Path(archive)
    if archive.stat().st_size != manifest['bytes'] or sha256(archive) != manifest['sha256']:
        raise ValueError('资源 ZIP 校验失败；请重新下载。')
    root.joinpath('static').mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) != len(manifest['files']) or {entry.filename for entry in entries} != set(manifest['files']):
            raise ValueError('Unexpected or duplicate ZIP entry')
        # Validate ALL bytes before publishing any file. Zip-slip, symlinks and
        # archive bombs cannot use extractall() or escape into user directories.
        with tempfile.TemporaryDirectory(prefix='.assets-', dir=root/'static') as temporary:
            stage = Path(temporary)
            for entry in entries:
                record = manifest['files'][entry.filename]
                if stat.S_ISLNK(entry.external_attr >> 16) or entry.file_size != record['bytes']:
                    raise ValueError('Unsafe ZIP entry')
                with zipped.open(entry) as stream: data = stream.read(record['bytes']+1)
                if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
                    raise ValueError('Asset content digest mismatch')
                target = root/entry.filename
                if target.exists() and (not target.is_file() or sha256(target) != record['sha256']):
                    raise ValueError('已有图片被修改，安装器不会覆盖：'+entry.filename)
                staged = stage/entry.filename
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(data)
            for name in manifest['files']:
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                (stage/name).replace(target)

def download(manifest, destination):
    if not manifest['url'].startswith('https://github.com/Laura-LLU/OPBP-Bank/releases/download/'):
        raise ValueError('Unexpected resource download host')
    partial = destination.with_suffix('.part')
    for attempt in range(3):
        offset = partial.stat().st_size if partial.is_file() else 0
        headers = {'User-Agent':'OPBP-Bank-resource-installer/1'}
        if offset: headers['Range'] = 'bytes='+str(offset)+'-'
        try:
            with urlopen(Request(manifest['url'], headers=headers), timeout=45) as response:
                append = offset > 0 and response.status == 206
                if append and not response.headers.get('Content-Range', '').startswith('bytes '+str(offset)+'-'):
                    raise ValueError('Download resume range mismatch')
                written = offset if append else 0
                with partial.open('ab' if append else 'wb') as stream:
                    while chunk := response.read(1024*1024):
                        written += len(chunk)
                        if written > manifest['bytes']: raise ValueError('Download exceeds declared size')
                        stream.write(chunk)
            if partial.stat().st_size != manifest['bytes']:
                raise OSError('Incomplete resource response; retrying the remaining bytes')
            if sha256(partial) != manifest['sha256']:
                raise ValueError('Download checksum mismatch')
            partial.replace(destination)
            return
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            if attempt == 2: raise RuntimeError('资源下载失败：'+str(exc)+'。可从 GitHub Release 手动下载后使用 --archive；Mac 证书错误见部署指南。') from exc
            time.sleep(1 << attempt)

def ensure_assets(root=ROOT, archive=None, verify=False):
    root = Path(root).resolve()
    manifest = json.loads((root/'data/asset-manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest, root)
    if assets_ready(manifest, root, verify):
        return {'ok':True, 'files':manifest['fileCount'], 'downloaded':False, 'verified':verify}
    if archive:
        install_archive(archive, manifest, root)
    else:
        cache = root/'.asset-cache'
        cache.mkdir(exist_ok=True)
        destination = cache/manifest['archiveName']
        print('首次安装下载题图资源（约 '+str(round(manifest['bytes']/1024**2))+' MB）；不含学生数据。',flush=True)
        if not destination.is_file() or destination.stat().st_size != manifest['bytes'] or sha256(destination) != manifest['sha256']:
            download(manifest, destination)
        install_archive(destination, manifest, root)
    if not assets_ready(manifest, root, verify=True): raise ValueError('资源安装后校验失败。')
    return {'ok':True, 'files':manifest['fileCount'], 'downloaded':archive is None, 'verified':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Install a manually downloaded GitHub Release ZIP')
    parser.add_argument('--verify',action='store_true',help='Verify every installed image checksum')
    args=parser.parse_args()
    try: print(json.dumps(ensure_assets(archive=args.archive,verify=args.verify),ensure_ascii=False))
    except (ValueError,RuntimeError,OSError,zipfile.BadZipFile) as exc:
        parser.exit(1,str(exc)+'\n')

if __name__=='__main__': main()
