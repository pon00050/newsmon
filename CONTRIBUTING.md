# Contributing

Thank you for your interest. Issues and pull requests are welcome.

- **Set up:** `uv sync --frozen --all-groups`, then `uv run pytest -q -m "not live and not slow"`. Tests never use the
  network (a guard fails any non-loopback connection) or a paid API.
- **Scope:** keep Newsmon one process with one SQLite file and no Docker requirement, fully usable without AI. Any AI
  feature must be optional and licence-gated per source. See `docs/ROADMAP.md` and `research/` for the design
  background; the architecture decisions are in `research/architecture/`.
- **Licensing rules are code:** a change must not let content reach storage, display, an AI provider or a public file
  beyond what its source's flags allow. Add a regression test for any such path.
- **Fixtures:** never commit captured third-party news text. Use synthetic content (see `tests/fixtures/wire/` and
  `demo/`).
- **Dependencies:** add them to `pyproject.toml`, run `uv lock`, then `uv run python scripts/third_party_notices.py`.
  Only licences compatible with Apache-2.0 are accepted (the script checks this).
- **Licence of contributions:** by contributing you agree that your code is licensed under Apache-2.0, and that
  documentation in `research/` and demo data are licensed under CC BY 4.0.
