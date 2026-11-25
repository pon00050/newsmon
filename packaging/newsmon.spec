# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the portable Windows app (onedir). Build with packaging/build_windows.ps1.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent          # <repo>/ (SPECPATH is packaging/)
SRC = ROOT / "src" / "newsmon"

datas = [
    (str(SRC / "web" / "templates"), "newsmon/web/templates"),       # Jinja2Templates(Path(__file__).parent / "templates")
    (str(SRC / "repo" / "migrations"), "newsmon/repo/migrations"),   # importlib.resources.files("newsmon.repo")/migrations
    (str(ROOT / "config.example"), "config.example"),                # desktop.find_example_dir() -> sys._MEIPASS
]
# The bundle redistributes third-party binaries (numpy/scipy/OpenBLAS, ...): ship the project's own notices beside the exe.
for _doc in ("LICENSE", "LICENSE-CC-BY-4.0.txt", "NOTICE", "THIRD_PARTY_NOTICES.md", "README.md"):
    if (ROOT / _doc).is_file():
        datas.append((str(ROOT / _doc), "."))
datas += collect_data_files("tldextract")   # .tld_set_snapshot: pipeline/domains.py uses suffix_list_urls=() so no network
datas += collect_data_files("tzdata")       # ZoneInfo("Asia/Seoul") on Windows has no system tz database
datas += collect_data_files("certifi")      # cacert.pem for httpx / TLS
datas += copy_metadata("newsmon")           # newsmon.__version__ reads importlib.metadata

hiddenimports = collect_submodules("newsmon") + collect_submodules("uvicorn") + ["tzdata"]

a = Analysis(
    [str(ROOT / "packaging" / "newsmon_desktop_entry.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "tkinter", "matplotlib", "IPython", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Newsmon",
    console=True,        # the console window is the "close this window to stop" control; Ctrl+C works
    upx=False,           # UPX-packed binaries raise more antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Newsmon")
