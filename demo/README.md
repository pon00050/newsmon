# Newsmon public demo: synthetic inbox

`make_demo_inbox.py` writes 48 plain-text wire files (format: `tests/fixtures/wire/plain/FORMAT.md`) that the demo copies
into the watched inbox of the `mock_wire_demo` source. Newsmon's directory connector parses, dedups and ranks them.

**All content is fictional.** Places (Aldoria, Lakeshore, Brightwater and others), agencies (Demo Wire, Sample News
Service, 예시통신, 示例通讯社), institutions and people are invented. Every body carries the marker `[SYNTHETIC DEMO]`.
Real pipeline behaviour is exercised; the news is not real.

## Run

```
.venv\Scripts\python -I demo\make_demo_inbox.py --out <DIR>
.venv\Scripts\python -I demo\make_demo_inbox.py --out <DIR> --now 2026-11-25T09:00:00+00:00
```

- `--out DIR` is created if missing. Existing files with the same names are overwritten.
- `--now` sets the reference time; timestamps fall in the 48 hours before it. Default: current UTC time.
- Output is deterministic for a given `--now`.

## Contents

- 48 files: about 50% English, 30% Korean, 20% Chinese (simplified).
- Three near-duplicate pairs (two agencies, reworded), one exact duplicate, and one story with a version 2 update.
- A few urgency 1-2 items (wire flash rule) and several topic-keyword hits; the rest are unrelated or hit the
  `exclude_keywords` list.
