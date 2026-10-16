from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_demo_samples import verify_sample

SAMPLES = Path(__file__).resolve().parents[1] / 'examples' / 'marking-demo'
ENTRIES = json.loads((SAMPLES / 'sample-manifest.json').read_text(encoding='utf-8'))
FULL_PAPERS = SAMPLES.parent / 'full-papers'
FULL_ENTRIES = json.loads((FULL_PAPERS / 'sample-manifest.json').read_text(encoding='utf-8'))


def test_only_declared_public_demo_pdfs_are_present():
    assert {p.name for p in SAMPLES.glob('*.pdf')} == {entry['file'] for entry in ENTRIES}


@pytest.mark.parametrize('entry', ENTRIES, ids=[entry['file'] for entry in ENTRIES])
def test_published_pdf_matches_upload_identification_and_attribution(entry, tmp_path):
    result = verify_sample(SAMPLES, entry, tmp_path)
    assert result['ok'] and result['questionRefs'] == entry['questionRefs']
    assert result['realModelCalls'] is False


def test_only_declared_complete_papers_are_present():
    assert {p.name for p in FULL_PAPERS.glob('*.pdf')} == {entry['file'] for entry in FULL_ENTRIES}


@pytest.mark.parametrize('entry', FULL_ENTRIES, ids=[entry['file'] for entry in FULL_ENTRIES])
def test_complete_paper_identifies_all_six_questions(entry, tmp_path):
    result = verify_sample(FULL_PAPERS, entry, tmp_path)
    assert result['ok'] and result['pages'] == 7
    assert result['questionRefs'] == entry['questionRefs']
    assert result['realModelCalls'] is False


def test_changed_sample_is_rejected_before_identification(tmp_path):
    entry = ENTRIES[0]
    (tmp_path / entry['file']).write_bytes((SAMPLES / entry['file']).read_bytes() + b'changed')
    output = tmp_path / 'result'
    with pytest.raises(ValueError, match='SHA-256'):
        verify_sample(tmp_path, entry, output)
    assert not output.exists()
