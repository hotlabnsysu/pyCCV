@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo pyCCV virtual environment setup
echo.
choice /C YN /M "Continue"
if errorlevel 2 (
    echo Cancelled.
    pause
    exit /b 0
)

set "PY_CMD="
set "PY_VER="

echo.
echo [1/6] Detecting Python...
call :detect_python
if errorlevel 1 (
    echo.
    echo [ERROR] Python 3.10 / 3.11 / 3.12 was not found.
    echo Install Python and enable "Add Python to PATH".
    echo If Windows Store aliases are enabled, disable python.exe/python3.exe app execution aliases.
    echo.
    pause
    exit /b 1
)
echo Found Python %PY_VER% using "%PY_CMD%"

echo.
echo [2/6] Creating venv...
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 (
        echo Existing venv is valid. Skipping creation.
        goto activate_venv
    )
)

if exist "venv" (
    echo Existing venv is invalid. Recreating...
    rmdir /s /q "venv"
)

call %PY_CMD% -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo venv created successfully.

:activate_venv
echo.
echo [3/6] Activating venv...
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv\Scripts\python.exe not found.
    pause
    exit /b 1
)
set "VIRTUAL_ENV=%~dp0venv"
set "PATH=%~dp0venv\Scripts;%PATH%"

echo.
echo [4/6] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo.
echo [5/6] Removing legacy full PySide6 packages...
python -m pip uninstall -y PySide6 PySide6-Addons
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to remove legacy PySide6 packages.
    echo.
    pause
    exit /b 1
)

echo.
echo [6/6] Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install requirements.
    echo Check network access and package conflicts.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup completed.
echo ========================================
echo.
echo Next steps:
echo   1. Run: venv\Scripts\activate.bat ^& python main.py
echo   2. To leave venv: deactivate
echo.
pause
exit /b 0

:detect_python
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.10"
    for /f "tokens=2 delims= " %%v in ('py -3.10 --version 2^>^&1') do set "PY_VER=%%v"
    exit /b 0
)

py --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2 delims= " %%v in ('py --version 2^>^&1') do set "PY_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do set "PY_MAJOR_MINOR=%%a.%%b"
    if "%PY_MAJOR_MINOR%"=="3.10" (
        set "PY_CMD=py"
        exit /b 0
    )
    if "%PY_MAJOR_MINOR%"=="3.11" (
        set "PY_CMD=py"
        exit /b 0
    )
    if "%PY_MAJOR_MINOR%"=="3.12" (
        set "PY_CMD=py"
        exit /b 0
    )
)

python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do set "PY_MAJOR_MINOR=%%a.%%b"
    if "%PY_MAJOR_MINOR%"=="3.10" (
        set "PY_CMD=python"
        exit /b 0
    )
    if "%PY_MAJOR_MINOR%"=="3.11" (
        set "PY_CMD=python"
        exit /b 0
    )
    if "%PY_MAJOR_MINOR%"=="3.12" (
        set "PY_CMD=python"
        exit /b 0
    )
)

exit /b 1
