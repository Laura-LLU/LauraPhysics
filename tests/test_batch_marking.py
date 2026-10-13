import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ai_workflows as marking
import core_server as core


class DormantThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


with tempfile.TemporaryDirectory(prefix='lauraphysics-batch-marking-') as temporary:
    root = Path(temporary)
    job_ids = [f'{index:032x}' for index in range(1, 5)]
    for job_id in job_ids:
        folder = root / 'marking' / job_id
        folder.mkdir(parents=True)
        core.save_json(folder / 'job.json', {'state': 'identified', 'ready': True})

    marking.RUNNING.clear()
    with mock.patch.object(core, 'public_settings', return_value={'configured': True, 'markingModel': 'test-vision'}), \
         mock.patch.object(marking.threading, 'Thread', DormantThread):
        for job_id in job_ids[:3]:
            result = marking.start({'jobId': job_id, 'confirmSend': True}, root)
            assert result['state'] == 'processing'
        try:
            marking.start({'jobId': job_ids[3], 'confirmSend': True}, root)
            raise AssertionError('fourth concurrent marking job should be blocked')
        except ValueError as exc:
            assert '已有3份答卷正在批改' in str(exc)
    marking.RUNNING.clear()

html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
swift = (ROOT / 'native' / 'main.swift').read_text(encoding='utf-8')
assert '学生姓名<input id="markingStudent"' not in html
assert '补填 OPBP 题号' not in html
assert 'id="markingFile" type="file"' in html and 'multiple' in html
session_js = (ROOT / 'static' / 'marking-session.js').read_text(encoding='utf-8')
assert 'startMarkingBatch' in session_js and '3-state.markingBatch.filter' in session_js
assert 'revealMarkingBatch' in session_js and '/api/marking/reveal-batch' in session_js
assert '统一导出并打开文件夹' in session_js
assert "if(!normalized){awarded.value='false'" in html
assert "if(!normalized){select.value='false'" in html
assert '按未作答不给分' in html
assert 'panel.allowsMultipleSelection = true' in swift
assert 'fileDropHandler: (([URL]) -> Void)?' in swift

with tempfile.TemporaryDirectory(prefix='lauraphysics-batch-export-') as temporary:
    root = Path(temporary)
    export_ids = [f'{index:032x}' for index in range(10, 12)]
    for index, job_id in enumerate(export_ids, 1):
        folder = root / 'marking' / job_id
        folder.mkdir(parents=True)
        core.save_json(folder / 'job.json', {'state': 'approved', 'title': f'Student Paper {index}.pdf'})
        core.save_json(folder / 'draft.json', {'assignmentTitle': f'Student Paper {index}.pdf'})
        (folder / 'Marked-Paper.pdf').write_bytes(f'marked-{index}'.encode())
    result = marking.reveal_marking_batch({'jobIds': export_ids}, root, reveal=False)
    assert result['count'] == 2
    assert sorted(path.name for path in Path(result['outputDir']).glob('*.pdf')) == sorted(result['files']+['Class-Marking-Summary.pdf'])

print(json.dumps({'redundantFieldsRemoved': True, 'multiFileInput': True,
                  'nativeMultiDrop': True, 'parallelLimit': 3, 'overflowQueuedByUi': True}))
