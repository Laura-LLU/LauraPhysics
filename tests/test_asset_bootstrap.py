"""Resource installation failures must not corrupt or escape the public tree."""
import hashlib, json, stat, zipfile
from pathlib import Path
import pytest
from scripts import bootstrap_assets as assets

def fixture(tmp_path, records=None):
 root=tmp_path/'project';(root/'static').mkdir(parents=True);(root/'data').mkdir()
 records=records or {'static/bank/a.png':b'anonymous image fixture','static/paper/b.png':b'other fixture'}
 archive=tmp_path/'assets.zip'
 with zipfile.ZipFile(archive,'w') as zipped:
  for name,data in records.items():zipped.writestr(name,data)
 manifest={'schemaVersion':1,'version':'test','fileCount':len(records),'bytes':archive.stat().st_size,
  'sha256':assets.sha256(archive),'uncompressedBytes':sum(len(v) for v in records.values()),
  'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in records.items()}}
 return root,archive,manifest

def test_offline_asset_archive_is_checksum_verified_and_installed(tmp_path):
 root,archive,manifest=fixture(tmp_path);assets.install_archive(archive,manifest,root)
 assert assets.assets_ready(manifest,root,verify=True)
 assert (root/'static/bank/a.png').read_bytes()==b'anonymous image fixture'

def test_corrupt_archive_does_not_write_any_asset(tmp_path):
 root,archive,manifest=fixture(tmp_path);archive.write_bytes(archive.read_bytes()+b'corrupt')
 with pytest.raises(ValueError,match='校验失败'):assets.install_archive(archive,manifest,root)
 assert not (root/'static/bank/a.png').exists()

@pytest.mark.parametrize('name',['../outside.png','static/../../outside.png','/static/bank/a.png','static\\bank\\a.png'])
def test_manifest_rejects_path_escape(tmp_path,name):
 root,archive,manifest=fixture(tmp_path,{name:b'fixture'})
 with pytest.raises(ValueError,match='Unsafe'):assets.install_archive(archive,manifest,root)

def test_zip_symlink_is_rejected_before_any_write(tmp_path):
 root,archive,manifest=fixture(tmp_path,{'static/bank/a.png':b'target'})
 with zipfile.ZipFile(archive,'w') as zipped:
  entry=zipfile.ZipInfo('static/bank/a.png');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16
  zipped.writestr(entry,b'target')
 manifest.update(bytes=archive.stat().st_size,sha256=assets.sha256(archive))
 with pytest.raises(ValueError,match='Unsafe'):assets.install_archive(archive,manifest,root)
 assert not (root/'static/bank/a.png').exists()

def test_unlisted_zip_entry_is_rejected(tmp_path):
 root,archive,manifest=fixture(tmp_path)
 with zipfile.ZipFile(archive,'a') as zipped:zipped.writestr('static/bank/unknown.png',b'unknown')
 manifest.update(bytes=archive.stat().st_size,sha256=assets.sha256(archive))
 with pytest.raises(ValueError,match='Unexpected'):assets.install_archive(archive,manifest,root)

def test_installer_preserves_user_modified_asset(tmp_path):
 root,archive,manifest=fixture(tmp_path);target=root/'static/bank/a.png';target.parent.mkdir();target.write_bytes(b'user modified')
 with pytest.raises(ValueError,match='不会覆盖'):assets.install_archive(archive,manifest,root)
 assert target.read_bytes()==b'user modified' and not (root/'static/paper/b.png').exists()

def test_digest_mismatch_prevents_partial_publication(tmp_path):
 root,archive,manifest=fixture(tmp_path);manifest['files']['static/paper/b.png']['sha256']='0'*64
 with pytest.raises(ValueError,match='digest'):assets.install_archive(archive,manifest,root)
 assert not (root/'static/bank/a.png').exists()

def test_cached_asset_verify_detects_same_size_corruption(tmp_path):
 root,archive,manifest=fixture(tmp_path);assets.install_archive(archive,manifest,root)
 target=root/'static/bank/a.png';target.write_bytes(b'x'*target.stat().st_size)
 assert assets.assets_ready(manifest,root,verify=False)
 assert not assets.assets_ready(manifest,root,verify=True)

def test_offline_ensure_assets_does_not_need_network(tmp_path,monkeypatch):
 root,archive,manifest=fixture(tmp_path)
 (root/'data/asset-manifest.json').write_text(json.dumps(manifest))
 monkeypatch.setattr(assets,'download',lambda *args:pytest.fail('Offline install used network'))
 result=assets.ensure_assets(root,archive=archive)
 assert result['ok'] and result['verified'] and not result['downloaded']
