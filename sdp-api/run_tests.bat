@echo off
REM Script per eseguire i test della suite SDP API

echo =======================================
echo   Synapse Data Platform - Test Suite
echo =======================================
echo.

REM Controlla se l'ambiente virtuale esiste
if not exist "venv\Scripts\pytest.exe" (
    echo [ERRORE] Ambiente virtuale non trovato o pytest non installato
    echo Esegui: pip install -r requirements.txt
    exit /b 1
)

REM Se nessun argomento, esegui tutti i test
if "%~1"=="" (
    echo Eseguendo tutti i test...
    echo.
    venv\Scripts\pytest.exe tests\ -v
    goto :end
)

REM Comandi speciali
if "%~1"=="coverage" (
    echo Eseguendo test con coverage...
    echo.
    venv\Scripts\pytest.exe tests\ --cov=. --cov-report=html --cov-report=term
    echo.
    echo Report HTML generato in: htmlcov\index.html
    goto :end
)

if "%~1"=="fast" (
    echo Eseguendo test in modalità veloce...
    echo.
    venv\Scripts\pytest.exe tests\ -x
    goto :end
)

if "%~1"=="auth" (
    echo Eseguendo test autenticazione...
    echo.
    venv\Scripts\pytest.exe tests\test_auth.py -v
    goto :end
)

if "%~1"=="users" (
    echo Eseguendo test users...
    echo.
    venv\Scripts\pytest.exe tests\test_users.py -v
    goto :end
)

if "%~1"=="banks" (
    echo Eseguendo test banks...
    echo.
    venv\Scripts\pytest.exe tests\test_banks.py -v
    goto :end
)

if "%~1"=="flows" (
    echo Eseguendo test flows...
    echo.
    venv\Scripts\pytest.exe tests\test_flows.py -v
    goto :end
)

if "%~1"=="reportistica" (
    echo Eseguendo test reportistica...
    echo.
    venv\Scripts\pytest.exe tests\test_reportistica.py -v
    goto :end
)

if "%~1"=="help" (
    goto :help
)

REM Default: passa tutti gli argomenti a pytest
echo Eseguendo: pytest %*
echo.
venv\Scripts\pytest.exe %*
goto :end

:help
echo.
echo Uso: run_tests.bat [opzione]
echo.
echo Opzioni:
echo   [nessuna]       Esegui tutti i test
echo   coverage        Esegui test con coverage report
echo   fast            Stop al primo fallimento
echo   auth            Test autenticazione
echo   users           Test users
echo   banks           Test banks
echo   flows           Test flows
echo   reportistica    Test reportistica
echo   help            Mostra questo messaggio
echo.
echo Esempi:
echo   run_tests.bat
echo   run_tests.bat coverage
echo   run_tests.bat auth
echo   run_tests.bat tests\test_auth.py -v
echo.

:end
