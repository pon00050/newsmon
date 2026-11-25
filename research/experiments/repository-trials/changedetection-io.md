# Trial — dgtlmoon/changedetection.io (R3, 2026-11-25)

> **Status: Experimental result.** Trial of an existing open-source tool in an isolated environment.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Verdict from the trial:** runs on this Windows machine from pip without Docker; REST API works; private-address fetch
guard works. **TESTED** (files in this folder).

## Environment
Windows 11, Python 3.13.7, uv. No Docker. Isolated venv in the R3 scratch folder (not in the project).

## Exact commands
```
uv venv <scratch>/cd_venv --python 3.13
uv pip install --python <scratch>/cd_venv/Scripts/python.exe changedetection.io
#   -> resolved to 0.45.14 (old). Cause: 0.70.4 pins pyppeteer-ng==2.0.0rc16, a pre-release.
uv pip install --prerelease=allow --python <scratch>/cd_venv/Scripts/python.exe "changedetection.io==0.70.4"   # 1m36s
<scratch>/cd_venv/Scripts/changedetection.io.exe -d <scratch>/cd_data -p 5099 -h 127.0.0.1
python -I cd_api_trial.py <scratch>/cd_data cd_api_trial_out.json      # API exercise (script in this folder)
# then a local-only probe: POST /api/v1/watch for http://127.0.0.1:5099/ and http://169.254.169.254/latest/meta-data/
# stop: Stop-Process on every process whose path is under <scratch>/cd_venv (2 processes stopped, 0 remaining)
```

## What worked
| Step | Result | Evidence |
|---|---|---|
| Install 0.70.4 (latest release, 2026-11-19) | OK with `--prerelease=allow` only | commands above |
| Server start on 127.0.0.1:5099 | HTTP 200 on `/` | run log (scratch) |
| API key | auto-generated in `<data>/changedetection.json`; read at run time, never printed | `cd_api_trial.py` |
| `POST /api/v1/watch` (Yonhap English RSS `https://en.yna.co.kr/RSS/news.xml`, robots.txt allows `/RSS`) | 201 + uuid | `cd_api_trial_out.json` |
| First check | `check_count 1`, `last_error false`, fetch backend `system` (plain HTTP, no browser) | same |
| `GET /watch/<id>/history` + snapshot | 1 snapshot, 28,304 chars of text extracted from the RSS, stored Brotli-compressed as a flat file | same |
| `GET /systeminfo` | 5 fetch workers; processors `text_json_diff`, `restock_diff` | same |
| Private-address guard | Watches to 127.0.0.1 and 169.254.169.254 are **accepted** by the API (201) but the **fetch is blocked**: "resolves to a private/reserved IP address … Set ALLOW_IANA_RESTRICTED_ADDRESSES=true to allow." | `cd_ssrf_probe.txt` + run log |

## What failed or surprised
- Plain `pip install changedetection.io` silently installs a 2-year-old version (0.45.14) on Python 3.13 because the
  current release depends on a pre-release package. A deployment must pin the version and allow pre-releases.
- On first start the app **creates example watches and fetches them by itself** (news.ycombinator.com,
  changedetection.io CHANGELOG). Not caused by this trial's requests; a deployment should delete them at setup.
- The unit of work is **one watched page → diff → notification**. There is no article model, no cross-source
  de-duplication, no search across items and no clustering. Storage is flat files per watch (no database).
- Uses Flask's development server in pip mode ("Do not use it in a production deployment").

## Implication (D1)
Integrate as a **component** for watching sources that have no feed (for example a State Department briefing index
page, a broadcaster notice page), feeding its change notifications (Apprise/webhook) into the project's own pipeline.
Not a foundation: it does not model items, dedup or search. Licence Apache-2.0 (commercial reuse fine).

API spend: $0.
