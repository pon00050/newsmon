"""AST-based architecture checkers (T-03). Each returns a list of `Violation`s for the given files.

Every checker is proven twice in tests/arch: it flags its planted control file (known-answer) and passes the clean
`src/` tree. Control files live in tests/arch/controls/ with a `.py.txt` suffix so they are never imported or collected.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "newsmon"
CONTROLS = Path(__file__).resolve().parent / "controls"


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} [{self.rule}] {self.detail}"


def src_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py"))


def rel(p: Path) -> str:
    try:
        return p.relative_to(SRC).as_posix()
    except ValueError:
        return p.name


def _parse(p: Path) -> ast.AST:
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def _imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


# --- TS-ARCH-01 import boundaries (NFR-21) ---------------------------------------------------------------------------
IO_MODULES = ("sqlite3", "httpx", "anthropic", "smtplib", "openai", "requests", "socket", "urllib.request")
PURE_LAYERS = ("domain/", "pipeline/")


def check_import_boundaries(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        if not force and not rel(p).startswith(PURE_LAYERS):
            continue
        for line, mod in _imported_modules(_parse(p)):
            if any(mod == m or mod.startswith(m + ".") for m in IO_MODULES):
                out.append(Violation(rel(p), line, "import-boundary", f"pure layer imports {mod}"))
    return out


# --- TS-ARCH-02 SQL location (NFR-22) ---------------------------------------------------------------------------------
_SQL = re.compile(
    r"\b(SELECT\b[\s\S]+?\bFROM\b|INSERT\s+(OR\s+\w+\s+)?INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b|"
    r"CREATE\s+(TABLE|INDEX|UNIQUE|VIRTUAL|TRIGGER|VIEW)\b|DROP\s+(TABLE|INDEX|TRIGGER|VIEW)\b|ALTER\s+TABLE\b|PRAGMA\s+\w+)"
    r"|\b(insert\s+into\s+\w+|delete\s+from\s+\w+|create\s+(table|virtual\s+table|index)\s+\w+|pragma\s+\w+\s*[=(;]|"
    r"select\s+[\w*,\s.()]+\s+from\s+\w+\s+where\b)"
)


def check_sql_location(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        if not force and rel(p).startswith("repo/"):
            continue
        tree = _parse(p)
        docs = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                if _SQL.search(node.value):
                    out.append(Violation(rel(p), node.lineno, "sql-location", node.value.strip()[:60]))
    return out


# --- TS-ARCH-03 secret access (NFR-27) --------------------------------------------------------------------------------
_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)
SECRET_ADAPTER = "adapters/secrets.py"


def _module_constants(tree: ast.AST) -> dict[str, str]:
    consts = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
    return consts


def _is_os_environ(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "environ"
            and isinstance(node.value, ast.Name) and node.value.id == "os") or (
        isinstance(node, ast.Name) and node.id == "environ")


def check_secret_access(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        if not force and rel(p) == SECRET_ADAPTER:
            continue
        tree = _parse(p)
        consts = _module_constants(tree)

        def literal(arg: ast.AST) -> str | None:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
            if isinstance(arg, ast.Name):
                return consts.get(arg.id)
            return None

        for line, mod in _imported_modules(tree):
            if mod == "dotenv" or mod.startswith("dotenv."):
                out.append(Violation(rel(p), line, "secret-access", "dotenv outside the SecretStore adapter"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call):
                f = node.func
                is_getenv = (isinstance(f, ast.Attribute) and f.attr == "getenv") or (isinstance(f, ast.Name) and f.id == "getenv")
                is_env_get = isinstance(f, ast.Attribute) and f.attr in ("get", "pop", "setdefault") and _is_os_environ(f.value)
                if (is_getenv or is_env_get) and node.args:
                    name = literal(node.args[0])
            elif isinstance(node, ast.Subscript) and _is_os_environ(node.value):
                name = literal(node.slice)
            if name and _SECRET_NAME.search(name):
                out.append(Violation(rel(p), node.lineno, "secret-access", f"reads secret {name!r} outside SecretStore"))
    return out


# --- TS-ARCH-04 no tools parameter (NFR-08) ---------------------------------------------------------------------------
def check_no_tools_param(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        if not force and not rel(p).startswith(("ai/", "adapters/")):
            continue
        for node in ast.walk(_parse(p)):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg in ("tools", "tool_choice", "functions", "function_call"):
                        out.append(Violation(rel(p), node.lineno, "no-tools", f"{kw.arg}= passed to a provider call"))
    return out


# --- TS-ARCH-05 no training / fine-tuning (NFR-19) ---------------------------------------------------------------------
_TRAINING = re.compile(r"fine[_\-]?tun|/v1/fine_tunes|training_file|\.fine_tuning\b", re.I)


def check_no_training(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        tree = _parse(p)
        docs = _docstring_nodes(tree)
        for node in ast.walk(tree):
            text = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                text = node.value
            elif isinstance(node, ast.Attribute):
                text = node.attr
            elif isinstance(node, ast.Name):
                text = node.id
            elif isinstance(node, ast.keyword):
                text = node.arg
            if text and _TRAINING.search(text):
                out.append(Violation(rel(p), getattr(node, "lineno", 0), "no-training", text[:60]))
    return out


# --- TS-ARCH-06 parameterised SQL -------------------------------------------------------------------------------------
# An f-string is allowed only when every interpolation is a call to a vetted helper that emits identifiers from a fixed
# allow-list (`ident`) or a run of '?' placeholders (`qmarks`).
SAFE_SQL_HELPERS = ("ident", "qmarks")


def _unsafe_sql_expr(node: ast.AST) -> str | None:
    if isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                call = v.value
                fname = call.func.attr if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) else (
                    call.func.id if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) else None)
                if fname not in SAFE_SQL_HELPERS:
                    return "f-string with a non-vetted interpolation"
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return "%-formatted SQL"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return ".format() SQL"
    return None


def check_sql_params(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        tree = _parse(p)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            assigned: dict[str, ast.AST] = {}
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    assigned[node.targets[0].id] = node.value
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ("execute", "executemany", "executescript") and node.args):
                    arg = node.args[0]
                    why = _unsafe_sql_expr(arg)
                    if why is None and isinstance(arg, ast.Name) and arg.id in assigned:
                        why = _unsafe_sql_expr(assigned[arg.id])
                    if why:
                        out.append(Violation(rel(p), node.lineno, "sql-params", why))
    return sorted(set(out), key=lambda v: (v.file, v.line))


# --- TS-ARCH-07 no browser automation, no local models ----------------------------------------------------------------
FORBIDDEN_IMPORTS = ("playwright", "selenium", "pyppeteer", "torch", "transformers", "whisper", "faster_whisper",
                     "sentence_transformers", "kiwipiepy", "spacy", "ollama", "tensorflow", "onnxruntime", "fastembed",
                     "vosk", "speechbrain", "pyannote", "llama_cpp")


def check_forbidden_imports(files: list[Path], *, force: bool = False) -> list[Violation]:
    out = []
    for p in files:
        for line, mod in _imported_modules(_parse(p)):
            top = mod.split(".")[0]
            if top in FORBIDDEN_IMPORTS:
                out.append(Violation(rel(p), line, "forbidden-import", mod))
    return out
