@echo off
chcp 65001 >nul

:: Re-launch self in minimized window.
if "%~1" neq "__MINIMIZED__" (
    start "" /min "%ComSpec%" /d /c call "%~f0" __MINIMIZED__
    exit
)

title pyCCV
echo [ pyCCV ]
echo Preparing launch...

cd /d "%~dp0"

:: Prefer project venv when it is healthy. If missing or broken, fall back to
:: the local Python installation.
if exist "venv\Scripts\python.exe" goto :TRY_VENV
goto :USE_LOCAL_PYTHON

:TRY_VENV
"%~dp0venv\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo [Warning] venv is broken. Falling back to local Python.
    goto :USE_LOCAL_PYTHON
)

echo Using venv: "%~dp0venv"
set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
set "PYTHON_ARGS="
goto :RUN_APP

:USE_LOCAL_PYTHON
echo [Warning] No usable venv found. Trying local Python.

py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    set "PYTHON_ARGS=-3.10"
    goto :RUN_APP
)

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [Error] Python is not available.
    echo Install Python, or create the project venv with venv_setup.bat.
    echo.
    exit /b 1
)

set "PYTHON_CMD=python"
set "PYTHON_ARGS="

:RUN_APP
echo Running: main.py
echo ---------------------------------------
"%PYTHON_CMD%" %PYTHON_ARGS% "main.py"
set "EXIT_CODE=%errorlevel%"
echo ---------------------------------------

if %EXIT_CODE% neq 0 (
    echo.
    echo [Error] Application exited with code: %EXIT_CODE%
    echo.
    exit /b %EXIT_CODE%
)

echo Launch finished.
exit /b 0
