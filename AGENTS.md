# AGENTS.md

## Cursor Cloud specific instructions

Python 3.12 CLI project (Naver / 당근마켓 쇼핑 대행 하네스). There is no web server or GUI app — the "application" is the set of CLI scripts under `scripts/`. Standard install/run commands live in `README.md`.

### Environment
- Dependencies are installed into a `.venv` virtualenv at the repo root by the startup update script. Always invoke tools via that venv, e.g. `.venv/bin/python`, `.venv/bin/pytest`. `.venv/` is gitignored.
- Playwright's Chromium is downloaded to `~/.cache/ms-playwright` (persisted in the snapshot). `naver_common.launch_browser()` forces headful; `naver_poc.py --mode browser` accepts `--headless`.

### Test / lint
- Tests: `.venv/bin/python -m pytest -q` — 126 pure unit tests driven by fixtures in `tests/fixtures/`. No network or browser needed.
- No linter/formatter is configured in this repo (no ruff/flake8/black/pyproject config).

### Running the app (pipelines)
- Runtime artifacts are written to `_workspace/` (gitignored) as numbered JSON files that feed the next stage: `01_candidates` → `03_prices` → `04_reviews`/`04_review_risk` → `05_final`.
- Naver flow: `scripts/naver_poc.py` (search) → `naver_product_detail.py` (03_prices) → `naver_reviews.py` (04_reviews) → `build_final.py` (05_final ranked recommendation).
- 당근마켓 flow: `scripts/daangn_collect.py` → `scripts/build_report.py`.
- `build_final.py` / `build_report.py` are pure file processors (no network); they are the deterministic way to exercise/demonstrate the scoring & ranking logic end-to-end.

### Non-obvious gotcha (live scraping)
- Live scraping is unreliable from the cloud VM: browser mode reaches Naver but is served the anti-bot login wall (page title `NAVER 로그인`), and `--mode api` requires a `NAVER_CLIENT_SECRET` secret (only `NAVER_CLIENT_ID=pds2225` is preset in `.env.example`). Per the README this is expected ("봇 차단 시 사람 개입"). Prefer the offline pipeline stages when you need a repeatable end-to-end run.
