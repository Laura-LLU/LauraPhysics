# Third-party dependencies and content

Program code: AGPL-3.0-only. Dependencies and question content use their respective licenses.

| Component | Runtime version | License | Use |
|---|---|---|---|
| PyMuPDF / MuPDF | PyMuPDF 1.28.2 | AGPL v3 or Artifex commercial agreement | PDF extraction, rendering, annotation |
| ReportLab | 4.5.1 | BSD-style | PDF layout |
| Pillow | 12.3.0 | MIT-CMU | Image processing |
| charset-normalizer | 3.5.2 | MIT | ReportLab dependency |
| Python | Recommended 3.12; supported 3.10–3.14 | PSF and associated notices | Runtime |

Test tools are pinned in `requirements-test.txt`: pytest (MIT), coverage.py (Apache-2.0), Playwright Python (Apache-2.0) and their dependencies. Browser distributions retain their upstream terms.

[PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)

## OPBP content

Source: [open-resources/physics_bank](https://github.com/open-resources/physics_bank/tree/59de2e82f4fa6fc1ca24c15a088f07428fd4480e).

The 900 selected questions comprise 709 under CC BY-NC-SA 4.0 and 191 under CC BY 4.0. Per-question author, URL, source digest, license and processing information are retained in `data/opbp-provenance.json` and`data/questions.json`. Teacher-reference answers are in `data/opbp-reference-answers.json`.

Processing includes cropping, splitting, typesetting, reference answers and scoring. Image assets, samples and screenshots follow [CONTENT_LICENSES.md](CONTENT_LICENSES.md). Retain source attribution, license links and processing descriptions when redistributing content.
