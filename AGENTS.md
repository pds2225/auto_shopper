# AGENTS.md

## Cursor Cloud specific instructions

Python 3.12 CLI project plus a phone/desktop web app under `web/` (Naver / 당근마켓 쇼핑 대행 하네스). CLI scripts live in `scripts/`. The mobile web UI is `web/` (Next.js). Standard install/run commands live in `README.md`.

### Environment
- Dependencies are installed into a `.venv` virtualenv at the repo root. Always invoke tools via that venv, e.g. `.venv/bin/python`, `.venv/bin/pytest`. `.venv/` is gitignored.
- Playwright Chromium may be present at `~/.cache/ms-playwright`. `naver_common.launch_browser()` forces headful; `naver_poc.py --mode browser` accepts `--headless` only on that PoC script.

### Test / lint
- Tests: `.venv/bin/python -m pytest -q` — pure unit tests driven by fixtures in `tests/fixtures/`. No network or browser needed.
- Web app: `cd web && npm test && npm run build`
- No Python linter/formatter is configured (no ruff/flake8/black/pyproject).

### Running the app (pipelines)
- Runtime artifacts go to `_workspace/` (gitignored) as numbered JSON: `01_candidates` → `03_prices` → `04_reviews`/`04_review_risk` → `05_final`.
- **Preferred one-shot:** `.venv/bin/python scripts/run_naver.py --offline` (no network) or `.venv/bin/python scripts/run_naver.py "무선청소기" --skip-browser`.
- Live Naver flow: `naver_poc.py` → `naver_product_detail.py` → `naver_reviews.py` → `review_risk.py` → `build_final.py`.
- 당근마켓 flow: `daangn_collect.py` → `build_report.py`.
- `build_final.py` / `build_report.py` / `review_risk.py` are pure file processors.

### Non-obvious gotcha (live scraping)
- Live scraping is unreliable from the cloud VM: browser mode often hits the Naver anti-bot login wall. `--mode api` needs `NAVER_CLIENT_SECRET`. Prefer `--offline` or `--skip-browser` for repeatable end-to-end runs. Bot blocks must stop with `needs_human` — never bypass captcha.
