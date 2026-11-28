"""Command-line entry point. Sub-commands register themselves in COMMANDS (IR-06).

Each command is `(help, configure(parser), run(args) -> int)`. Later tasks add commands by calling `register`.
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable

from newsmon import __version__

Configure = Callable[[argparse.ArgumentParser], None]
Run = Callable[[argparse.Namespace], int]

COMMANDS: dict[str, tuple[str, Configure, Run]] = {}


def register(name: str, help_: str, configure: Configure, run: Run) -> None:
    COMMANDS[name] = (help_, configure, run)


def _load_builtin_commands() -> None:
    # Imported lazily so `newsmon --version` stays fast and has no side effects.
    from newsmon.ops import commands  # noqa: F401  (registers init, migrate, run-once, ...)
    from newsmon.ops import events_cmd  # noqa: F401  (registers events)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsmon", description="Foreign-news desk monitoring")
    parser.add_argument("--version", action="version", version=f"newsmon {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for name, (help_, configure, _run) in sorted(COMMANDS.items()):
        configure(sub.add_parser(name, help=help_))
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # redirected output on Windows defaults to a legacy code page that cannot encode Korean. A real console already
        # writes UTF-8 and is left alone; the NUL device claims to be a tty but still uses the legacy code page.
        enc = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if hasattr(stream, "reconfigure") and (not stream.isatty() or enc != "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    _load_builtin_commands()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    _help, _configure, run = COMMANDS[args.command]
    return int(run(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
