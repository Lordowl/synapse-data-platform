#!/bin/bash
# Script per eseguire i test della suite SDP API

echo "======================================="
echo "  Synapse Data Platform - Test Suite"
echo "======================================="
echo ""

# Controlla se l'ambiente virtuale esiste
if [ ! -f "venv/bin/pytest" ]; then
    echo "[ERRORE] Ambiente virtuale non trovato o pytest non installato"
    echo "Esegui: pip install -r requirements.txt"
    exit 1
fi

# Se nessun argomento, esegui tutti i test
if [ $# -eq 0 ]; then
    echo "Eseguendo tutti i test..."
    echo ""
    venv/bin/pytest tests/ -v
    exit 0
fi

# Comandi speciali
case "$1" in
    coverage)
        echo "Eseguendo test con coverage..."
        echo ""
        venv/bin/pytest tests/ --cov=. --cov-report=html --cov-report=term
        echo ""
        echo "Report HTML generato in: htmlcov/index.html"
        ;;
    fast)
        echo "Eseguendo test in modalità veloce..."
        echo ""
        venv/bin/pytest tests/ -x
        ;;
    auth)
        echo "Eseguendo test autenticazione..."
        echo ""
        venv/bin/pytest tests/test_auth.py -v
        ;;
    users)
        echo "Eseguendo test users..."
        echo ""
        venv/bin/pytest tests/test_users.py -v
        ;;
    banks)
        echo "Eseguendo test banks..."
        echo ""
        venv/bin/pytest tests/test_banks.py -v
        ;;
    flows)
        echo "Eseguendo test flows..."
        echo ""
        venv/bin/pytest tests/test_flows.py -v
        ;;
    reportistica)
        echo "Eseguendo test reportistica..."
        echo ""
        venv/bin/pytest tests/test_reportistica.py -v
        ;;
    help)
        echo ""
        echo "Uso: ./run_tests.sh [opzione]"
        echo ""
        echo "Opzioni:"
        echo "  [nessuna]       Esegui tutti i test"
        echo "  coverage        Esegui test con coverage report"
        echo "  fast            Stop al primo fallimento"
        echo "  auth            Test autenticazione"
        echo "  users           Test users"
        echo "  banks           Test banks"
        echo "  flows           Test flows"
        echo "  reportistica    Test reportistica"
        echo "  help            Mostra questo messaggio"
        echo ""
        echo "Esempi:"
        echo "  ./run_tests.sh"
        echo "  ./run_tests.sh coverage"
        echo "  ./run_tests.sh auth"
        echo "  ./run_tests.sh tests/test_auth.py -v"
        echo ""
        ;;
    *)
        echo "Eseguendo: pytest $@"
        echo ""
        venv/bin/pytest "$@"
        ;;
esac
