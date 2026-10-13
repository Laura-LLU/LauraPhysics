# Third-party dependencies and content

Code is AGPL-3.0-only. Dependency and content licenses remain their own. This notice is not a legal warranty or an additional grant from upstream authors.

| Component | Pinned runtime version | License | Use |
|---|---|---|---|
| PyMuPDF / MuPDF | PyMuPDF 1.28.2 | AGPL v3 or Artifex commercial agreement | PDF extraction, rendering, annotation |
| ReportLab | 4.5.1 | BSD-style | PDF layout |
| Pillow | 12.3.0 | MIT-CMU | Image processing |
| charset-normalizer | 3.5.2 | MIT | ReportLab dependency |
| Python | Recommended 3.12; supported 3.10–3.14 | PSF and associated notices | Independently installed, not redistributed |

Test tools are pinned in `requirements-test.txt`: pytest (MIT), coverage.py (Apache-2.0), Playwright Python (Apache-2.0) and installed transitive dependencies. Downloaded browsers retain upstream terms. This repository does not vendor Python, wheels, Chromium, Apple system fonts or a signed/notarized macOS binary. Retain original notices if separately redistributing them.

PyMuPDF licensing: https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright . AGPL does not waive combined-work obligations or permit closed-source redistribution contrary to upstream terms.

OPBP source snapshot: https://github.com/open-resources/physics_bank/tree/59de2e82f4fa6fc1ca24c15a088f07428fd4480e . 900 active selected questions: 709 CC BY-NC-SA 4.0; 191 CC BY 4.0. These are selected-question counts, not unique upstream-file counts. 113 archived parent records are compatibility data, not extra active questions.

Per-question author, URL, source digest, license and modification information are retained in `data/opbp-provenance.json` and `data/questions.json`. Teacher-reference answers are in `data/opbp-reference-answers.json`. Cropping/splitting/typesetting/reference answers/scoring are local processing, not Cambridge or upstream author approval. Separate content terms also cover image assets in Releases; see `CONTENT_LICENSES.md`.

No official Cambridge exam archive, real student submission, API credential, private setting or author-specific development history is shipped.
