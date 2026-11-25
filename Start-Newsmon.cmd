@echo off
chcp 65001 >nul
rem Newsmon launcher for Windows: double-click to start. Newsmon opens in your browser.
rem Settings and the database live in %LOCALAPPDATA%\Newsmon (kept when you update or move this folder).
rem   Start-Newsmon.cmd --check      install/verify only, then exit (used by CI)
rem   Start-Newsmon.cmd --no-browser start without opening the browser
setlocal EnableExtensions
title Newsmon
cd /d "%~dp0"
if not exist "pyproject.toml" goto :nofolder

rem Keep the Python environment outside this folder: short path (Windows MAX_PATH) and survives updates.
if not defined UV_PROJECT_ENVIRONMENT set "UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\Newsmon\venv"

set "UV="
for /f "delims=" %%U in ('where uv 2^>nul') do if not defined UV set "UV=%%U"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV goto :installuv

:haveuv
echo Preparing Newsmon. The first start downloads Python and libraries, which can take a few minutes.
echo Newsmon 준비 중입니다. 처음 실행할 때는 몇 분 걸릴 수 있습니다.
"%UV%" sync --frozen --no-dev --quiet
if errorlevel 1 goto :syncfailed
if /i "%~1"=="--check" goto :check
"%UV%" run --frozen --no-dev --no-sync newsmon-desktop %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Newsmon stopped with an error, code %RC%. See the messages above.
  echo Newsmon이 오류로 종료되었습니다. 위의 메시지를 확인하세요.
  pause
)
exit /b %RC%

:check
"%UV%" run --frozen --no-dev --no-sync newsmon --version
exit /b %ERRORLEVEL%

:installuv
echo.
echo Newsmon needs "uv", a small free tool that installs Python and Newsmon's libraries for your Windows account.
echo It does not need administrator rights. Details: https://docs.astral.sh/uv/
echo Newsmon을 실행하려면 uv 설치가 필요합니다. 관리자 권한은 필요 없습니다.
echo.
if /i "%~1"=="--check" goto :douv
choice /c YN /m "Install uv now? 지금 설치할까요?"
if errorlevel 2 goto :nouv
:douv
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV goto :nouv
goto :haveuv

:nouv
echo uv is not installed, so Newsmon cannot start. Install it from https://docs.astral.sh/uv/ and run this file again.
echo uv가 설치되지 않아 Newsmon을 시작할 수 없습니다.
pause
exit /b 1

:syncfailed
echo.
echo Installing Newsmon's libraries failed. Check your internet connection and run this file again.
echo 라이브러리 설치에 실패했습니다. 인터넷 연결을 확인한 뒤 다시 실행하세요.
pause
exit /b 1

:nofolder
echo This launcher must stay in the Newsmon folder, next to pyproject.toml.
pause
exit /b 1
