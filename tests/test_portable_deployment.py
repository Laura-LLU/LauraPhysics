from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pymupdf as fitz
import pytest
import ai_workflows as ai
import core_server as core
from scripts import prepare_release as release


def miniature_project(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir()
    for name,content in {'server.py':"VERSION='9.8.7'",'question_pool.py':'# new runtime module',
                         'requirements-test.txt':'pytest', 'README.md':'readme'}.items():
        (root/name).write_text(content,encoding='utf-8')
    (root/'data').mkdir();(root/'data/questions.json').write_text('{"metadata":{"appVersion":"0.0.1"}}')
    (root/'vendor').mkdir();(root/'vendor/macos-only.so').write_bytes(b'arm64')
    (root/'scripts').mkdir();(root/'scripts/ai-settings.json').write_text('{"private":"not for release"}')
    monkeypatch.setattr(release,'ROOT',root)
    return root


def test_portable_archive_contains_new_modules_current_version_and_verified_manifest(tmp_path,monkeypatch):
    root=miniature_project(tmp_path,monkeypatch)
    result=release.prepare(tmp_path/'package')
    assert 'v9.8.7-' in result['archive']
    with zipfile.ZipFile(result['archive']) as archive:
        names=archive.namelist();assert 'LauraPhysics/question_pool.py' in names
        assert 'LauraPhysics/requirements-test.txt' in names
        assert not any('/vendor/' in name or 'ai-settings.json' in name for name in names)
        manifest=json.loads(archive.read('LauraPhysics/release-manifest.json'))
        assert manifest['portable'] and manifest['version']=='9.8.7'
        for name,checksum in manifest['files'].items():
            assert hashlib.sha256(archive.read('LauraPhysics/'+name)).hexdigest()==checksum


def test_release_rejects_secrets_in_browser_assets(tmp_path,monkeypatch):
    root=miniature_project(tmp_path,monkeypatch);(root/'static').mkdir()
    (root/'static/app.js').write_text('const leaked="'+ 'sk-'+'x'*30+'";')
    with pytest.raises(ValueError,match='疑似凭证'):release.prepare(tmp_path/'package')


def test_release_cannot_include_a_symlink_to_external_files(tmp_path,monkeypatch):
    root=miniature_project(tmp_path,monkeypatch)
    private=tmp_path/'private.txt';private.write_text('not for distribution')
    try:(root/'data/external.txt').symlink_to(private)
    except OSError:pytest.skip('This filesystem does not permit test symlinks')
    with pytest.raises(ValueError,match='外部'):release.prepare(tmp_path/'package')


@pytest.mark.parametrize('system',['Windows','Linux'])
def test_non_mac_credentials_use_environment_and_are_never_exposed(monkeypatch,system):
    monkeypatch.setattr(core.platform,'system',lambda:system)
    monkeypatch.setenv('LAURAPHYSICS_OPEN_API_KEY','test-only-not-a-real-key')
    monkeypatch.setattr(core,'raw_settings',lambda:({'baseUrl':'https://example.invalid/v1','model':'test-model'},False))
    settings=core.public_settings()
    assert settings['configured'] and settings['credentialStored']
    assert 'test-only-not-a-real-key' not in json.dumps(settings)
    monkeypatch.delenv('LAURAPHYSICS_OPEN_API_KEY')
    assert core.read_api_key('test-profile')==''


def test_headless_linux_folder_export_keeps_pdf_and_zip_download(tmp_path,monkeypatch):
    monkeypatch.setattr(core.platform,'system',lambda:'Linux')
    monkeypatch.delenv('DISPLAY',raising=False);monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    job='a'*32;folder=tmp_path/'marking'/job;folder.mkdir(parents=True)
    core.save_json(folder/'job.json',{'state':'approved'})
    core.save_json(folder/'draft.json',{'assignmentTitle':'Portable.pdf','items':[]})
    doc=fitz.open();doc.new_page();doc.save(folder/'Marked-Paper.pdf');doc.close()
    result=ai.reveal_marking_batch({'jobIds':[job]},tmp_path,reveal=True)
    assert result['ok'] and not result['folderRevealed']
    assert (Path(result['outputDir'])/'批改试卷.zip').is_file()


def test_summary_without_macos_fonts_preserves_english_and_negative_exponents(tmp_path,monkeypatch):
    original=Path.is_file
    monkeypatch.setattr(Path,'is_file',lambda path:False if 'Arial Unicode.ttf' in str(path) or 'arialuni.ttf' in str(path) else original(path))
    job='b'*32;folder=tmp_path/'marking'/job;folder.mkdir(parents=True)
    core.save_json(folder/'job.json',{'state':'approved'})
    core.save_json(folder/'draft.json',{'items':[{'id':'test','source':'P456','title':'Force on a Mosquito','maximum':1,'teacherApproved':True,
        'markPoints':[{'marks':1,'awarded':False,'reason':'结果应为1.2×10⁻² kg·m s⁻¹。'}]}]})
    result=ai.batch_summary_pdf({'jobIds':[job]},tmp_path)
    from urllib.parse import unquote
    with fitz.open(tmp_path/unquote(result['summaryUrl'].removeprefix('/generated/'))) as doc:
        text=''.join(page.get_text() for page in doc)
        assert 'Force on a Mosquito' in text and '10^-2 kg m s^-1' in text and '全对率' in text
