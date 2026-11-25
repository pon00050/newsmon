"""Build the website's dashboard datasets with the real Newsmon pipeline.

    uv run python scripts/build_public_data.py synthetic --out _site_data/synthetic.json
    uv run python scripts/build_public_data.py live --config demo/live-config --data .live-state \
        --previous previous-live.json --out _site_data/live.json

synthetic: copies demo/config to a temporary folder, writes fictional wire files into its inbox with
demo/make_demo_inbox.py (timestamps relative to now), then runs init -> collect -> export-public.
live: runs init -> collect -> export-public against a config whose sources carry a documented public
redistribution permission (demo/live-config). With --previous, earlier published items roll forward (bounded).
republish: no collection; the previous snapshot re-filtered against the current permissions (used when collection fails).

Both paths go through the normal collection, dedup, ranking and the public publication gate; nothing here
collects, ranks or filters on its own. Exit status is non-zero if any step fails or the export is refused.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def newsmon(*args: str, config: Path, data: Path) -> None:
    env = dict(os.environ, NEWSMON_CONFIG_DIR=str(config), NEWSMON_DATA_DIR=str(data))
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):  # the public build never uses AI
        env.pop(k, None)
    cmd = [sys.executable, "-c", "import sys; from newsmon.cli import main; sys.exit(main(sys.argv[1:]))", *args]
    print("+ newsmon " + " ".join(args), flush=True)
    r = subprocess.run(cmd, env=env, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"step failed ({r.returncode}): newsmon {' '.join(args)}")


def synthetic(out: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="newsmon-demo-") as tmp:
        cfg, data = Path(tmp) / "config", Path(tmp) / "data"
        shutil.copytree(ROOT / "demo" / "config", cfg)
        inbox = cfg / "inbox" / "demo"
        inbox.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable, "-I", str(ROOT / "demo" / "make_demo_inbox.py"), "--out", str(inbox)])
        if r.returncode != 0:
            raise SystemExit("demo inbox generation failed")
        newsmon("init", config=cfg, data=data)
        # The inbox watcher ingests a file once it is unchanged across two scans (partial-copy protection).
        newsmon("collect", "--force", config=cfg, data=data)
        newsmon("collect", "--force", config=cfg, data=data)
        newsmon("export-public", "--dataset", "synthetic", "--out", str(out.resolve()), config=cfg, data=data)


def live(out: Path, config: Path, data: Path, previous: Path | None, max_items: int, max_age_days: int) -> None:
    data.mkdir(parents=True, exist_ok=True)
    newsmon("init", config=config, data=data)
    newsmon("collect", "--force", config=config, data=data)
    args = ["export-public", "--dataset", "live", "--out", str(out.resolve()), "--max-items", str(max_items),
            "--max-age-days", str(max_age_days)]
    if previous is not None:
        args += ["--previous", str(previous.resolve())]
    newsmon(*args, config=config, data=data)


def republish(out: Path, config: Path, data: Path, previous: Path, max_items: int, max_age_days: int) -> None:
    """Collection failed: republish the previous snapshot, re-filtered against the CURRENT source permissions
    (a source switched to `none` disappears, `metadata` loses headlines) and the age/size bounds. Nothing is fetched."""
    data.mkdir(parents=True, exist_ok=True)
    newsmon("init", config=config, data=data)
    newsmon("export-public", "--dataset", "live", "--out", str(out.resolve()), "--previous", str(previous.resolve()),
            "--max-items", str(max_items), "--max-age-days", str(max_age_days), config=config, data=data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dataset", choices=["synthetic", "live", "republish"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--config", type=Path, default=ROOT / "demo" / "live-config")
    ap.add_argument("--data", type=Path, default=ROOT / ".live-state")
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--max-items", type=int, default=300)
    ap.add_argument("--max-age-days", type=int, default=14)
    a = ap.parse_args()
    if a.dataset == "synthetic":
        synthetic(a.out)
    elif a.dataset == "republish":
        if a.previous is None:
            raise SystemExit("republish needs --previous")
        republish(a.out, a.config, a.data, a.previous, a.max_items, a.max_age_days)
    else:
        live(a.out, a.config, a.data, a.previous, a.max_items, a.max_age_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
