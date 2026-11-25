# Infrastructure, costs and releases

## Expected recurring cost: none

| Service | Use | Why it is free (checked 2026-11-25) |
|---|---|---|
| GitHub public repository | source, issues, releases | GitHub Free includes public repositories. Release files must each be under 2 GiB, with no total-size or bandwidth limit. |
| GitHub Actions, standard hosted runners | CI on Linux and Windows; website build every 3 hours | Standard runners in public repositories are free and do not use the included minutes. Jobs here time out after 10–25 minutes (the platform limit is 6 h). |
| GitHub Pages | website, research library, dashboards | Free for public repositories. Site limit 1 GB, soft bandwidth limit 100 GB a month. The 10-builds-per-hour limit does not apply to Actions-based deployment. |
| Data sources | NASA news feed | public feed, no key, one request per run |
| AI | none | the website build removes any AI key from the environment and never calls a model |

No domain, server, database, paid runner or paid API is used. To keep it that way, do not switch workflows to
larger (paid) runners. If the account has a payment method on file, set a $0 Actions budget with "stop usage"
enabled.

## Limits of relying on free services

- **Scheduled runs are best-effort.** GitHub can delay scheduled workflows under load, and can drop them. The
  dashboard shows its last update time, so a late run is visible.
- **Scheduled workflows are switched off after 60 days without repository activity.** If the live dashboard stops
  updating, re-enable the "Website" workflow on the Actions tab, or push any commit.
- **Pages is for project showcases.** GitHub's terms do not allow using it as free hosting for a commercial service.
  A managed or paid Newsmon offering would need its own hosting.
- **Actions acceptable use.** Work on GitHub-hosted runners must relate to the repository's software. The scheduled
  job builds and publishes this project's own demonstration with a few feed requests every three hours, which keeps
  the burden low.
- **Third-party feeds can change or disappear.** A failed collection keeps the previous snapshot. A source that keeps
  failing shows its status on the dashboard's source table.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, pull request, manual | tests on Ubuntu and Windows; launcher check on Windows; licence check; synthetic data and site build; public-artifact check; gitleaks over the full history |
| `pages.yml` | push to `main`, every 3 hours, manual | builds synthetic and live datasets with the real pipeline, builds the site, validates it and deploys to Pages. Concurrency group `pages`, so runs never overlap. |
| `release.yml` | tag `v*`, manual | builds the source ZIP and the Windows portable build, writes SHA-256 checksums and publishes the GitHub Release |

Permissions are least-privilege: workflows default to `contents: read`. Only the Pages deploy job gets `pages: write`
and `id-token: write`, and only the release job gets `contents: write`.

## Making a release

1. Update `version` in `pyproject.toml` and `src/newsmon/__init__.py`, and add a `CHANGELOG.md` entry.
2. Run the gate locally: `uv run pytest -q -m "not live and not slow"`, `uv run python scripts/third_party_notices.py --check`,
   `uv run python scripts/check_public_artifacts.py . --repo`.
3. Commit, then tag and push: `git tag v0.1.1 && git push origin v0.1.1`.
4. `release.yml` attaches `newsmon-<version>-source.zip`, `newsmon-<version>-windows-portable.zip` and
   `SHA256SUMS.txt`, and uses the changelog section as the release notes.

The build is reproducible from the lock file (`uv sync --frozen`). The portable build is produced on GitHub's
`windows-latest` runner, not on a developer machine, so it contains no local paths or settings.
