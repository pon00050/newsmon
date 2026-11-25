# Portable Windows app (PyInstaller, onedir)

`Newsmon.exe` is `newsmon.desktop.main()` frozen with its dependencies: double-click, a console window opens, the
server starts on `127.0.0.1:8765` (same as `newsmon serve --auto-collect`) and the default browser opens when `/healthz`
answers. Close the window or press Ctrl+C to stop.

## Build

```powershell
powershell -File packaging\build_windows.ps1 -Zip      # output: %TEMP%\newsmon-build\dist\Newsmon\ and ...\Newsmon-windows-x64.zip
powershell -File packaging\build_windows.ps1 -Out D:\out
```

Needs `uv`. PyInstaller (pinned in the script) is added only to a throwaway `uv run --with` environment: `pyproject.toml`
and `uv.lock` are not touched. Nothing is written inside the repository (work and dist go to `-Out`).

Measured on Windows 11, Python 3.13, PyInstaller 6.22.3: build about 2 min, folder 174 MB, zip 73 MB, cold start to
`/healthz` about 5.7 s (6-8 s on the very first launch), Ctrl+C stop about 1.2 s with exit code 0.

## What is bundled (newsmon.spec)

Templates, SQL migrations, `config.example` (copied into `%LOCALAPPDATA%\Newsmon\config` on first run, never over existing
files), `tzdata` (Windows has no tz database), `certifi`, tldextract's bundled public-suffix snapshot (the code already
passes `suffix_list_urls=()`, so it never fetches the list), the `newsmon` package metadata (for `--version`) and the
project licence and notice files. Empty directories do not survive PyInstaller, so `desktop.ensure_inbox_dirs` recreates
the `inbox/` folders that directory sources point at.

## Caveats

- **Unsigned.** A downloaded zip carries the Mark of the Web, so SmartScreen shows "Windows protected your PC" until the
  user chooses More info, Run anyway. A code-signing certificate removes this; none is used here.
- **Antivirus.** PyInstaller bootloaders are a known source of false positives. UPX is off to reduce them. Publish the
  SHA-256 of the zip with the release and submit the file to Microsoft if Defender flags it.
- **Size.** About 90 MB of the folder is scipy and OpenBLAS, pulled in by `datasketch`. Trimming is possible but untested.
- **Updates.** Replace the folder; config and data live under `%LOCALAPPDATA%\Newsmon` and are not touched.
- Windows only. Build on the OS you ship for (CI: `windows-latest`).
