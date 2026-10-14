"""Public installation defaults; never contact a real model or keychain."""
from __future__ import annotations

import json

import pytest

import core_server as core
from conftest import QA_ARTIFACTS, request_json


@pytest.fixture
def fresh_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'SETTINGS_PATH', tmp_path / 'settings.json')
    monkeypatch.setattr(core, 'LEGACY_SETTINGS', tmp_path / 'legacy.json')
    monkeypatch.setenv('LAURAPHYSICS_DISABLE_LEGACY_CONFIG', '1')
    monkeypatch.setenv('LAURAPHYSICS_DISABLE_KEYCHAIN', '1')
    monkeypatch.delenv('LAURAPHYSICS_OPEN_API_KEY', raising=False)


def test_fresh_defaults_need_user_key_and_do_not_persist(fresh_settings, monkeypatch):
    settings = core.public_settings()
    for name, value in core.DEFAULT_AI_SETTINGS.items():
        assert settings[name] == value
    assert not settings['configured'] and not settings['credentialStored']
    assert not settings['isLocal'] and not settings['inheritedFromPhysicsBank']
    assert not core.SETTINGS_PATH.exists()
    monkeypatch.setattr(core, 'urlopen', lambda *a, **kw: pytest.fail('Unexpected network call'))
    with pytest.raises(ValueError, match='尚未配置'):
        core.chat([{'role': 'user', 'content': 'test'}])
    first, _ = core.raw_settings()
    first['model'] = 'changed-test-copy'
    assert core.raw_settings()[0]['model'] == 'qwen3.8-flash'


def test_environment_key_activates_defaults_without_exposing_it(fresh_settings, monkeypatch):
    key = 'qa-only-not-a-real-credential'
    monkeypatch.setenv('LAURAPHYSICS_OPEN_API_KEY', key)
    settings = core.public_settings()
    assert settings['configured'] and settings['credentialStored']
    assert settings['credentialProfile'] == 'qwen'
    assert key not in json.dumps(settings)


@pytest.mark.parametrize('endpoint', ['https://api.deepseek.com', 'http://127.0.0.1:11434/v1'])
def test_unrelated_legacy_provider_is_not_automatically_imported(fresh_settings, monkeypatch, endpoint):
    monkeypatch.delenv('LAURAPHYSICS_DISABLE_LEGACY_CONFIG')
    core.save_json(core.LEGACY_SETTINGS, {'baseUrl': endpoint, 'model': 'legacy-test'})
    settings, inherited = core.raw_settings()
    assert settings == core.DEFAULT_AI_SETTINGS and not inherited


def test_explicit_saved_configuration_is_not_overwritten(fresh_settings):
    saved = {'baseUrl': 'https://example.invalid/v1', 'model': 'saved-model', 'markingModel': 'saved-vision'}
    core.save_json(core.SETTINGS_PATH, saved)
    settings, inherited = core.raw_settings()
    assert settings == saved and not inherited
    assert core.load_json(core.SETTINGS_PATH, {}) == saved


def test_disabled_keychain_does_not_invoke_system_credential_tool(fresh_settings, monkeypatch):
    monkeypatch.setattr(core.subprocess, 'run', lambda *a, **kw: pytest.fail('Real keychain access'))
    assert core.read_keychain('unused', 'unused') == ''


@pytest.mark.parametrize('endpoint', ['/api/settings', '/api/ai/settings'])
def test_settings_api_returns_bailian_defaults(isolated_server, endpoint):
    status, settings = request_json(isolated_server, endpoint)
    assert status == 200
    for name, value in core.DEFAULT_AI_SETTINGS.items():
        assert settings[name] == value
    assert not settings['configured'] and not settings['credentialStored']
    assert 'apiKey' not in settings


@pytest.mark.parametrize('path,preset,smart', [('/', '#preset', False), ('/opbp', '#providerPreset', True),
                                            ('/0625.html', '#providerPreset', True)])
def test_browser_has_only_bailian_and_custom_presets(isolated_server, page, path, preset, smart):
    page.goto(isolated_server.base_url + path)
    page.wait_for_load_state('networkidle')
    page.wait_for_function("document.querySelector('#modelName').value === 'qwen3.8-flash'")
    if smart:
        page.evaluate("switchView('smart')")
    else:
        page.locator('details.settings summary').click()
    options = page.locator(preset + ' option').evaluate_all('(options) => options.map(o => o.value)')
    assert options == ['', 'qwen']
    assert page.locator(preset).input_value() == 'qwen'
    assert page.locator('#baseUrl').input_value() == core.DEFAULT_AI_SETTINGS['baseUrl']
    assert page.locator('#markingModel').input_value() == 'qwen3.7-plus'
    assert page.locator('#apiKey').input_value() == ''
    page.locator(preset).select_option('')
    page.locator('#modelName').fill('test-custom-model')
    page.locator(preset).select_option('qwen')
    assert page.locator('#modelName').input_value() == 'qwen3.8-flash'
    page.screenshot(path=str(QA_ARTIFACTS / ('bailian-defaults-' + ('home' if path == '/' else path[1:]) + '.png')),
                    full_page=True)
