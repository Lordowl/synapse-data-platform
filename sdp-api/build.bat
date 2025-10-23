@echo off
REM =========================================================
REM Synapse Data Platform API - Build Script
REM =========================================================
echo.
echo ========================================
echo   SDP-API Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python non trovato! Installa Python 3.11 o superiore.
    pause
    exit /b 1
)

echo [INFO] Python trovato!
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Virtual environment non trovato. Creazione in corso...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Errore nella creazione del virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment creato!
)

REM Activate virtual environment
echo [INFO] Attivazione virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Errore nell'attivazione del virtual environment.
    pause
    exit /b 1
)

echo [OK] Virtual environment attivato!
echo.

REM Install dependencies
echo [INFO] Installazione dipendenze...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Errore nell'installazione delle dipendenze.
    pause
    exit /b 1
)

echo [OK] Dipendenze installate!
echo.

REM Install PyInstaller
echo [INFO] Installazione PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Errore nell'installazione di PyInstaller.
    pause
    exit /b 1
)

echo [OK] PyInstaller installato!
echo.

REM Clean previous builds
echo [INFO] Pulizia build precedenti...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
echo [OK] Build precedenti pulite!
echo.

REM Build executable
echo [INFO] Build eseguibile in corso...
echo [INFO] Questo processo potrebbe richiedere alcuni minuti...
echo.
pyinstaller sdp-api.spec
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Errore durante la build!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   BUILD COMPLETATA CON SUCCESSO!
echo ========================================
echo.
echo [OK] Eseguibile creato in: dist\sdp-api.exe
echo.
echo [INFO] Per eseguire l'API:
echo        cd dist
echo        sdp-api.exe
echo.
echo [INFO] Opzioni aggiuntive:
echo        sdp-api.exe --host 0.0.0.0 --port 9123
echo        sdp-api.exe --config (mostra configurazione)
echo        sdp-api.exe --regenerate-secret (rigenera SECRET_KEY)
echo.

pause