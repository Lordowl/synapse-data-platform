"""
Script per monitorare lo stato del sync reposync
Uso: python monitor_sync.py
"""
import sqlite3
import psutil
from datetime import datetime
import os

DB_PATH = 'C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/sdp.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Leggi info dal database (gestito da reposync)
cursor.execute("SELECT operation_type, start_time, end_time, update_interval FROM sync_runs WHERE id = 1")
result = cursor.fetchone()

if not result:
    print("[ERROR] Nessun record sync_runs trovato")
    conn.close()
    exit(1)

operation_type, start_time, end_time, update_interval = result

print("="*80)
print("STATO SYNC REPOSYNC")
print("="*80)
print(f"Operation Type:  {operation_type}")
print(f"DB Start Time:   {start_time}")
print(f"DB End Time:     {end_time}")
print(f"Update Interval: {update_interval} minuti")
print()

# Leggi PID dal file
import os as os2
pid_file = os2.path.join(os2.path.dirname(DB_PATH), "sync_logs", "current_sync.pid")

pid = None
stdout_log = None
stderr_log = None
user = None
sync_start_time = None

if os2.path.exists(pid_file):
    with open(pid_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("PID:"):
                pid = int(line.split(":")[1])
            elif line.startswith("User:"):
                user = line.split(":")[1]
            elif line.startswith("Stdout:"):
                stdout_log = line.split(":", 1)[1]
            elif line.startswith("Stderr:"):
                stderr_log = line.split(":", 1)[1]
            elif line.startswith("StartTime:"):
                sync_start_time = line.split(":", 1)[1]

    print(f"Lanciato da:     {user}")
    print(f"Started At:      {sync_start_time}")
    print(f"PID:             {pid}")
    print()

    # Verifica se il processo è ancora attivo
    try:
        proc = psutil.Process(pid)
        if proc.is_running():
            print("[OK] PROCESSO ATTIVO")
            print(f"  Nome:          {proc.name()}")
            print(f"  Status:        {proc.status()}")
            print(f"  CPU:           {proc.cpu_percent(interval=0.1)}%")
            print(f"  Memory:        {proc.memory_info().rss / 1024 / 1024:.2f} MB")
            print(f"  Create Time:   {datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("[WARNING] PROCESSO NON ATTIVO (terminato normalmente)")
    except psutil.NoSuchProcess:
        print(f"[ERROR] PROCESSO PID {pid} NON TROVATO (crash o terminato)")
    print()

    # Mostra percorsi log
    print("LOG FILES:")
    print(f"  Stdout: {stdout_log}")
    if stdout_log and os.path.exists(stdout_log):
        size_kb = os.path.getsize(stdout_log) / 1024
        print(f"          (size: {size_kb:.2f} KB)")
    else:
        print(f"          (file non trovato)")

    print(f"  Stderr: {stderr_log}")
    if stderr_log and os.path.exists(stderr_log):
        size_kb = os.path.getsize(stderr_log) / 1024
        print(f"          (size: {size_kb:.2f} KB)")
    else:
        print(f"          (file non trovato)")

    print()
    print("ULTIMI 20 RIGHE STDOUT:")
    print("-"*80)
    if stdout_log and os.path.exists(stdout_log):
        with open(stdout_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    else:
        print("(nessun log)")

    print()
    print("ULTIMI 20 RIGHE STDERR:")
    print("-"*80)
    if stderr_log and os.path.exists(stderr_log):
        with open(stderr_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    else:
        print("(nessun log)")

else:
    print("[WARNING] Nessun PID registrato (sync mai avviato o record non aggiornato)")

print("="*80)

conn.close()
