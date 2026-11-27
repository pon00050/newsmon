# Running Newsmon on Windows

There are two ways to start Newsmon without typing commands. Both keep your settings and database in
`%LOCALAPPDATA%\Newsmon\` (`config\` and `data\`), so you can update, move or delete the program folder without
losing them. Neither needs an AI key.

## Option 1: portable app (no installation)

1. From the [latest release](https://github.com/pon00050/newsmon/releases/latest), download
   `newsmon-<version>-windows-portable.zip` and extract it.
2. Double-click `Newsmon\Newsmon.exe`. A console window opens, the server starts, and your browser opens
   `http://127.0.0.1:8765/`.
3. Close the window or press Ctrl+C to stop.

The app is not code-signed, so Windows SmartScreen may say "Windows protected your PC". Choose **More info** and
then **Run anyway**. You can check the download against `SHA256SUMS.txt` from the same release:
`Get-FileHash .\newsmon-0.2.0-windows-portable.zip`. The extracted folder is about 175 MB. The first start takes up
to about 8 seconds.

It is built by GitHub Actions on a clean `windows-latest` runner with PyInstaller (onedir) from `packaging/newsmon.spec`.
It contains Python, Newsmon and its libraries, the example configuration, and the licence and notice files. See
`packaging/README.md`.

## Option 2: launcher from the source folder

1. Download `newsmon-<version>-source.zip` (or clone the repository) and extract it.
2. Double-click **`Start-Newsmon.cmd`**.

On first use the launcher:

- finds [uv](https://docs.astral.sh/uv/), or offers to install it for your Windows account (no administrator rights);
- installs Python 3.12+ and the locked libraries into `%LOCALAPPDATA%\Newsmon\venv`. This takes a few minutes once,
  and later starts take seconds;
- runs `newsmon-desktop`, which copies the example configuration into `%LOCALAPPDATA%\Newsmon\config` (never over
  existing files), creates or upgrades the database, starts the server with background collection, waits until it
  answers, and opens your browser.

If Newsmon is already running on that port, the launcher just opens the browser. If another program uses the port, it
says so and stops. Options: `Start-Newsmon.cmd --no-browser`, `--port 8780`, `--config <folder>`, `--data <folder>`.
`NEWSMON_CONFIG_DIR` and `NEWSMON_DATA_DIR` are honoured if set.

## Changing what Newsmon monitors

Edit the files in `%LOCALAPPDATA%\Newsmon\config\`:

- `sources.yaml` lists feeds and their licence flags;
- `profiles\*.yaml` sets what is important to your desk.

Changes apply at the next collection. See [`configuration.md`](configuration.md).

## Troubleshooting

| Symptom | What to do |
|---|---|
| "Installing Newsmon's libraries failed" | check the internet connection and proxy, then run the launcher again |
| Browser opens but the page is empty | wait for the first collection, or press "지금 수집" (collect now) |
| "port is in use by another program" | start with `--port 8780`, or set `bind_port` in `settings.yaml` |
| Start over with the example configuration | close Newsmon, then rename `%LOCALAPPDATA%\Newsmon\config`. Your database in `data\` is kept. |
